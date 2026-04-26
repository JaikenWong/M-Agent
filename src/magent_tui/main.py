"""CLI 入口：magent-tui [run|init|templates]。"""

from __future__ import annotations

import argparse
import asyncio
import signal
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
    workflow = WorkflowConfig(mode="round_robin", max_turns=12)
    project_name = "m-agent"
    if template == "dev_team_oob":
        project_name = "dev-team-oob"
        workflow = WorkflowConfig(
            mode="pipeline",
            max_turns=24,
            required_artifacts={
                "PM": ["PRD.md"],
                "TechLead": ["architecture.md"],
                "Backend": ["backend_plan.md"],
                "Frontend": ["frontend_plan.md"],
                "QA": ["test_plan.md"],
                "DevOps": ["release_plan.md"],
                "TechWriter": ["README.md"],
            },
        )
    return AppConfig(
        project_name=project_name,
        workspace_root="deliverables",
        default_model="default",
        models={"default": model},
        agents=agents,
        workflow=workflow,
    )


def _load_config(config_path: Optional[str], template: Optional[str] = None) -> tuple[AppConfig, Optional[Path]]:
    if config_path:
        path = Path(config_path)
        if not path.exists():
            print(f"❌ 配置文件不存在: {path}")
            sys.exit(2)
        cfg = AppConfig.from_yaml(path)
        return cfg, path
    tpl = template or "dev_team_oob"
    cfg = _build_default_config(tpl)
    return cfg, None


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


def _fix_model_fallback(cfg: AppConfig) -> None:
    for key, m in list(cfg.models.items()):
        if not m.resolved_api_key() and not m.base_url:
            cfg.models[key] = default_model_config()


async def _headless_run(cfg: AppConfig, task: str) -> int:
    """无头模式：终端流式输出，不启动 TUI。"""
    from .run_service import RunService

    svc = RunService(cfg)
    cancel_event = asyncio.Event()

    def _sig_handler() -> None:
        cancel_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _sig_handler)

    print(f"\n🚀 任务: {task}\n   模式: {cfg.workflow.mode} | Agent 数: {len(cfg.agents)}\n")
    try:
        async for event in svc.run(task):
            if cancel_event.is_set():
                print("\n⚠ 已取消")
                break
            if event.event_type == "agent_message" and event.agent and event.agent != "system":
                role_tag = f"({event.role})" if event.role else ""
                print(f"\n● {event.agent} {role_tag}:")
                print(f"  {event.content}")
            elif event.event_type == "agent_message" and event.agent == "system":
                print(f"\n[System] {event.content}")
            elif event.event_type == "run_completed":
                print("\n✓ 完成")
            elif event.event_type == "run_failed":
                print(f"\n✗ 失败: {event.content}")
                return 1
    except KeyboardInterrupt:
        print("\n⚠ 已取消")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    cfg, path = _load_config(args.config, getattr(args, "template", None))
    _fix_model_fallback(cfg)

    task = getattr(args, "task", None)
    if task:
        if not cfg.agents:
            print("❌ 没有 Agent，请通过 --template 指定模板或 --config 指定配置。")
            return 2
        return asyncio.run(_headless_run(cfg, task))

    from .tab_app import run_app
    run_app(cfg, path)
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    report = format_doctor_report(run_doctor(args.config))
    print(report)
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    cfg, path = _load_config(args.config, getattr(args, "template", None))
    _fix_model_fallback(cfg)

    import uvicorn
    from .server import create_app
    app = create_app(cfg)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("magent-tui", description="多智能体协作 TUI")
    sub = p.add_subparsers(dest="cmd")

    p_run = sub.add_parser("run", help="启动 TUI 或无头执行任务")
    p_run.add_argument("-c", "--config", help="YAML 配置路径")
    p_run.add_argument("-t", "--task", help="直接执行任务（无头模式，不启动 TUI）")
    p_run.add_argument("--template", help="使用的模板名（无 --config 时生效）")
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

    p_serve = sub.add_parser("serve", help="启动 FastAPI 服务器")
    p_serve.add_argument("--host", default="127.0.0.1", help="监听地址")
    p_serve.add_argument("--port", type=int, default=8765, help="监听端口")
    p_serve.add_argument("-c", "--config", help="YAML 配置路径")
    p_serve.add_argument("--template", help="使用的模板名")
    p_serve.set_defaults(func=cmd_serve)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        return cmd_run(argparse.Namespace(config=None))
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
