"""AutoGen 编排层：把 AppConfig 转成一组 AssistantAgent 并运行 GroupChat。

为了让 TUI 在没有安装/没有配置 API 的情况下也能启动演示，本模块在 AutoGen
不可用时会回退到一个 `MockOrchestrator`，按轮次返回模拟回复。
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import AsyncIterator, Callable, Optional

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


def _openai_base_is_default_or_official(base_url: Optional[str]) -> bool:
    """未设 base_url 时 OpenAI 客户端默认连官方；与 claude-* 模型名组合会 404。"""
    b = (base_url or "").strip().lower()
    if not b:
        return True
    return "api.openai.com" in b


def _effective_model_config_for_client(
    model_cfg: ModelConfig, merge_claude_code_settings: bool = True
) -> ModelConfig:
    """把误配成 openai* 的 Anthropic 模型名拉回 Anthropic 协议，避免对 OpenAI 端点发 claude-* 导致 404。

    常见来源：`default_model_config()` 在仅有 OPENAI_API_KEY 时设成 openai，但 YAML/合并里 `model` 仍是 claude-*；
    或历史上写错 provider。带 localhost 的 base_url 视为自建聚合，不自动改，以免破坏 LiteLLM 等 OpenAI 面。
    """
    m = (model_cfg.model or "").strip().lower()
    if not m.startswith("claude-"):
        return model_cfg
    if model_cfg.provider not in ("openai", "openai_compatible"):
        return model_cfg
    bu = (model_cfg.resolved_base_url(merge_claude_code_settings) or "").strip().lower()
    if bu and any(x in bu for x in ("localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal")):
        return model_cfg
    k_from_cfg = (model_cfg.api_key or "").strip()
    if k_from_cfg.startswith("sk-ant"):
        return model_cfg.model_copy(update={"provider": "anthropic", "api_key": k_from_cfg})
    if merge_claude_code_settings:
        from .settings_loader import anthropic_key_from_merged_settings

        auth = (
            anthropic_key_from_merged_settings()
            or os.getenv("ANTHROPIC_API_KEY")
            or os.getenv("ANTHROPIC_AUTH_TOKEN")
            or ""
        ).strip()
    else:
        auth = (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN") or "").strip()
    if auth:
        return model_cfg.model_copy(update={"provider": "anthropic", "api_key": auth})
    return model_cfg


def _build_model_client(
    model_cfg: ModelConfig, merge_claude_code_settings: bool = True
):
    """根据 ModelConfig 构造 autogen model client。延迟导入。"""
    from autogen_ext.models.openai import OpenAIChatCompletionClient  # type: ignore

    model_cfg = _effective_model_config_for_client(
        model_cfg, merge_claude_code_settings=merge_claude_code_settings
    )

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
            resolved_key = model_cfg.resolved_api_key(merge_claude_code_settings)
            resolved_base = model_cfg.resolved_base_url(merge_claude_code_settings)
            if resolved_key:
                kwargs["api_key"] = resolved_key
            if resolved_base:
                kwargs["base_url"] = resolved_base
            if model_cfg.temperature is not None:
                kwargs["temperature"] = model_cfg.temperature
            if model_cfg.max_tokens is not None:
                kwargs["max_tokens"] = model_cfg.max_tokens
            kwargs["model_info"] = _fallback_model_info("anthropic", model_cfg.model)
            return AnthropicChatCompletionClient(**kwargs)
        except Exception as exc:
            raise RuntimeError(f"Anthropic client 初始化失败: {exc}") from exc

    mod = (model_cfg.model or "").strip().lower()
    eff_base_oai = model_cfg.resolved_base_url(merge_claude_code_settings)
    if mod.startswith("claude-") and _openai_base_is_default_or_official(eff_base_oai):
        raise RuntimeError(
            "模型 id 为 claude-*，但当前仍走 OpenAI 官方地址（base_url 为空或含 api.openai.com），"
            "会对错误端点发请求并出现 404。\n"
            "请任选：1) 设置 ANTHROPIC_API_KEY（或 merged Claude settings），并保持 use_claude_code_settings: true；"
            "2) 在 YAML 为 default 显式写 provider: anthropic；"
            "3) 若用讯飞等 OpenAI 兼容网关，请写 provider: openai_compatible、控制台的 base_url 与 modelId，"
            "并设 use_claude_code_settings: false，勿混用 claude 模型名与官方 OpenAI。"
        )

    kwargs: dict = dict(model=model_cfg.model)
    resolved_key = model_cfg.resolved_api_key(merge_claude_code_settings)
    resolved_base = model_cfg.resolved_base_url(merge_claude_code_settings)
    if resolved_key:
        kwargs["api_key"] = resolved_key
    if resolved_base:
        kwargs["base_url"] = resolved_base
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
    def __init__(self, config: AppConfig, event_callback: Optional[Callable] = None):
        self.config = config
        self._workspace_root: Path = config.ensure_workspace()
        self._event_callback = event_callback

    def _build_agents(self):
        from autogen_agentchat.agents import AssistantAgent  # type: ignore

        agents = []
        for a in self.config.agents:
            mc = self.config.get_model_for_agent(a)
            client = _build_model_client(mc, self.config.use_claude_code_settings)
            workspace_path = self._workspace_root / a.resolved_workspace()
            system = (
                f"{a.system_prompt}\n\n"
                f"[你的工作目录]: {workspace_path}\n"
                f"[角色]: {a.role}\n"
            )
            tool_names = "write_text_file / append_text_file / read_text_file / list_workspace_files"
            if "claude_agent" in a.tools:
                tool_names += " / claude_agent"
                system += (
                    "\n[特殊工具]: claude_agent — 当你需要编写、修改、调试实际代码时，"
                    "调用此工具并传入详细实现指令。Claude Agent 会在项目目录中执行代码工程。\n"
                )
            system += (
                f"[可用工具]: {tool_names}\n"
                "所有过程稿、分析稿、代码片段、交付件优先写入你的工作目录。\n"
                "请用中文回复。不需要继续时回复 `TERMINATE`。"
            )
            kwargs = {}
            tools = _build_tools_for_agent(self._workspace_root, a)
            if "claude_agent" in a.tools:
                from .claude_agent import ClaudeAgentTool
                claude_tool = ClaudeAgentTool(
                    cwd=self._workspace_root / a.resolved_workspace(),
                    event_callback=self._event_callback,
                    agent_name=f"{a.name}_ClaudeAgent",
                )
                tools.append(claude_tool.as_function_tool())
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

    @staticmethod
    def _stream_item_to_text(ev: object) -> str | None:
        """把 AutoGen 流事件转 UI 可读文本；用官方 to_text() 覆盖工具/思考/文本/代码执行等。"""
        from autogen_agentchat.messages import (  # type: ignore[import-not-found]
            BaseAgentEvent,
            BaseChatMessage,
            UserInputRequestedEvent,
        )
        if isinstance(ev, UserInputRequestedEvent):
            return None
        ChunkCls = None
        try:
            from autogen_agentchat.messages import (  # type: ignore[import-not-found]
                ModelClientStreamingChunkEvent as ChunkCls,  # noqa: N814
            )
        except Exception:
            ChunkCls = None
        if ChunkCls is not None and isinstance(ev, ChunkCls):
            return None
        if isinstance(ev, (BaseChatMessage, BaseAgentEvent)):
            t = ev.to_text()
            s = t.strip() if t else ""
            return s or None
        return None

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
            client = (
                _build_model_client(mc, self.config.use_claude_code_settings) if mc else None
            )
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

        from autogen_agentchat.base import TaskResult  # type: ignore[import-not-found]

        team = self._build_team(agents)
        stop_reason: str | None = None
        any_user_visible = False
        async for event in team.run_stream(task=task):
            if isinstance(event, TaskResult):
                stop_reason = event.stop_reason
                continue
            text = self._stream_item_to_text(event)
            if not text:
                continue
            any_user_visible = True
            name = getattr(event, "source", None) or ""
            role = next((a.role for a in self.config.agents if a.name == name), "agent")
            yield AgentMessage(agent=name or "system", role=role, content=text)
        if not any_user_visible:
            detail = f" stop_reason={stop_reason!r}" if stop_reason else ""
            yield AgentMessage(
                "system",
                "system",
                "未产生任何可展示输出（流中无 TextMessage/工具结果等）。"
                f"请检查 API Key、网络、额度与 workflow.max_turns。{detail}",
            )
        reason_text = f"（{stop_reason}）" if stop_reason else ""
        yield AgentMessage("system", "system", f"协作结束{reason_text}。", final=True)

    async def _run_pipeline(self, agents, task: str) -> AsyncIterator[AgentMessage]:
        running_context = task
        predecessor_summaries: list[str] = []
        for agent in agents:
            predecessor_info = ""
            if predecessor_summaries:
                predecessor_info = (
                    "\n\n## 前序阶段产出\n\n"
                    + "\n".join(predecessor_summaries)
                    + "\n\n你可以用 read_text_file / list_workspace_files 工具读取前序 Agent 工作目录中的文件获取详细信息。"
                )
            prompt = (
                f"{running_context}\n\n"
                "你处于 pipeline 协作模式，请只完成你当前阶段，将产出写入你的工作目录。"
                f"{predecessor_info}"
            )
            last_msg_content = ""
            async for msg in self._run_single(agent, prompt):
                yield msg
                if msg.final and msg.content:
                    last_msg_content = msg.content
            if last_msg_content:
                running_context = f"{running_context}\n\n[{agent.name} 输出]\n{last_msg_content}"
            # 收集此 agent 的产物文件清单供后续 agent 参考
            agent_ws = self._workspace_root / self._agent_workspace_name(agent)
            if agent_ws.exists():
                files = sorted(
                    str(p.relative_to(agent_ws)) for p in agent_ws.rglob("*") if p.is_file()
                )
                if files:
                    predecessor_summaries.append(
                        f"### {agent.name} 工作目录 ({agent_ws.name}/)\n"
                        + "\n".join(f"- `{f}`" for f in files)
                    )
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

    def _agent_workspace_name(self, agent) -> str:
        cfg_agent = next((a for a in self.config.agents if a.name == agent.name), None)
        return cfg_agent.resolved_workspace() if cfg_agent else agent.name

    async def _run_single(self, agent, task: str) -> AsyncIterator[AgentMessage]:
        """流式跑单 agent：把工具调用、思考、token chunk 都推给 UI，pipeline 的每一阶段也走这条。"""
        from autogen_agentchat.base import TaskResult  # type: ignore[import-not-found]

        cur_role = next((a.role for a in self.config.agents if a.name == agent.name), "agent")
        any_emitted = False
        last_text: str | None = None
        async for ev in agent.run_stream(task=task):
            if isinstance(ev, TaskResult):
                continue
            text = self._stream_item_to_text(ev)
            if not text:
                continue
            any_emitted = True
            last_text = text
            yield AgentMessage(agent=agent.name, role=cur_role, content=text)
        if not any_emitted:
            yield AgentMessage(
                agent=agent.name,
                role=cur_role,
                content="（无输出：检查模型 key/网络/额度。）",
                final=True,
            )
        else:
            yield AgentMessage(
                agent=agent.name,
                role=cur_role,
                content=last_text or "",
                final=True,
            )

# --------------------------- Factory ---------------------------

def build_orchestrator(config: AppConfig, event_callback: Optional[Callable] = None) -> OrchestratorBase:
    """根据环境选择真实或 mock 编排器。"""
    try:
        import autogen_agentchat  # noqa: F401
        import autogen_ext  # noqa: F401
    except Exception as e:
        return MockOrchestrator(config, reason=f"AutoGen 未安装 ({e})")

    merge = config.use_claude_code_settings
    for a in config.agents:
        mc = _effective_model_config_for_client(config.get_model_for_agent(a), merge)
        if mc.provider == "anthropic":
            try:
                from autogen_ext.models.anthropic import AnthropicChatCompletionClient  # type: ignore # noqa: F401
            except Exception as e:
                return MockOrchestrator(
                    config,
                    reason=f"Agent `{a.name}` 使用 anthropic 但缺少依赖 ({e})",
                )
        if not mc.resolved_api_key(merge) and mc.provider != "openai_compatible":
            return MockOrchestrator(
                config,
                reason=f"Agent `{a.name}` 的模型 `{mc.model}` 未配置 API Key",
            )

    try:
        return AutoGenOrchestrator(config, event_callback=event_callback)
    except Exception as e:
        return MockOrchestrator(config, reason=f"初始化 AutoGen 失败: {e}")
