"""从 Claude Code 的 `~/.claude/settings.json` 读取模型/Key 配置。

Claude Code settings.json 常见字段（非公开契约，尽量宽松解析）：
- `env.ANTHROPIC_API_KEY` / `env.ANTHROPIC_BASE_URL`
- `env.ANTHROPIC_MODEL` 或 `model`
- 顶层可能的 `apiKeyHelper`（忽略）
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from .config_models import ModelConfig


CLAUDE_SETTINGS_PATHS = [
    Path.home() / ".claude" / "settings.json",
    Path.home() / ".config" / "claude" / "settings.json",
]


def find_claude_settings() -> Optional[Path]:
    for p in CLAUDE_SETTINGS_PATHS:
        if p.exists():
            return p
    return None


def load_claude_settings() -> dict:
    path = find_claude_settings()
    if not path:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def model_from_claude_settings() -> Optional[ModelConfig]:
    """尝试从 Claude Code settings 构造一个默认 ModelConfig。"""
    data = load_claude_settings()
    if not data:
        return None

    env = data.get("env") or {}
    api_key = env.get("ANTHROPIC_API_KEY") or data.get("api_key")
    base_url = env.get("ANTHROPIC_BASE_URL") or data.get("base_url")
    model = env.get("ANTHROPIC_MODEL") or data.get("model") or "claude-sonnet-4-5"

    if not api_key and not base_url:
        return None

    return ModelConfig(
        provider="anthropic",
        model=model,
        api_key=api_key,
        base_url=base_url,
    )


def default_model_config() -> ModelConfig:
    """按优先级返回默认 ModelConfig：Claude settings → env → 占位。"""
    m = model_from_claude_settings()
    if m:
        return m

    if os.getenv("ANTHROPIC_API_KEY"):
        return ModelConfig(
            provider="anthropic",
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            base_url=os.getenv("ANTHROPIC_BASE_URL"),
        )
    if os.getenv("OPENAI_API_KEY"):
        return ModelConfig(
            provider="openai",
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )

    return ModelConfig(provider="anthropic", model="claude-sonnet-4-5")
