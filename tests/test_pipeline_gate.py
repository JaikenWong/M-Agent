from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from magent_tui.config_models import AgentConfig, AppConfig, ModelConfig, WorkflowConfig
from magent_tui.run_service import RunService


class PipelineGateTest(unittest.IsolatedAsyncioTestCase):
    async def test_pipeline_required_artifacts_gate_in_mock_mode(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "deliverables"
            cfg = AppConfig(
                project_name="pipeline-test",
                workspace_root=str(root),
                default_model="default",
                models={"default": ModelConfig(provider="anthropic", model="claude-sonnet-4-5")},
                agents=[
                    AgentConfig(name="PM", role="产品经理", system_prompt="写 PRD"),
                    AgentConfig(name="Architect", role="架构师", system_prompt="写架构"),
                ],
                workflow=WorkflowConfig(
                    mode="pipeline",
                    max_turns=6,
                    required_artifacts={"PM": ["PRD.md"]},
                ),
            )
            service = RunService(cfg)
            messages = []
            async for event in service.run("请按 pipeline 协作"):
                if event.event_type == "agent_message":
                    messages.append(event.content or "")
                await asyncio.sleep(0)

            self.assertTrue(any("pipeline 门禁失败" in msg for msg in messages))

