from __future__ import annotations

import asyncio
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from magent_tui import server
from magent_tui.config_models import AgentConfig, AppConfig, ModelConfig, WorkflowConfig
from magent_tui.run_events import RunEvent


class _FakeRunService:
    def __init__(self, _config) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    async def run(self, _task: str):
        yield RunEvent.now(
            "run_started",
            "fake-run",
            content="started",
            metadata={"run_dir": "fake/run"},
        )
        while not self._cancelled:
            await asyncio.sleep(0.02)


class ServerWebSocketTest(unittest.TestCase):
    def test_cancel_task_updates_state_and_streams_cancelled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / "deliverables"
            cfg = AppConfig(
                project_name="server-test",
                workspace_root=str(workspace),
                default_model="default",
                models={"default": ModelConfig(provider="anthropic", model="claude-sonnet-4-5")},
                agents=[AgentConfig(name="PM", role="产品经理", system_prompt="写 PRD")],
                workflow=WorkflowConfig(mode="round_robin", max_turns=1),
            )

            original = server.RunService
            server.RunService = _FakeRunService
            try:
                app = server.create_app(cfg)
                client = TestClient(app)
                with client.websocket_connect("/ws") as ws:
                    ws.send_json({"type": "start_task", "prompt": "测试取消"})

                    first = ws.receive_json()
                    self.assertEqual(first["type"], "run_event")
                    self.assertEqual(first["event"]["event_type"], "run_started")
                    task_id = first["task_id"]

                    ws.send_json({"type": "cancel_task", "task_id": task_id})

                    deadline = time.time() + 2.0
                    cancelled = None
                    while time.time() < deadline:
                        msg = ws.receive_json()
                        if msg.get("type") == "run_cancelled" and msg.get("task_id") == task_id:
                            cancelled = msg
                            break
                    self.assertIsNotNone(cancelled, "未收到 run_cancelled 消息")

                    deadline = time.time() + 2.0
                    task_status = None
                    while time.time() < deadline:
                        tasks = client.get("/api/tasks").json()
                        target = next((t for t in tasks if t["id"] == task_id), None)
                        if target:
                            task_status = target["status"]
                            if task_status == "cancelled":
                                break
                        time.sleep(0.05)
                    self.assertEqual(task_status, "cancelled")
            finally:
                server.RunService = original
