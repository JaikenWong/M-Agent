"""AutoGen 编排层：把 AppConfig 转成一组 AssistantAgent 并运行 GroupChat。

为了让 TUI 在没有安装/没有配置 API 的情况下也能启动演示，本模块在 AutoGen
不可用时会回退到一个 `MockOrchestrator`，按轮次返回模拟回复。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Optional

from .config_models import AgentConfig, AppConfig, ModelConfig
from .workspace_tools import WorkspaceToolset


@dataclass
class AgentMessage:
    agent: str
    role: str
    content: str
    final: bool = False


class OrchestratorBase:
    async def run(self, task: str) -> AsyncIterator[AgentMessage]:  # pragma: no cover
        raise NotImplementedError
        yield  # type: ignore[unreachable]


def _missing_required_artifacts(config: AppConfig, workspace_root: Path, agent_name: str) -> list[str]:
    required = config.workflow.required_artifacts.get(agent_name, [])
    if not required:
        return []
    workspace_name = next((a.resolved_workspace() for a in config.agents if a.name == agent_name), agent_name)
    workspace = workspace_root / workspace_name
    return [name for name in required if not (workspace / name).exists()]


# --------------------------- Mock ---------------------------

class MockOrchestrator(OrchestratorBase):
    """无依赖的演示编排器：按 round_robin 给每个 agent 生成占位回复。"""

    def __init__(self, config: AppConfig, reason: str = ""):
        self.config = config
        self.reason = reason
        self._workspace_root = self.config.ensure_workspace()

    async def run(self, task: str) -> AsyncIterator[AgentMessage]:
        agents = self.config.agents
        if not agents:
            yield AgentMessage("system", "system", "当前没有 Agent，请先配置。", final=True)
            return
        if self.reason:
            yield AgentMessage("system", "system", f"⚠ 运行在演示模式：{self.reason}")
        if self.config.workflow.mode == "pipeline":
            turns = len(agents)
        else:
            turns = min(self.config.workflow.max_turns, len(agents))
        for i in range(turns):
            a = agents[i % len(agents)]
            toolset = WorkspaceToolset.for_agent(
                self.config.ensure_workspace(),
                a.resolved_workspace(),
                a.name,
            )
            output_path = f"mock_round_{i + 1}.md"
            toolset.write_text_file(
                output_path,
                (
                    f"# {a.name}\n\n"
                    f"- role: {a.role}\n"
                    f"- task: {task}\n"
                    f"- mode: mock\n"
                ),
            )
            await asyncio.sleep(0.3)
            yield AgentMessage(
                agent=a.name,
                role=a.role,
                content=(
                    f"【{a.role}·{a.name}】\n"
                    f"收到任务：{task}\n"
                    f"(演示模式输出) 已写入 `{a.resolved_workspace()}/{output_path}`。"
                ),
            )
            missing = _missing_required_artifacts(self.config, self._workspace_root, a.name)
            if missing:
                yield AgentMessage(
                    "system",
                    "system",
                    f"❌ pipeline 门禁失败：`{a.name}` 缺失产物 {', '.join(missing)}",
                    final=True,
                )
                return
        yield AgentMessage("system", "system", "协作结束（演示模式）。", final=True)


# --------------------------- AutoGen ---------------------------

def _build_model_client(model_cfg: ModelConfig):
    """根据 ModelConfig 构造 autogen model client。延迟导入。"""
    from autogen_ext.models.openai import OpenAIChatCompletionClient  # type: ignore

    def _fallback_model_info(provider: str, model: str) -> dict:
        base = {
            "vision": False,
            "function_calling": True,
            "json_output": True,
            "family": model,
            "structured_output": True,
            "multiple_system_messages": provider != "anthropic",
        }
        custom = model_cfg.extra.get("model_info")
        if isinstance(custom, dict):
            base.update(custom)
        return base

    if model_cfg.provider == "anthropic":
        try:
            from autogen_ext.models.anthropic import AnthropicChatCompletionClient  # type: ignore

            kwargs = dict(model=model_cfg.model)
            if model_cfg.api_key:
                kwargs["api_key"] = model_cfg.api_key
            if model_cfg.base_url:
                kwargs["base_url"] = model_cfg.base_url
            if model_cfg.temperature is not None:
                kwargs["temperature"] = model_cfg.temperature
            if model_cfg.max_tokens is not None:
                kwargs["max_tokens"] = model_cfg.max_tokens
            kwargs["model_info"] = _fallback_model_info("anthropic", model_cfg.model)
            return AnthropicChatCompletionClient(**kwargs)
        except Exception as exc:
            raise RuntimeError(f"Anthropic client 初始化失败: {exc}") from exc

    kwargs: dict = dict(model=model_cfg.model)
    if model_cfg.api_key:
        kwargs["api_key"] = model_cfg.api_key
    if model_cfg.base_url:
        kwargs["base_url"] = model_cfg.base_url
    if model_cfg.temperature is not None:
        kwargs["temperature"] = model_cfg.temperature
    if model_cfg.max_tokens is not None:
        kwargs["max_tokens"] = model_cfg.max_tokens
    kwargs["model_info"] = _fallback_model_info(model_cfg.provider, model_cfg.model)
    return OpenAIChatCompletionClient(**kwargs)


def _build_tools_for_agent(workspace_root: Path, agent: AgentConfig):
    from autogen_core.tools import FunctionTool  # type: ignore

    toolset = WorkspaceToolset.for_agent(workspace_root, agent.resolved_workspace(), agent.name)
    ws = toolset.agent_workspace

    def _write_text_file(path: str, content: str) -> str:
        target = (ws / Path(path.strip() or ".")).resolve()
        try:
            target.relative_to(ws)
        except ValueError as exc:
            raise ValueError("路径必须位于当前 Agent 工作目录内") from exc
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"已写入 {target}"

    def _append_text_file(path: str, content: str) -> str:
        target = (ws / Path(path.strip() or ".")).resolve()
        try:
            target.relative_to(ws)
        except ValueError as exc:
            raise ValueError("路径必须位于当前 Agent 工作目录内") from exc
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(content)
        return f"已追加 {target}"

    def _read_text_file(path: str) -> str:
        target = (ws / Path(path.strip() or ".")).resolve()
        try:
            target.relative_to(ws)
        except ValueError as exc:
            raise ValueError("路径必须位于当前 Agent 工作目录内") from exc
        return target.read_text(encoding="utf-8")

    def _list_workspace_files(path: str = ".") -> str:
        target = (ws / Path(path.strip() or ".")).resolve()
        try:
            target.relative_to(ws)
        except ValueError as exc:
            raise ValueError("路径必须位于当前 Agent 工作目录内") from exc
        if target.is_file():
            return str(target.relative_to(ws))
        if not target.exists():
            return "(empty)"
        files = sorted(
            str(item.relative_to(ws)) + ("/" if item.is_dir() else "")
            for item in target.rglob("*")
        )
        return "\n".join(files) if files else "(empty)"

    return [
        FunctionTool(_write_text_file, name="write_text_file", description="将文本写入当前 Agent 工作目录内的文件，会覆盖已有内容。"),
        FunctionTool(_append_text_file, name="append_text_file", description="向当前 Agent 工作目录内的文件追加文本。"),
        FunctionTool(_read_text_file, name="read_text_file", description="读取当前 Agent 工作目录内的 UTF-8 文本文件。"),
        FunctionTool(_list_workspace_files, name="list_workspace_files", description="列出当前 Agent 工作目录下的文件和目录。"),
    ]


class AutoGenOrchestrator(OrchestratorBase):
    def __init__(self, config: AppConfig):
        self.config = config
        self._workspace_root: Path = config.ensure_workspace()

    def _build_agents(self):
        from autogen_agentchat.agents import AssistantAgent  # type: ignore

        agents = []
        for a in self.config.agents:
            mc = self.config.get_model_for_agent(a)
            client = _build_model_client(mc)
            workspace_path = self._workspace_root / a.resolved_workspace()
            system = (
                f"{a.system_prompt}\n\n"
                f"[你的工作目录]: {workspace_path}\n"
                f"[角色]: {a.role}\n"
                "[可用工具]: write_text_file / append_text_file / read_text_file / list_workspace_files\n"
                "所有过程稿、分析稿、代码片段、交付件优先写入你的工作目录。\n"
                "请用中文回复。不需要继续时回复 `TERMINATE`。"
            )
            kwargs = {}
            tools = _build_tools_for_agent(self._workspace_root, a)
            if tools:
                kwargs["tools"] = tools
            agents.append(
                AssistantAgent(
                    name=a.name,
                    model_client=client,
                    system_message=system,
                    description=a.description or a.role,
                    **kwargs,
                )
            )
        return agents

    def _build_team(self, agents):
        from autogen_agentchat.teams import RoundRobinGroupChat, SelectorGroupChat  # type: ignore
        from autogen_agentchat.conditions import (  # type: ignore
            MaxMessageTermination,
            TextMentionTermination,
        )

        term = MaxMessageTermination(self.config.workflow.max_turns)
        for kw in self.config.workflow.termination_keywords:
            term = term | TextMentionTermination(kw)

        if self.config.workflow.mode == "selector":
            mc = next(iter(self.config.models.values()), None)
            client = _build_model_client(mc) if mc else None
            selector_kwargs: dict = dict(
                participants=agents,
                model_client=client,
                termination_condition=term,
            )
            if self.config.workflow.selector_prompt:
                selector_kwargs["selector_prompt"] = self.config.workflow.selector_prompt
            return SelectorGroupChat(**selector_kwargs)
        return RoundRobinGroupChat(participants=agents, termination_condition=term)

    async def run(self, task: str) -> AsyncIterator[AgentMessage]:
        agents = self._build_agents()
        if self.config.workflow.mode == "single" and agents:
            async for m in self._run_single(agents[0], task):
                yield m
            return
        if self.config.workflow.mode == "pipeline":
            async for m in self._run_pipeline(agents, task):
                yield m
            return

        team = self._build_team(agents)
        stop_reason = None
        async for event in team.run_stream(task=task):
            if hasattr(event, "messages") and hasattr(event, "stop_reason"):
                stop_reason = getattr(event, "stop_reason", None)
                continue
            name = getattr(event, "source", None) or ""
            content = getattr(event, "content", None)
            if content is None:
                continue
            if not isinstance(content, str):
                content = str(content)
            role = next((a.role for a in self.config.agents if a.name == name), "agent")
            yield AgentMessage(agent=name or "system", role=role, content=content)
        reason_text = f"（{stop_reason}）" if stop_reason else ""
        yield AgentMessage("system", "system", f"协作结束{reason_text}。", final=True)

    async def _run_pipeline(self, agents, task: str) -> AsyncIterator[AgentMessage]:
        running_context = task
        for agent in agents:
            prompt = (
                f"{running_context}\n\n"
                "你处于 pipeline 协作模式，请只完成你当前阶段，并尽量写入工作目录。"
            )
            async for msg in self._run_single(agent, prompt):
                yield msg
                running_context = f"{running_context}\n\n[{agent.name} 输出]\n{msg.content}"
            missing = _missing_required_artifacts(self.config, self._workspace_root, agent.name)
            if missing:
                yield AgentMessage(
                    "system",
                    "system",
                    f"❌ pipeline 门禁失败：`{agent.name}` 缺失产物 {', '.join(missing)}",
                    final=True,
                )
                return
        yield AgentMessage("system", "system", "协作结束（pipeline）。", final=True)

    async def _run_single(self, agent, task: str) -> AsyncIterator[AgentMessage]:
        from autogen_agentchat.messages import TextMessage  # type: ignore
        from autogen_core import CancellationToken  # type: ignore

        res = await agent.on_messages(
            [TextMessage(content=task, source="user")],
            cancellation_token=CancellationToken(),
        )
        msg = res.chat_message
        yield AgentMessage(
            agent=agent.name,
            role="agent",
            content=getattr(msg, "content", str(msg)),
            final=True,
        )

# --------------------------- Factory ---------------------------

def build_orchestrator(config: AppConfig) -> OrchestratorBase:
    """根据环境选择真实或 mock 编排器。"""
    try:
        import autogen_agentchat  # noqa: F401
        import autogen_ext  # noqa: F401
    except Exception as e:
        return MockOrchestrator(config, reason=f"AutoGen 未安装 ({e})")

    for a in config.agents:
        mc = config.get_model_for_agent(a)
        if mc.provider == "anthropic":
            try:
                from autogen_ext.models.anthropic import AnthropicChatCompletionClient  # type: ignore # noqa: F401
            except Exception as e:
                return MockOrchestrator(
                    config,
                    reason=f"Agent `{a.name}` 使用 anthropic 但缺少依赖 ({e})",
                )
        if not mc.resolved_api_key() and mc.provider != "openai_compatible":
            return MockOrchestrator(
                config,
                reason=f"Agent `{a.name}` 的模型 `{mc.model}` 未配置 API Key",
            )

    try:
        return AutoGenOrchestrator(config)
    except Exception as e:
        return MockOrchestrator(config, reason=f"初始化 AutoGen 失败: {e}")
