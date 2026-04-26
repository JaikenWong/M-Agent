"""ClaudeAgentTool: 包装 Claude Agent SDK 供 AutoGen agent 调用。

当 AutoGen agent 需要执行代码工程（读/写/编辑文件、运行命令）时，
调用 claude_agent(prompt) 工具，由 Claude Agent SDK 在目标项目目录执行。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .orchestrator import AgentMessage


@dataclass
class ClaudeAgentResult:
    output: str
    files_modified: list[str] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


class ClaudeAgentTool:
    def __init__(
        self,
        cwd: str | Path,
        event_callback: Optional[Callable[[AgentMessage], None]] = None,
        permission_mode: str = "acceptEdits",
        max_turns: int = 50,
        agent_name: str = "ClaudeAgent",
    ):
        self.cwd = Path(cwd).resolve()
        self.permission_mode = permission_mode
        self.max_turns = max_turns
        self.agent_name = agent_name
        self._event_callback = event_callback
        self._sdk_available: Optional[bool] = None

    def _check_sdk(self) -> bool:
        if self._sdk_available is None:
            try:
                from claude_agent_sdk import query  # type: ignore[import-not-found] # noqa: F401
                self._sdk_available = True
            except ImportError:
                self._sdk_available = False
        return self._sdk_available

    def _emit(self, msg: AgentMessage) -> None:
        if self._event_callback:
            self._event_callback(msg)

    async def run(self, prompt: str) -> ClaudeAgentResult:
        if not self._check_sdk():
            return ClaudeAgentResult(
                output="Claude Agent SDK 未安装。安装: pip install claude-agent-sdk",
                success=False,
                error="sdk_not_available",
            )

        self._emit(AgentMessage(
            agent=self.agent_name,
            role="code_engineer",
            content=f"Claude Agent 启动于 `{self.cwd}`...\n任务: {prompt[:200]}",
        ))

        try:
            from claude_agent_sdk import query  # type: ignore[import-not-found]

            collected: list[str] = []
            files_modified: list[str] = []

            async for event in query(
                prompt=prompt,
                cwd=str(self.cwd),
                permission_mode=self.permission_mode,
                maxTurns=self.max_turns,
                tools=["Read", "Write", "Edit", "Bash", "Grep", "Glob"],
            ):
                # Handle different event shapes from the SDK
                event_type = getattr(event, "type", None) or (event.get("type", "") if isinstance(event, dict) else "")
                if isinstance(event, str):
                    collected.append(event)
                    self._emit(AgentMessage(
                        agent=self.agent_name, role="code_engineer", content=event,
                    ))
                    continue

                if event_type == "assistant_message" or event_type == "text":
                    content = ""
                    if hasattr(event, "content"):
                        content = event.content if isinstance(event.content, str) else str(event.content)
                    elif isinstance(event, dict):
                        content = event.get("content", "")
                    if content:
                        collected.append(content)
                        self._emit(AgentMessage(
                            agent=self.agent_name, role="code_engineer", content=content,
                        ))

                elif event_type == "tool_use":
                    tool_input = getattr(event, "input", {}) or (event.get("input", {}) if isinstance(event, dict) else {})
                    tool_name = getattr(event, "name", "") or (event.get("name", "") if isinstance(event, dict) else "")
                    if tool_name in ("Write", "Edit"):
                        fp = tool_input.get("file_path", "unknown")
                        if fp not in files_modified:
                            files_modified.append(fp)
                        self._emit(AgentMessage(
                            agent=self.agent_name, role="code_engineer",
                            content=f"{'Writing' if tool_name == 'Write' else 'Editing'}: `{fp}`",
                        ))
                    elif tool_name == "Bash":
                        cmd = tool_input.get("command", "")
                        self._emit(AgentMessage(
                            agent=self.agent_name, role="code_engineer",
                            content=f"Running: `{cmd[:100]}`",
                        ))
                    else:
                        self._emit(AgentMessage(
                            agent=self.agent_name, role="code_engineer",
                            content=f"Tool: {tool_name}",
                        ))

                elif event_type == "result":
                    content = ""
                    if hasattr(event, "content"):
                        content = event.content if isinstance(event.content, str) else str(event.content)
                    elif isinstance(event, dict):
                        content = event.get("content", "")
                    if content and content not in collected:
                        collected.append(content)

            output = "\n".join(collected)
            self._emit(AgentMessage(
                agent=self.agent_name, role="code_engineer",
                content=f"Claude Agent 完成。修改文件: {', '.join(files_modified) or 'none'}",
                final=True,
            ))
            return ClaudeAgentResult(output=output, files_modified=files_modified, success=True)

        except Exception as exc:
            error_msg = f"Claude Agent 错误: {exc}"
            self._emit(AgentMessage(
                agent=self.agent_name, role="code_engineer", content=error_msg, final=True,
            ))
            return ClaudeAgentResult(output=error_msg, success=False, error=str(exc))

    def as_function_tool(self):
        from autogen_core.tools import FunctionTool  # type: ignore[import-untyped]

        async def _claude_agent_impl(prompt: str) -> str:
            result = await self.run(prompt)
            if not result.success:
                return f"Error: {result.error}"
            summary = result.output
            if result.files_modified:
                summary += f"\n\n修改文件: {', '.join(result.files_modified)}"
            return summary

        return FunctionTool(
            _claude_agent_impl,
            name="claude_agent",
            description=(
                "调用 Claude Agent 执行代码工程任务。"
                "当你需要编写、修改、调试实际代码文件时使用此工具。"
                "传入详细的实现指令，Claude Agent 将在目标项目目录中"
                "使用 Read/Write/Edit/Bash 工具完成任务。"
                "例如：'请实现用户注册模块，包括 API 路由、数据模型和测试'"
            ),
        )
