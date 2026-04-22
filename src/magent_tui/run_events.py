"""运行事件模型。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal, Optional

from .orchestrator import AgentMessage


EventType = Literal[
    "run_started",
    "run_state_changed",
    "agent_message",
    "run_completed",
    "run_failed",
]


@dataclass
class RunEvent:
    event_type: EventType
    run_id: str
    timestamp: str
    agent: Optional[str] = None
    role: Optional[str] = None
    content: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def now(
        cls,
        event_type: EventType,
        run_id: str,
        *,
        agent: Optional[str] = None,
        role: Optional[str] = None,
        content: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "RunEvent":
        return cls(
            event_type=event_type,
            run_id=run_id,
            timestamp=datetime.now().isoformat(timespec="seconds"),
            agent=agent,
            role=role,
            content=content,
            metadata=metadata or {},
        )

    @classmethod
    def from_message(cls, run_id: str, message: AgentMessage) -> "RunEvent":
        return cls.now(
            "agent_message",
            run_id,
            agent=message.agent,
            role=message.role,
            content=message.content,
            metadata={"final": message.final},
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

