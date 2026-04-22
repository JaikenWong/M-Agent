from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from magent_tui.config_models import AgentConfig, AppConfig, ModelConfig, WorkflowConfig
from magent_tui.tab_app import MAgentTabApp


class TabAppSendTest(unittest.IsolatedAsyncioTestCase):
    async def test_enter_submits_task(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / "deliverables"
            cfg = AppConfig(
                project_name="tab-test",
                workspace_root=str(workspace),
                default_model="default",
                models={"default": ModelConfig(provider="anthropic", model="claude-sonnet-4-5")},
                agents=[AgentConfig(name="PM", role="产品经理", system_prompt="写 PRD")],
                workflow=WorkflowConfig(mode="round_robin", max_turns=1),
            )
            app = MAgentTabApp(cfg)
            async with app.run_test() as pilot:
                area = app.query_one("#task-input")
                area.focus()
                area.value = "请输出一个最小 PRD"
                await pilot.press("enter")
                for _ in range(30):
                    if not app._task_running:
                        break
                    await pilot.pause(0.1)
            runs_dir = workspace / "runs"
            self.assertTrue(runs_dir.exists())
            self.assertTrue(any(runs_dir.iterdir()))

