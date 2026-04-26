"""环境与配置诊断。"""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from pathlib import Path

from .config_models import AppConfig
from .settings_loader import (
    apply_claude_code_to_config,
    claude_config_dir,
    default_model_config,
    find_claude_settings,
    model_from_claude_settings,
    merged_claude_code_settings,
)


@dataclass
class DoctorCheck:
    label: str
    ok: bool
    detail: str


def _module_check(module_name: str) -> DoctorCheck:
    try:
        mod = importlib.import_module(module_name)
        return DoctorCheck(module_name, True, getattr(mod, "__file__", "(built-in)"))
    except Exception as exc:
        return DoctorCheck(module_name, False, str(exc))


def _config_check(path: Path | None) -> tuple[DoctorCheck, AppConfig | None]:
    if path is None:
        return DoctorCheck("config", True, "未指定 --config，可使用默认模板启动"), None
    if not path.exists():
        return DoctorCheck("config", False, f"配置文件不存在: {path}"), None
    try:
        cfg = AppConfig.from_yaml(path)
        cc = "on" if cfg.use_claude_code_settings else "off"
        return DoctorCheck(
            "config",
            True,
            f"{path} | agents={len(cfg.agents)} | workflow={cfg.workflow.mode} | claude_settings_merge={cc}",
        ), cfg
    except Exception as exc:
        return DoctorCheck("config", False, f"{path} | {exc}"), None


def _claude_settings_check() -> DoctorCheck:
    data = merged_claude_code_settings()
    m = model_from_claude_settings()
    env = data.get("env") or {}
    raw = env.get("ANTHROPIC_MODEL") or data.get("model")
    res = f"{m.model} ({m.provider})" if m else "(与 Claude 合并后无 api/base_url, 可依赖进程 env)"
    first = find_claude_settings()
    has_file = first is not None
    has_key = bool(m) or bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))
    d = f"config_dir={claude_config_dir()}"
    if first:
        d += f" | 首个匹配文件: {first}"
    if has_file:
        d += f" | 顶层/ env model={raw!r} | 解析为 {res}"
    else:
        d += f" | 未找到分层的 settings.json，解析为 {res}"
    return DoctorCheck("claude_settings", has_key, d)


def _env_check() -> list[DoctorCheck]:
    items = [
        ("ANTHROPIC_API_KEY", bool(os.getenv("ANTHROPIC_API_KEY"))),
        ("ANTHROPIC_AUTH_TOKEN", bool(os.getenv("ANTHROPIC_AUTH_TOKEN"))),
        ("OPENAI_API_KEY", bool(os.getenv("OPENAI_API_KEY"))),
        ("OPENAI_BASE_URL", bool(os.getenv("OPENAI_BASE_URL"))),
    ]
    return [
        DoctorCheck(name, ok, "set" if ok else "missing")
        for name, ok in items
    ]


def _model_checks(cfg: AppConfig | None) -> list[DoctorCheck]:
    if cfg is None:
        return []
    checks: list[DoctorCheck] = []
    merge = cfg.use_claude_code_settings
    fallback_model = default_model_config(merge_claude_code_settings=merge)
    for key, model in cfg.models.items():
        has_auth = bool(
            model.resolved_api_key(merge) or model.resolved_base_url(merge)
        )
        can_fallback = not has_auth and bool(
            fallback_model.resolved_api_key(merge) or fallback_model.resolved_base_url(merge)
        )
        detail = f"{model.provider}:{model.model} | api/base={'yes' if has_auth else 'no'}"
        if can_fallback:
            detail += f" | runtime_fallback={fallback_model.provider}:{fallback_model.model}"
        checks.append(
            DoctorCheck(
                f"model:{key}",
                has_auth or model.provider == "openai_compatible" or can_fallback,
                detail,
            )
        )
    if cfg.default_model not in cfg.models:
        checks.append(DoctorCheck("default_model", False, f"`{cfg.default_model}` 不在 models 中"))
    else:
        checks.append(DoctorCheck("default_model", True, cfg.default_model))
    return checks


def run_doctor(config_path: str | None = None) -> list[DoctorCheck]:
    path = Path(config_path) if config_path else None
    config_check, cfg = _config_check(path)
    if cfg is not None:
        apply_claude_code_to_config(cfg)
    checks = [
        _module_check("textual"),
        _module_check("pydantic"),
        _module_check("yaml"),
        _module_check("autogen_agentchat"),
        _module_check("autogen_core"),
        _module_check("autogen_ext"),
        _module_check("fastapi"),
        _module_check("uvicorn"),
        _module_check("websockets"),
        config_check,
        _claude_settings_check(),
        *_env_check(),
        *_model_checks(cfg),
    ]
    # Optional deps: don't fail if missing
    for mod in ("claude_agent_sdk",):
        c = _module_check(mod)
        if not c.ok:
            c.detail = f"{mod} (optional) not installed"
            c.ok = True
        checks.append(c)
    return checks


def format_doctor_report(checks: list[DoctorCheck]) -> str:
    lines = ["magent-tui doctor", ""]
    for check in checks:
        prefix = "OK" if check.ok else "ERR"
        lines.append(f"[{prefix}] {check.label:<18} {check.detail}")
    ok_count = sum(1 for item in checks if item.ok)
    lines.extend(["", f"summary: {ok_count}/{len(checks)} checks passed"])
    return "\n".join(lines)
