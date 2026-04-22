from __future__ import annotations

import unittest
from types import SimpleNamespace

from magent_tui.app import MAgentApp
from magent_tui.config_models import AgentConfig, AppConfig, ModelConfig, WorkflowConfig
from magent_tui.tab_app import MAgentTabApp


def _build_config() -> AppConfig:
    return AppConfig(
        project_name="test",
        workspace_root="deliverables",
        default_model="default",
        models={"default": ModelConfig(provider="anthropic", model="claude-sonnet-4-5")},
        agents=[
            AgentConfig(name="A1", role="R1", system_prompt="p1"),
            AgentConfig(name="A2", role="R2", system_prompt="p2"),
        ],
        workflow=WorkflowConfig(mode="round_robin", max_turns=2),
    )


class AgentSelectionGuardTest(unittest.TestCase):
    def test_tab_app_ignore_out_of_range_selection_event(self) -> None:
        app = MAgentTabApp(_build_config())
        app._selected_agent_index = 0
        event = SimpleNamespace(item=SimpleNamespace(id="agent-99"))
        app._selected_agent(event)  # type: ignore[arg-type]
        self.assertEqual(app._selected_agent_index, 0)

    def test_classic_app_ignore_out_of_range_selection_event(self) -> None:
        app = MAgentApp(_build_config())
        app._selected_agent_index = 0
        event = SimpleNamespace(item=SimpleNamespace(id="agent-99"))
        app._selected_agent(event)  # type: ignore[arg-type]
        self.assertEqual(app._selected_agent_index, 0)

