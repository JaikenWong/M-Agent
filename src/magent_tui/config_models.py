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

    def resolved_api_key(self) -> Optional[str]:
        import os

        if self.api_key:
            return self.api_key
        if self.provider == "anthropic":
            return os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
        return os.getenv("OPENAI_API_KEY")

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


class AppConfig(BaseModel):
    """整个应用的顶层配置。"""

    project_name: str = "m-agent"
    workspace_root: str = "deliverables"
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
