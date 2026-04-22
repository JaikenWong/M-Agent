"""Agent 可用的本地工作目录工具。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class WorkspaceToolset:
    agent_name: str
    workspace_root: Path
    agent_workspace: Path

    @classmethod
    def for_agent(cls, workspace_root: Path, workspace_name: str, agent_name: str) -> "WorkspaceToolset":
        root = workspace_root.resolve()
        agent_workspace = (root / workspace_name).resolve()
        agent_workspace.mkdir(parents=True, exist_ok=True)
        return cls(agent_name=agent_name, workspace_root=root, agent_workspace=agent_workspace)

    def _resolve(self, relative_path: str) -> Path:
        rel = Path(relative_path.strip() or ".")
        target = (self.agent_workspace / rel).resolve()
        try:
            target.relative_to(self.agent_workspace)
        except ValueError as exc:
            raise ValueError("路径必须位于当前 Agent 工作目录内") from exc
        return target

    def write_text_file(self, path: str, content: str) -> str:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"已写入 {target}"

    def append_text_file(self, path: str, content: str) -> str:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(content)
        return f"已追加 {target}"

    def read_text_file(self, path: str) -> str:
        target = self._resolve(path)
        return target.read_text(encoding="utf-8")

    def list_workspace_files(self, path: str = ".") -> str:
        target = self._resolve(path)
        if target.is_file():
            return str(target.relative_to(self.agent_workspace))
        if not target.exists():
            return "(empty)"
        files = sorted(
            str(item.relative_to(self.agent_workspace)) + ("/" if item.is_dir() else "")
            for item in target.rglob("*")
        )
        return "\n".join(files) if files else "(empty)"

    def tool_specs(self) -> list[dict[str, object]]:
        return [
            {
                "name": "write_text_file",
                "description": "将文本写入当前 Agent 工作目录内的文件，会覆盖已有内容。",
                "callable": self.write_text_file,
            },
            {
                "name": "append_text_file",
                "description": "向当前 Agent 工作目录内的文件追加文本。",
                "callable": self.append_text_file,
            },
            {
                "name": "read_text_file",
                "description": "读取当前 Agent 工作目录内的 UTF-8 文本文件。",
                "callable": self.read_text_file,
            },
            {
                "name": "list_workspace_files",
                "description": "列出当前 Agent 工作目录下的文件和目录。",
                "callable": self.list_workspace_files,
            },
        ]
