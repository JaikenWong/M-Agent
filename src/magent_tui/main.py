"""CLI 入口：magent-tui [run|init|templates]。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from .config_models import AgentConfig, AppConfig, ModelConfig, WorkflowConfig
from .doctor import format_doctor_report, run_doctor
from .settings_loader import default_model_config, find_claude_settings
from .templates import describe_templates, instantiate_template, template_names


def _build_default_config(template: Optional[str] = None) -> AppConfig:
    model = default_model_config()
    agents: list[AgentConfig] = instantiate_template(template) if template else []
    return AppConfig(
        project_name="m-agent",
        workspace_root="deliverables",
        default_model="default",
        models={"default": model},
        agents=agents,
        workflow=WorkflowConfig(mode="round_robin", max_turns=12),
    )


def cmd_templates(_: argparse.Namespace) -> int:
    print("可用模板：\n")
    for name, desc in describe_templates():
        print(f"  • {name:<18} {desc}")
    print("\n用法: magent-tui init --template <name> -o configs/<name>.yaml")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    if args.template and args.template not in template_names():
        print(f"❌ 未知模板: {args.template}")
        print(f"可用: {', '.join(template_names())}")
        return 2
    cfg = _build_default_config(args.template)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    cfg.to_yaml(out)
    print(f"✓ 已生成配置: {out}")
    if find_claude_settings():
        print(f"  模型从 Claude Code settings 读取 ({find_claude_settings()})")
    print(f"  启动: magent-tui run --config {out}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    if args.config:
        path = Path(args.config)
        if not path.exists():
            print(f"❌ 配置文件不存在: {path}")
            return 2
        cfg = AppConfig.from_yaml(path)
    else:
        cfg = _build_default_config("product_sprint")
        path = None
        print("ℹ 未指定 --config，使用内置 product_sprint 模板启动。")

    for key, m in list(cfg.models.items()):
        if not m.resolved_api_key() and not m.base_url:
            fallback = default_model_config()
            cfg.models[key] = fallback

    from .app import run_app

    run_app(cfg, path)
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    report = format_doctor_report(run_doctor(args.config))
    print(report)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("magent-tui", description="多智能体协作 TUI")
    sub = p.add_subparsers(dest="cmd")

    p_run = sub.add_parser("run", help="启动 TUI")
    p_run.add_argument("-c", "--config", help="YAML 配置路径")
    p_run.set_defaults(func=cmd_run)

    p_init = sub.add_parser("init", help="生成默认配置 YAML")
    p_init.add_argument("-t", "--template", help="使用的模板名")
    p_init.add_argument("-o", "--output", default="configs/default.yaml", help="输出路径")
    p_init.set_defaults(func=cmd_init)

    p_tpl = sub.add_parser("templates", help="列出所有内置模板")
    p_tpl.set_defaults(func=cmd_templates)

    p_doctor = sub.add_parser("doctor", help="检查依赖、配置与模型环境")
    p_doctor.add_argument("-c", "--config", help="YAML 配置路径")
    p_doctor.set_defaults(func=cmd_doctor)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        return cmd_run(argparse.Namespace(config=None))
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
