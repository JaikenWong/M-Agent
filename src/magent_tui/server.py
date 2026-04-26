"""FastAPI 服务器：REST + WebSocket 事件流。"""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Optional

from fastapi import Body, FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config_models import AppConfig, AgentConfig, ModelConfig, WorkflowConfig
from .run_events import RunEvent
from .run_service import RunService
from .task_state import Task, TaskManager
from .templates import describe_templates, instantiate_template, template_names
from .doctor import run_doctor
from .settings_loader import (
    anthropic_base_url_from_merged_settings,
    anthropic_key_from_merged_settings,
    apply_claude_code_to_config,
    openai_base_url_from_merged_settings,
    openai_key_from_merged_settings,
)


class AgentAddRequest(BaseModel):
    name: str
    role: str = ""
    system_prompt: str
    workspace: Optional[str] = None
    model: Optional[str] = None


class ConfigUpdateRequest(BaseModel):
    """全字段可选；须作为 JSON 请求体。模块级定义避免嵌套类 + Body() 的 ForwardRef 问题。"""

    project_name: Optional[str] = None
    workspace_root: Optional[str] = None
    workflow_mode: Optional[str] = None
    max_turns: Optional[int] = None
    use_claude_code_settings: Optional[bool] = None
    default_model: Optional[str] = None


class ModelUpsertRequest(BaseModel):
    """编辑/新增单个 model；空字符串视为清空（回退到合并 settings/env）。"""

    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


def _model_with_resolution(cfg: AppConfig, key: str, m: ModelConfig) -> dict:
    """返回 model dict，附 resolved_* 字段以便 UI 显示「已合并出的有效值与来源」。

    出于安全考虑，不返回 api_key 原文，只返回是否存在与来源（config / claude_settings / env / none）。
    """
    merge = cfg.use_claude_code_settings
    explicit_key = bool((m.api_key or "").strip())
    explicit_base = bool((m.base_url or "").strip())

    resolved_key = m.resolved_api_key(merge) or ""
    resolved_base = m.resolved_base_url(merge) or ""

    def _key_source() -> str:
        if explicit_key:
            return "config"
        if not resolved_key:
            return "none"
        if merge:
            if m.provider == "anthropic" and (anthropic_key_from_merged_settings() or "") == resolved_key:
                return "claude_settings"
            if m.provider in ("openai", "openai_compatible", "litellm") and (
                openai_key_from_merged_settings() or ""
            ) == resolved_key:
                return "claude_settings"
        return "env"

    def _base_source() -> str:
        if explicit_base:
            return "config"
        if not resolved_base:
            return "none"
        if merge:
            if m.provider == "anthropic" and (anthropic_base_url_from_merged_settings() or "") == resolved_base:
                return "claude_settings"
            if m.provider in ("openai", "openai_compatible", "litellm") and (
                openai_base_url_from_merged_settings() or ""
            ) == resolved_base:
                return "claude_settings"
        return "env"

    base = m.model_dump(exclude_none=True)
    base.update(
        {
            "resolved_api_key_present": bool(resolved_key),
            "resolved_api_key_source": _key_source(),
            "resolved_base_url": resolved_base or None,
            "resolved_base_url_source": _base_source(),
        }
    )
    return base


def _config_response(cfg: AppConfig) -> dict:
    """统一构造 GET / PUT 配置返回，让 models 携带 resolved_* 元信息。"""
    data = cfg.model_dump(exclude_none=True)
    data["models"] = {k: _model_with_resolution(cfg, k, m) for k, m in cfg.models.items()}
    return data


