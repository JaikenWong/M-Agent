"""配置模型层：Pydantic 定义 Model / Agent / Workflow / App 配置。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class ModelConfig(BaseModel):
    """单个模型的连接配置。"""

    provider: Literal["anthropic", "openai", "openai_compatible", "litellm"] = "anthropic"
    model: str = "claude-sonnet-4-5"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    extra: dict[str, Any] = Field(default_factory=dict)

    def resolved_api_key(self, merge_claude_code_settings: bool = True) -> Optional[str]:
        """api_key 优先；否则（merge 为真）从合并的 Claude settings 读 env/顶层，再回退到进程环境变量。"""
        import os

        if self.api_key:
            return self.api_key
        if not merge_claude_code_settings:
            if self.provider == "anthropic":
                return os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
            if self.provider in ("openai", "openai_compatible", "litellm"):
                return os.getenv("OPENAI_API_KEY")
            return os.getenv("OPENAI_API_KEY")
        if self.provider == "anthropic":
            from .settings_loader import anthropic_key_from_merged_settings

            return (
                anthropic_key_from_merged_settings()
                or os.getenv("ANTHROPIC_API_KEY")
                or os.getenv("ANTHROPIC_AUTH_TOKEN")
            )
        if self.provider in ("openai", "openai_compatible", "litellm"):
            from .settings_loader import openai_key_from_merged_settings

            return openai_key_from_merged_settings() or os.getenv("OPENAI_API_KEY")
        return os.getenv("OPENAI_API_KEY")

    def resolved_base_url(self, merge_claude_code_settings: bool = True) -> Optional[str]:
        """与 resolved_api_key 相同的三段：显式 / 合并 settings / 环境变量。"""
        import os

        b = (self.base_url or "").strip()
        if b:
            return b
        if not merge_claude_code_settings:
            if self.provider == "anthropic":
                s = (os.getenv("ANTHROPIC_BASE_URL") or "").strip()
                return s or None
            s = (os.getenv("OPENAI_BASE_URL") or "").strip()
            return s or None
        if self.provider == "anthropic":
            from .settings_loader import anthropic_base_url_from_merged_settings

            s = (anthropic_base_url_from_merged_settings() or os.getenv("ANTHROPIC_BASE_URL") or "").strip()
            return s or None
        if self.provider in ("openai", "openai_compatible", "litellm"):
            from .settings_loader import openai_base_url_from_merged_settings

            s = (openai_base_url_from_merged_settings() or os.getenv("OPENAI_BASE_URL") or "").strip()
            return s or None
        s = (os.getenv("OPENAI_BASE_URL") or "").strip()
        return s or None

    def summary(self) -> str:
        provider = self.provider
        model = self.model
        return f"{provider}:{model}"


class AgentConfig(BaseModel):
    """单个 Agent 的配置。"""

    name: str
    role: str = ""
    system_prompt: str
    model: Optional[str] = None  # 引用 AppConfig.models 中的 key，None = 使用 default
    workspace: Optional[str] = None  # 相对 workspace_root 的子目录，None = 用 name
    tools: list[str] = Field(default_factory=list)
    description: str = ""

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("agent name 不能为空")
        return v.strip()

    def resolved_workspace(self) -> str:
        return self.workspace or self.name


class WorkflowConfig(BaseModel):
    """协作编排配置。"""

    mode: Literal["round_robin", "selector", "single", "pipeline"] = "round_robin"
    max_turns: int = 12
    termination_keywords: list[str] = Field(default_factory=lambda: ["TERMINATE", "任务完成"])
    selector_prompt: Optional[str] = None
    required_artifacts: dict[str, list[str]] = Field(default_factory=dict)
    liaison_agent: Optional[str] = Field(
        default=None,
        description=(
            "对用户的总接口：须与 `agents` 中某 `name` 一致（常设为 PM）。"
            "不自动改编排逻辑；用于约定「谁用自然语言向用户汇报、要澄清、收反馈」。"
        ),
    )


class AppConfig(BaseModel):
    """整个应用的顶层配置。"""

    project_name: str = "m-agent"
    workspace_root: str = "deliverables"
    use_claude_code_settings: bool = Field(
        default=True,
        description=(
            "为 True：与 Claude Code 一致，从 ~/.claude 等合并后的 settings 注入 models.default，"
            "并对缺凭据的模型项用 default_model_config 补全（含读 settings）。"
            "为 False：仅使用本 YAML + 进程环境变量（ANTHROPIC_* 等），不读取 Claude Code 的 settings 文件。"
        ),
    )
    default_model: str = "default"
    models: dict[str, ModelConfig] = Field(default_factory=dict)
    agents: list[AgentConfig] = Field(default_factory=list)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)

    def get_model_for_agent(self, agent: AgentConfig) -> ModelConfig:
        key = agent.model or self.default_model
        if key not in self.models:
            if self.models:
                return next(iter(self.models.values()))
            return ModelConfig()
        return self.models[key]

    def model_name_for_agent(self, agent: AgentConfig) -> str:
        key = agent.model or self.default_model
        return key if key in self.models else self.default_model

    def ensure_workspace(self) -> Path:
        """创建 workspace_root 及每个 Agent 的子目录。"""
        root = Path(self.workspace_root).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        for agent in self.agents:
            (root / agent.resolved_workspace()).mkdir(parents=True, exist_ok=True)
        return root

    @classmethod
    def from_yaml(cls, path: str | Path) -> "AppConfig":
        import yaml

        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls.model_validate(data)

    def to_yaml(self, path: str | Path) -> None:
        import yaml

        data = self.model_dump(exclude_none=True)
        Path(path).write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False, indent=2),
            encoding="utf-8",
        )
