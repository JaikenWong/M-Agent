"""从 Claude Code 与 Cursor 中一致的配置源读取「当前」模型与凭据，供 m-agent 使用。

与 Claude Code 行为对齐的要点：
- 深合并多份 `settings.json` 的 `env`（后写覆盖先写，与多文件层级类似）。
- 合并顺序（后者覆盖前者）：
  1) `~/.claude/settings.json` 或 `CLAUDE_CONFIG_DIR/settings.json`
  2) `~/.config/claude/settings.json`（与上一条路径不重复时）
  3) 当前工作目录下 `.claude/settings.json`（项目级）
  4) 当前工作目录下 `.claude/settings.local.json`（本机/个人覆盖）
- 模型字段：`env.ANTHROPIC_MODEL` 优先，否则顶层 `model`；支持 `sonnet`/`opus`/`haiku` 等别名，按
  `ANTHROPIC_DEFAULT_*_MODEL` 与 Claude Code 文档解析。

不在此实现与 Claude Code 无关的「骚操作」；无配置时只回落到进程环境变量，最后才是占位默认模型名。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .config_models import AppConfig

from .config_models import ModelConfig


def claude_config_dir() -> Path:
    raw = (os.environ.get("CLAUDE_CONFIG_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / ".claude").resolve()


def _deep_merge(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    r = dict(a)
    for k, v in b.items():
        if k in r and isinstance(r[k], dict) and isinstance(v, dict):
            r[k] = _deep_merge(r[k], v)
        else:
            r[k] = v
    return r


def _settings_json_paths_in_merge_order() -> list[Path]:
    cdir = claude_config_dir()
    g = cdir / "settings.json"
    xdg = Path.home() / ".config" / "claude" / "settings.json"
    out = [g]
    try:
        if g.resolve() != xdg.resolve():
            out.append(xdg)
    except OSError:
        out.append(xdg)
    out.append(Path.cwd() / ".claude" / "settings.json")
    out.append(Path.cwd() / ".claude" / "settings.local.json")
    return out


def load_claude_settings() -> dict[str, Any]:
    """与 Claude Code 等效的合并后 settings 字典（纯读）。"""
    return merged_claude_code_settings()


def merged_claude_code_settings() -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for p in _settings_json_paths_in_merge_order():
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            merged = _deep_merge(merged, data)
    return merged


def _resolve_claude_picker_model(raw: str, env: dict[str, Any], merged: dict[str, Any]) -> str:
    """把 Claude Code 里可能出现的别名（sonnet 等）解析成发给 API 的 model 字符串。"""
    m = (raw or "").strip()
    if not m:
        return "claude-sonnet-4-5"
    key = m.lower()
    # env 中 ANTHROPIC_DEFAULT_* 可覆盖 /model 的 sonnet|opus|haiku
    alias_to_env: dict[str, str] = {
        "sonnet": "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "opus": "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "haiku": "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    }
    if key in alias_to_env:
        ev = (env.get(alias_to_env[key]) or "").strip()
        if ev:
            return _resolve_claude_picker_model(ev, env, merged) if ev.lower() in alias_to_env else ev
    # 已是完整 id
    if "claude-" in m or m.startswith("arn:") or m.startswith("vertex"):
        return m
    if key in ("sonnet", "opus", "haiku"):
        fallbacks: dict[str, str] = {
            "sonnet": "claude-sonnet-4-5",
            "opus": "claude-opus-4-5",
            "haiku": "claude-haiku-4-5",
        }
        return fallbacks.get(key, m)
    return m


def find_claude_settings() -> Optional[Path]:
    for p in _settings_json_paths_in_merge_order():
        if p.is_file():
            return p
    return None


def anthropic_key_from_merged_settings() -> Optional[str]:
    """从合并后的 settings（`env` 与顶层 `api_key` / `auth_token`）取 Anthropic 凭据。无则 None。"""
    merged = merged_claude_code_settings()
    if not merged:
        return None
    env: dict[str, Any] = dict(merged.get("env") or {})
    if not isinstance(env, dict):
        env = {}
    s = (
        str(env.get("ANTHROPIC_API_KEY") or "")
        or str(env.get("ANTHROPIC_AUTH_TOKEN") or "")
        or str(merged.get("api_key") or "")
        or str(merged.get("auth_token") or "")
    ).strip()
    return s or None


def anthropic_base_url_from_merged_settings() -> Optional[str]:
    merged = merged_claude_code_settings()
    if not merged:
        return None
    env: dict[str, Any] = dict(merged.get("env") or {})
    if not isinstance(env, dict):
        env = {}
    b = str(env.get("ANTHROPIC_BASE_URL") or merged.get("base_url") or "").strip()
    return b or None


def openai_key_from_merged_settings() -> Optional[str]:
    """合并 settings 中 `env.OPENAI_API_KEY`（Claude Code 有时与 OpenAI 共用配置）。"""
    merged = merged_claude_code_settings()
    if not merged:
        return None
    env: dict[str, Any] = dict(merged.get("env") or {})
    if not isinstance(env, dict):
        env = {}
    s = str(env.get("OPENAI_API_KEY") or "").strip()
    return s or None


def openai_base_url_from_merged_settings() -> Optional[str]:
    merged = merged_claude_code_settings()
    if not merged:
        return None
    env: dict[str, Any] = dict(merged.get("env") or {})
    if not isinstance(env, dict):
        env = {}
    b = str(env.get("OPENAI_BASE_URL") or "").strip()
    return b or None


def model_from_claude_settings() -> Optional[ModelConfig]:
    """从与 Claude Code 合并后的 effective settings 构造 `default` 模型配置。"""
    merged = merged_claude_code_settings()
    if not merged:
        return None

    env: dict[str, Any] = dict(merged.get("env") or {})
    if not isinstance(env, dict):
        env = {}

    api_key = anthropic_key_from_merged_settings()

    base_url = anthropic_base_url_from_merged_settings()
    if base_url and not (base_url.strip()):
        base_url = None

    # 与 Claude Code: env.ANTHROPIC_MODEL 优先，否则顶层 `model`（/model 选择会落在其一）
    raw_model = (
        str(env.get("ANTHROPIC_MODEL") or "").strip()
        or str(merged.get("model") or "").strip()
    )
    if not raw_model and (api_key or base_url):
        raw_model = "claude-sonnet-4-5"
    model = _resolve_claude_picker_model(raw_model, env, merged)

    overrides = merged.get("modelOverrides")
    if isinstance(overrides, dict) and model in overrides and overrides[model]:
        model = str(overrides[model])

    if not api_key and not base_url:
        return None

    # 非官方域名时若仍把 provider 设成 openai_compatible，会用工 OpenAI 客户端发 claude-*
    # 模型名，多数网关 / 官方 OpenAI 会返回 404。Anthropic 企业/代理端点应继续走 Anthropic 客户端 + base_url。
    provider = _provider_for_custom_base_url(base_url, model)

    return ModelConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
    )


def _provider_for_custom_base_url(base_url: Optional[str], model: str) -> str:
    """`ANTHROPIC_BASE_URL` 非 api.anthropic.com 时，区分 Anthropic 兼容端点与 OpenAI 兼容聚合。"""
    if not base_url or "anthropic.com" in base_url:
        return "anthropic"
    m = (model or "").strip().lower()
    if m.startswith("claude-") or m.startswith("arn:") or m.startswith("vertex"):
        return "anthropic"
    return "openai_compatible"


def default_model_config(*, merge_claude_code_settings: bool = True) -> ModelConfig:
    """与 Claude Code 一致：优先合并 settings / Anthropic 环境变量。不从 shell 的 OPENAI_API_KEY
    自动充当默认模型，避免 conda 里挂着的 OpenAI 抢答、把 claude 名错配到 OpenAI 端点。
    需要 OpenAI 时在 YAML 的 `models` 中显式写 `provider: openai`。

    merge_claude_code_settings=False 时跳过读 ~/.claude，仅用环境变量与占位默认。
    """
    if merge_claude_code_settings:
        m = model_from_claude_settings()
        if m:
            return m

    if os.getenv("ANTHROPIC_API_KEY"):
        base_url = os.getenv("ANTHROPIC_BASE_URL")
        m = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
        return ModelConfig(
            provider=_provider_for_custom_base_url(base_url, m),
            model=m,
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            base_url=base_url,
        )
    if os.getenv("ANTHROPIC_AUTH_TOKEN"):
        base_url = os.getenv("ANTHROPIC_BASE_URL")
        m = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
        return ModelConfig(
            provider=_provider_for_custom_base_url(base_url, m),
            model=m,
            api_key=os.getenv("ANTHROPIC_AUTH_TOKEN"),
            base_url=base_url,
        )

    return ModelConfig(provider="anthropic", model="claude-sonnet-4-5")


def apply_claude_code_to_config(cfg: "AppConfig") -> None:
    """用 Claude Code 合并结果覆盖 `models['default']`；再为缺凭据的项补全。

    `cfg.use_claude_code_settings` 为 False 时不读 settings 文件，仅靠 YAML 与环境变量。

    若 YAML 已写 `base_url`（如讯飞/自建 OpenAI 兼容网关），不覆盖 default，避免与 ~/.claude 里
    的 ANTHROPIC_MODEL 等冲突导致 404。
    """
    merge = cfg.use_claude_code_settings
    m = model_from_claude_settings() if merge else None
    cur = cfg.models.get("default")
    if merge and m is not None:
        if cur is not None and (cur.base_url or "").strip():
            pass
        else:
            cfg.models["default"] = m
    for k, mod in list(cfg.models.items()):
        if mod.resolved_api_key(merge) or mod.resolved_base_url(merge):
            continue
        cfg.models[k] = default_model_config(merge_claude_code_settings=merge)
