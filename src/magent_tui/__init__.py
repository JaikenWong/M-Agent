"""magent-tui: 基于 AutoGen + Textual 的多智能体协作 TUI。"""

from .config_models import AgentConfig, AppConfig, ModelConfig, WorkflowConfig
from .templates import TEMPLATE_LIBRARY, instantiate_template, template_names

__all__ = [
    "AgentConfig",
    "AppConfig",
    "ModelConfig",
    "WorkflowConfig",
    "TEMPLATE_LIBRARY",
    "instantiate_template",
    "template_names",
]

__version__ = "0.1.0"
