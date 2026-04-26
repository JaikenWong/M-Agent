"""任务状态机。

状态流转:
    todo → pending → running ↔ input_required → done | failed | cancelled
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class TaskStatus(str, Enum):
    TODO = "todo"
    PENDING = "pending"
    RUNNING = "running"
    INPUT_REQUIRED = "input_required"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @classmethod
    def is_active(cls, status: "TaskStatus") -> bool:
        return status in {cls.PENDING, cls.RUNNING, cls.INPUT_REQUIRED}

    @classmethod
    def is_finished(cls, status: "TaskStatus") -> bool:
        return status in {cls.DONE, cls.FAILED, cls.CANCELLED}


STATUS_LABELS: dict[TaskStatus, str] = {
    TaskStatus.TODO: "📋 待执行",
    TaskStatus.PENDING: "⏳ 排队中",
    TaskStatus.RUNNING: "🔄 运行中",
    TaskStatus.INPUT_REQUIRED: "❓ 需要确认",
    TaskStatus.DONE: "✓ 完成",
    TaskStatus.FAILED: "✗ 失败",
    TaskStatus.CANCELLED: "⊘ 已取消",
}


@dataclass
class Task:
    id: str
    name: str
    prompt: str
    status: TaskStatus = TaskStatus.TODO
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    attention_requested_at: Optional[datetime] = None
    run_dir: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    def start(self) -> None:
        if self.status != TaskStatus.TODO:
            return
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()

    def request_attention(self) -> None:
        self.status = TaskStatus.INPUT_REQUIRED
        self.attention_requested_at = datetime.now()

    def resume(self) -> None:
        if self.status == TaskStatus.INPUT_REQUIRED:
            self.status = TaskStatus.RUNNING
            self.attention_requested_at = None

    def finish(self, success: bool = True, error: Optional[str] = None) -> None:
        self.status = TaskStatus.DONE if success else TaskStatus.FAILED
        self.finished_at = datetime.now()
        self.error_message = error

    def cancel(self) -> None:
        self.status = TaskStatus.CANCELLED
        self.finished_at = datetime.now()

    @property
    def is_active(self) -> bool:
        return TaskStatus.is_active(self.status)

    @property
    def is_finished(self) -> bool:
        return TaskStatus.is_finished(self.status)

    @property
    def needs_attention(self) -> bool:
        return self.status == TaskStatus.INPUT_REQUIRED

    @property
    def duration(self) -> Optional[float]:
        if self.started_at is None:
            return None
        end = self.finished_at or datetime.now()
        return (end - self.started_at).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "prompt": self.prompt,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "attention_requested_at": self.attention_requested_at.isoformat() if self.attention_requested_at else None,
            "run_dir": self.run_dir,
            "metadata": self.metadata,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        def parse_dt(s: Optional[str]) -> Optional[datetime]:
            return datetime.fromisoformat(s) if s else None
        return cls(
            id=data["id"],
            name=data["name"],
            prompt=data["prompt"],
            status=TaskStatus(data["status"]),
            created_at=parse_dt(data.get("created_at")),
            started_at=parse_dt(data.get("started_at")),
            finished_at=parse_dt(data.get("finished_at")),
            attention_requested_at=parse_dt(data.get("attention_requested_at")),
            run_dir=data.get("run_dir"),
            metadata=data.get("metadata", {}),
            error_message=data.get("error_message"),
        )


class TaskManager:
    def __init__(self, storage_path: Optional[Path] = None):
        self._tasks: dict[str, Task] = {}
        self._storage_path = storage_path or Path(".magent_tasks")

    def add(self, task: Task) -> None:
        self._tasks[task.id] = task

    def get(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def list(self, status: Optional[TaskStatus] = None) -> list[Task]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    def active_tasks(self) -> list[Task]:
        return [t for t in self._tasks.values() if t.is_active]

    def needs_attention_tasks(self) -> list[Task]:
        return [t for t in self._tasks.values() if t.needs_attention]

    def remove(self, task_id: str) -> None:
        self._tasks.pop(task_id, None)

    def save(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {tid: task.to_dict() for tid, task in self._tasks.items()}
        import json
        with open(self._storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self) -> None:
        if not self._storage_path.exists():
            return
        import json
        with open(self._storage_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._tasks = {tid: Task.from_dict(tdata) for tid, tdata in data.items()}

    def reconcile_stale_active_on_load(self) -> int:
        """服务重启后，持久化里仍处于 active 的任务不属本次进程，标为 failed。"""
        n = 0
        for t in list(self._tasks.values()):
            if t.is_active:
                t.status = TaskStatus.FAILED
                t.finished_at = datetime.now()
                t.error_message = t.error_message or "进程已重启，任务已中断；若已跑完可忽略本提示"
                n += 1
        if n:
            self.save()
        return n
