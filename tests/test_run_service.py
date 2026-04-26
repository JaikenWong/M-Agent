from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from magent_tui.config_models import AgentConfig, AppConfig, ModelConfig, WorkflowConfig
from magent_tui.run_service import RunService


class RunServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_run_service_emits_events_and_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "deliverables"
            cfg = AppConfig(
                project_name="test",
                workspace_root=str(root),
                use_claude_code_settings=False,
                default_model="default",
                models={"default": ModelConfig(provider="anthropic", model="claude-sonnet-4-5")},
                agents=[
                    AgentConfig(name="PM", role="产品经理", system_prompt="写 PRD"),
                    AgentConfig(name="QA", role="测试", system_prompt="验收"),
                ],
                workflow=WorkflowConfig(mode="round_robin", max_turns=2),
            )
            no_keys = {k: "" for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY")}
            with mock.patch.dict(os.environ, no_keys, clear=False):
                service = RunService(cfg)
                events = []
                async for event in service.run("请完成一个最小任务"):
                    events.append(event)
                    await asyncio.sleep(0)

                kinds = [e.event_type for e in events]
                self.assertIn("run_started", kinds)
                self.assertIn("agent_message", kinds)
                self.assertIn("run_completed", kinds)

                runs_dir = root / "runs"
                self.assertTrue(runs_dir.exists())
                run_entries = list(runs_dir.iterdir())
                self.assertEqual(len(run_entries), 1)
                run_dir = run_entries[0]
                self.assertTrue((run_dir / "run.json").exists())
                self.assertTrue((run_dir / "events.jsonl").exists())
                self.assertTrue((run_dir / "transcript.jsonl").exists())
                self.assertTrue((run_dir / "summary.md").exists())

