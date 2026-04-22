"""运行过程产物写入器。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .config_models import AppConfig
from .run_events import RunEvent

if TYPE_CHECKING:
    from .orchestrator import AgentMessage


@dataclass
class ArtifactRecord:
    timestamp: str
    agent: str
    role: str
    content: str
    final: bool


class RunArtifacts:
    """把任务和消息流写入 runs 目录及 agent 工作目录。"""

    def __init__(self, config: AppConfig, task: str, run_dir: Path):
        self.config = config
        self.task = task
        self.run_dir = run_dir
        self.run_id = run_dir.name
        self.transcript_path = self.run_dir / "transcript.jsonl"
        self.events_path = self.run_dir / "events.jsonl"
        self.summary_path = self.run_dir / "summary.md"

    @classmethod
    def start(cls, config: AppConfig, task: str) -> "RunArtifacts":
        root = config.ensure_workspace()
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        run_dir = root / "runs" / stamp
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run.json").write_text(
            json.dumps(
                {
                    "run_id": stamp,
                    "project": config.project_name,
                    "workflow": config.workflow.mode,
                    "started_at": datetime.now().isoformat(timespec="seconds"),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (run_dir / "task.md").write_text(f"# Task\n\n{task}\n", encoding="utf-8")
        summary = [
            "# Run Summary",
            "",
            f"- project: {config.project_name}",
            f"- workflow: {config.workflow.mode}",
            f"- started_at: {datetime.now().isoformat(timespec='seconds')}",
            "",
            "## Task",
            "",
            task,
            "",
            "## Agents",
            "",
        ]
        for agent in config.agents:
            summary.append(
                f"- {agent.name}: role={agent.role or '-'}, model={agent.model or config.default_model}, workspace={agent.resolved_workspace()}"
            )
        (run_dir / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
        return cls(config=config, task=task, run_dir=run_dir)

    def write_message(self, message: "AgentMessage") -> None:
        record = ArtifactRecord(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            agent=message.agent,
            role=message.role,
            content=message.content,
            final=message.final,
        )
        with self.transcript_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

        if message.agent == "system":
            target = self.run_dir / "system.md"
        else:
            workspace = self.config.ensure_workspace() / self._workspace_for_agent(message.agent)
            workspace.mkdir(parents=True, exist_ok=True)
            target = workspace / "activity.md"

        with target.open("a", encoding="utf-8") as fh:
            fh.write(
                f"\n## {record.timestamp} · {message.agent}"
                f"{' (final)' if message.final else ''}\n\n{message.content}\n"
            )

    def write_event(self, event: RunEvent) -> None:
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

    def finish(self, status: str, error: str | None = None) -> None:
        lines = [
            "",
            "## Result",
            "",
            f"- status: {status}",
            f"- finished_at: {datetime.now().isoformat(timespec='seconds')}",
        ]
        if error:
            lines.append(f"- error: {error}")
        with self.summary_path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

    def _workspace_for_agent(self, name: str) -> str:
        for agent in self.config.agents:
            if agent.name == name:
                return agent.resolved_workspace()
        return name
