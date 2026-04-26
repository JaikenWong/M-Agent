"""FastAPI 服务器：REST + WebSocket 事件流。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config_models import AppConfig, AgentConfig, ModelConfig, WorkflowConfig
from .run_events import RunEvent
from .run_service import RunService
from .task_state import Task, TaskManager
from .templates import describe_templates, instantiate_template, template_names
from .doctor import run_doctor
from .settings_loader import default_model_config


def create_app(config: Optional[AppConfig] = None) -> FastAPI:
    app = FastAPI(title="m-agent", version="0.2.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -- Shared state --
    if config is None:
        from .main import _build_default_config
        config = _build_default_config("dev_team_oob")
    app.state.config = config
    app.state.task_manager = TaskManager(Path(config.workspace_root) / ".tasks.json")
    app.state.task_manager.load()
    app.state.active_runs: dict[str, asyncio.Task] = {}
    app.state.run_cancellations: dict[str, asyncio.Event] = {}
    app.state.connected_clients: list[WebSocket] = []

    # -- Request models --
    class TaskRequest(BaseModel):
        prompt: str

    class AgentAddRequest(BaseModel):
        name: str
        role: str = ""
        system_prompt: str
        workspace: Optional[str] = None
        model: Optional[str] = None

    class ConfigUpdateRequest(BaseModel):
        project_name: Optional[str] = None
        workspace_root: Optional[str] = None
        workflow_mode: Optional[str] = None
        max_turns: Optional[int] = None

    # -- REST Endpoints --

    @app.get("/api/config")
    async def get_config():
        return app.state.config.model_dump(exclude_none=True)

    @app.put("/api/config")
    async def update_config(req: ConfigUpdateRequest):
        cfg = app.state.config
        if req.project_name:
            cfg.project_name = req.project_name
        if req.workspace_root:
            cfg.workspace_root = req.workspace_root
        if req.workflow_mode:
            cfg.workflow.mode = req.workflow_mode
        if req.max_turns:
            cfg.workflow.max_turns = req.max_turns
        cfg.ensure_workspace()
        return cfg.model_dump(exclude_none=True)

    @app.get("/api/templates")
    async def list_templates():
        return [{"name": name, "description": desc} for name, desc in describe_templates()]

    @app.post("/api/templates/{name}/apply")
    async def apply_template(name: str):
        if name not in template_names():
            raise HTTPException(404, f"Unknown template: {name}")
        app.state.config.agents = instantiate_template(name)
        app.state.config.ensure_workspace()
        return {"applied": name, "agent_count": len(app.state.config.agents)}

    @app.get("/api/agents")
    async def list_agents():
        return [a.model_dump(exclude_none=True) for a in app.state.config.agents]

    @app.post("/api/agents")
    async def add_agent(req: AgentAddRequest):
        agent = AgentConfig(**req.model_dump())
        app.state.config.agents.append(agent)
        app.state.config.ensure_workspace()
        return agent.model_dump(exclude_none=True)

    @app.delete("/api/agents/{index}")
    async def delete_agent(index: int):
        if index < 0 or index >= len(app.state.config.agents):
            raise HTTPException(404)
        removed = app.state.config.agents.pop(index)
        return {"deleted": removed.name}

    @app.get("/api/workspace/tree")
    async def workspace_tree(path: str = "."):
        root = Path(app.state.config.workspace_root).resolve()
        target = (root / path).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            raise HTTPException(403, "Path outside workspace")
        if not target.exists():
            return {"path": str(path), "entries": []}
        entries = []
        for item in sorted(target.rglob("*")):
            rel = str(item.relative_to(root))
            entries.append({"path": rel, "is_dir": item.is_dir(), "size": item.stat().st_size if item.is_file() else 0})
        return {"path": str(path), "entries": entries}

    @app.get("/api/workspace/file")
    async def read_file(path: str):
        root = Path(app.state.config.workspace_root).resolve()
        target = (root / path).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            raise HTTPException(403, "Path outside workspace")
        if not target.is_file():
            raise HTTPException(404, "Not a file")
        try:
            content = target.read_text(encoding="utf-8")
        except Exception as e:
            raise HTTPException(500, str(e))
        return {"path": str(path), "content": content}

    @app.get("/api/tasks")
    async def list_tasks():
        return [t.to_dict() for t in app.state.task_manager.list()]

    @app.get("/api/tasks/{task_id}")
    async def get_task(task_id: str):
        t = app.state.task_manager.get(task_id)
        if not t:
            raise HTTPException(404)
        return t.to_dict()

    @app.post("/api/tasks/{task_id}/cancel")
    async def cancel_task(task_id: str):
        cancel_event = app.state.run_cancellations.get(task_id)
        if cancel_event:
            cancel_event.set()
        return {"cancelled": task_id}

    @app.get("/api/doctor")
    async def doctor():
        checks = run_doctor()
        return [{"label": c.label, "ok": c.ok, "detail": c.detail} for c in checks]

    @app.get("/api/runs")
    async def list_runs():
        root = Path(app.state.config.workspace_root) / "runs"
        if not root.exists():
            return []
        runs = []
        for d in sorted(root.iterdir(), reverse=True):
            if d.is_dir():
                run_json = d / "run.json"
                if run_json.exists():
                    data = json.loads(run_json.read_text(encoding="utf-8"))
                    data["run_dir"] = str(d)
                    runs.append(data)
        return runs

    @app.get("/api/runs/{run_id}/events")
    async def run_events(run_id: str):
        root = Path(app.state.config.workspace_root) / "runs" / run_id
        events_path = root / "events.jsonl"
        if not events_path.exists():
            return []
        events = []
        for line in events_path.read_text(encoding="utf-8").strip().splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return events

    # -- WebSocket Endpoint --

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        app.state.connected_clients.append(ws)
        try:
            while True:
                data = await ws.receive_text()
                msg = json.loads(data)
                msg_type = msg.get("type")

                if msg_type == "start_task":
                    prompt = msg.get("prompt", "").strip()
                    if not prompt:
                        await ws.send_json({"type": "error", "content": "Empty prompt"})
                        continue
                    if not app.state.config.agents:
                        await ws.send_json({"type": "error", "content": "No agents configured"})
                        continue
                    task_id = f"task_{id(ws)}_{asyncio.get_event_loop().time()}"
                    cancel_event = asyncio.Event()
                    app.state.run_cancellations[task_id] = cancel_event

                    task_obj = Task(id=task_id, name=prompt[:50], prompt=prompt)
                    app.state.task_manager.add(task_obj)
                    task_obj.start()

                    await _run_and_stream(ws, prompt, task_id, task_obj, cancel_event, app)

                elif msg_type == "cancel_task":
                    task_id = msg.get("task_id")
                    cancel_event = app.state.run_cancellations.get(task_id)
                    if cancel_event:
                        cancel_event.set()

                elif msg_type == "update_config":
                    updates = msg.get("updates", {})
                    if "template" in updates:
                        name = updates["template"]
                        if name in template_names():
                            app.state.config.agents = instantiate_template(name)
                            app.state.config.ensure_workspace()
                    for client in app.state.connected_clients:
                        try:
                            await client.send_json({
                                "type": "config_updated",
                                "config": app.state.config.model_dump(exclude_none=True),
                            })
                        except Exception:
                            pass

        except WebSocketDisconnect:
            pass
        finally:
            if ws in app.state.connected_clients:
                app.state.connected_clients.remove(ws)

    async def _run_and_stream(ws, prompt, task_id, task_obj, cancel_event, app):
        svc = RunService(app.state.config)
        try:
            async for event in svc.run(prompt):
                if cancel_event.is_set():
                    task_obj.cancel()
                    await ws.send_json({"type": "run_cancelled", "task_id": task_id})
                    break
                payload = {"type": "run_event", "task_id": task_id, "event": event.to_dict()}
                for client in app.state.connected_clients:
                    try:
                        await client.send_json(payload)
                    except Exception:
                        pass
                if event.event_type == "run_started":
                    task_obj.run_dir = event.metadata.get("run_dir")
            task_obj.finish(success=True)
        except Exception as e:
            task_obj.finish(success=False, error=str(e))
            try:
                await ws.send_json({"type": "run_failed", "task_id": task_id, "error": str(e)})
            except Exception:
                pass
        finally:
            app.state.task_manager.save()
            app.state.run_cancellations.pop(task_id, None)

    return app