def create_app(config: Optional[AppConfig] = None, *, config_path: Optional[Path] = None) -> FastAPI:
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
    apply_claude_code_to_config(config)
    app.state.config = config
    app.state.config_path = config_path
    # 与 RunArtifacts / ensure_workspace 使用同一套解析路径，避免相对路径 + 不同 cwd 时 runs 与 .tasks 错位
    _ws = config.ensure_workspace()
    app.state.task_manager = TaskManager(_ws / ".tasks.json")
    app.state.task_manager.load()
    app.state.task_manager.reconcile_stale_active_on_load()
    app.state.active_runs: dict[str, asyncio.Task] = {}
    app.state.active_run_services: dict[str, RunService] = {}
    app.state.run_cancellations: dict[str, asyncio.Event] = {}
    app.state.ws_tasks: dict[int, set[str]] = {}
    app.state.connected_clients: list[WebSocket] = []

    # -- REST Endpoints --

    @app.get("/api/config")
    async def get_config():
        return _config_response(app.state.config)

    @app.put("/api/config")
    async def update_config(req: ConfigUpdateRequest = Body(...)):
        path = getattr(app.state, "config_path", None)
        has_file = path is not None and Path(path).is_file()
        if req.use_claude_code_settings is not None and has_file:
            cfg = AppConfig.from_yaml(path)
            cfg.use_claude_code_settings = req.use_claude_code_settings
            apply_claude_code_to_config(cfg)
            app.state.config = cfg
        cfg = app.state.config
        if req.project_name:
            cfg.project_name = req.project_name
        if req.workspace_root:
            cfg.workspace_root = req.workspace_root
        if req.workflow_mode:
            cfg.workflow.mode = req.workflow_mode
        if req.max_turns is not None:
            cfg.workflow.max_turns = req.max_turns
        if req.use_claude_code_settings is not None and not has_file:
            cfg.use_claude_code_settings = req.use_claude_code_settings
            apply_claude_code_to_config(cfg)
        if req.default_model:
            if req.default_model not in cfg.models:
                raise HTTPException(400, f"default_model `{req.default_model}` 不在 models 中")
            cfg.default_model = req.default_model
        cfg.ensure_workspace()
        return _config_response(cfg)

    @app.put("/api/models/{key}")
    async def upsert_model(key: str, req: ModelUpsertRequest = Body(...)):
        """编辑或新增 models[key]。空字符串字段表示清空，让 resolved_* 回退到合并 settings/env。"""
        cfg: AppConfig = app.state.config
        existing = cfg.models.get(key)
        if existing is not None:
            data = existing.model_dump()
        else:
            data = ModelConfig().model_dump()

        provided = req.model_dump(exclude_unset=True)
        for field in ("api_key", "base_url"):
            if field in provided:
                v = provided[field]
                data[field] = (v or "").strip() or None
        for field in ("provider", "model"):
            if field in provided and provided[field] is not None:
                v = str(provided[field]).strip()
                if v:
                    data[field] = v
        for field in ("temperature", "max_tokens"):
            if field in provided:
                data[field] = provided[field]
        try:
            cfg.models[key] = ModelConfig(**data)
        except Exception as e:
            raise HTTPException(422, f"Invalid model fields: {e}")
        return _config_response(cfg)

    @app.delete("/api/models/{key}")
    async def delete_model(key: str):
        cfg: AppConfig = app.state.config
        if key not in cfg.models:
            raise HTTPException(404, f"Unknown model: {key}")
        if key == cfg.default_model:
            raise HTTPException(400, "Cannot delete default model")
        cfg.models.pop(key, None)
        return _config_response(cfg)

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

    async def _cancel_task(task_id: str) -> bool:
        cancelled = False
        cancel_event = app.state.run_cancellations.get(task_id)
        if cancel_event:
            cancel_event.set()
            cancelled = True
        svc = app.state.active_run_services.get(task_id)
        if svc:
            svc.cancel()
            cancelled = True
        return cancelled

    @app.delete("/api/tasks/{task_id}")
    async def delete_task(task_id: str):
        t = app.state.task_manager.get(task_id)
        if not t:
            raise HTTPException(404)
        if t.is_active:
            raise HTTPException(400, "Cannot delete active task, cancel it first")
        app.state.task_manager.remove(task_id)
        app.state.task_manager.save()
        return {"deleted": task_id}

    @app.post("/api/tasks/{task_id}/cancel")
    async def cancel_task(task_id: str):
        await _cancel_task(task_id)
        return {"cancelled": task_id}

    @app.get("/api/doctor")
    async def doctor():
        checks = run_doctor()
        return [{"label": c.label, "ok": c.ok, "detail": c.detail} for c in checks]

    @app.get("/api/runs")
    async def list_runs():
        root = app.state.config.ensure_workspace() / "runs"
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
        root = app.state.config.ensure_workspace() / "runs" / run_id
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

    @app.get("/api/runs/{run_id}/detail")
    async def run_detail(run_id: str):
        root = app.state.config.ensure_workspace() / "runs" / run_id
        if not root.is_dir():
            raise HTTPException(404)
        run_json = root / "run.json"
        data = json.loads(run_json.read_text(encoding="utf-8")) if run_json.exists() else {}
        task_md = root / "task.md"
        summary_md = root / "summary.md"
        data["task_content"] = task_md.read_text(encoding="utf-8") if task_md.exists() else None
        data["summary_content"] = summary_md.read_text(encoding="utf-8") if summary_md.exists() else None
        return data

    @app.delete("/api/runs/{run_id}")
    async def delete_run(run_id: str):
        root = app.state.config.ensure_workspace() / "runs" / run_id
        if not root.is_dir():
            raise HTTPException(404)
        shutil.rmtree(root)
        return {"deleted": run_id}

    # -- WebSocket Endpoint --

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        app.state.connected_clients.append(ws)
        ws_key = id(ws)
        app.state.ws_tasks.setdefault(ws_key, set())
        try:
            while True:
                try:
                    data = await ws.receive_text()
                    msg = json.loads(data)
                except json.JSONDecodeError:
                    await ws.send_json({"type": "error", "content": "Invalid JSON"})
                    continue
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
                    app.state.task_manager.save()
                    app.state.ws_tasks[ws_key].add(task_id)

                    run_task = asyncio.create_task(
                        _run_and_stream(ws, prompt, task_id, task_obj, cancel_event, app),
                        name=f"run:{task_id}",
                    )
                    app.state.active_runs[task_id] = run_task

                elif msg_type == "cancel_task":
                    task_id = msg.get("task_id")
                    if task_id:
                        await _cancel_task(task_id)

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
                                "config": _config_response(app.state.config),
                            })
                        except Exception:
                            pass

        except WebSocketDisconnect:
            pass
        finally:
            for task_id in list(app.state.ws_tasks.get(ws_key, set())):
                await _cancel_task(task_id)
            app.state.ws_tasks.pop(ws_key, None)
            if ws in app.state.connected_clients:
                app.state.connected_clients.remove(ws)

    async def _run_and_stream(ws, prompt, task_id, task_obj, cancel_event, app):
        svc = RunService(app.state.config)
        app.state.active_run_services[task_id] = svc
        was_cancelled = False
        try:
            async for event in svc.run(prompt):
                if cancel_event.is_set():
                    svc.cancel()
                    task_obj.cancel()
                    await ws.send_json({"type": "run_cancelled", "task_id": task_id})
                    was_cancelled = True
                    break
                payload = {"type": "run_event", "task_id": task_id, "event": event.to_dict()}
                for client in app.state.connected_clients:
                    try:
                        await client.send_json(payload)
                    except Exception:
                        pass
                if event.event_type == "run_started":
                    task_obj.run_dir = event.metadata.get("run_dir")
            if cancel_event.is_set() and not was_cancelled:
                task_obj.cancel()
                try:
                    await ws.send_json({"type": "run_cancelled", "task_id": task_id})
                except Exception:
                    pass
                was_cancelled = True
            if not was_cancelled:
                task_obj.finish(success=True)
        except asyncio.CancelledError:
            task_obj.cancel()
            was_cancelled = True
            raise
        except Exception as e:
            task_obj.finish(success=False, error=str(e))
            try:
                await ws.send_json({"type": "run_failed", "task_id": task_id, "error": str(e)})
            except Exception:
                pass
        finally:
            if not task_obj.is_finished:
                task_obj.finish(
                    success=False,
                    error="运行未正常结束（可能为连接断开或旧版本问题），已标为失败",
                )
            app.state.task_manager.save()
            app.state.active_runs.pop(task_id, None)
            app.state.active_run_services.pop(task_id, None)
            app.state.run_cancellations.pop(task_id, None)

    return app
