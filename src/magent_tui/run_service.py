"""RunService: 统一 run 生命周期与事件流。"""

from __future__ import annotations

from typing import AsyncIterator

from .artifacts import RunArtifacts
from .config_models import AppConfig
from .orchestrator import build_orchestrator
from .run_events import RunEvent


class RunService:
    def __init__(self, config: AppConfig):
        self.config = config

    async def run(self, task: str) -> AsyncIterator[RunEvent]:
        artifacts = RunArtifacts.start(self.config, task)
        run_id = artifacts.run_id
        started = RunEvent.now(
            "run_started",
            run_id,
            content=f"任务开始：{task}",
            metadata={"run_dir": str(artifacts.run_dir)},
        )
        artifacts.write_event(started)
        yield started

        orchestrator = build_orchestrator(self.config)
        initialized = RunEvent.now(
            "run_state_changed",
            run_id,
            content="orchestrator_initialized",
            metadata={"orchestrator": orchestrator.__class__.__name__},
        )
        artifacts.write_event(initialized)
        yield initialized

        try:
            async for msg in orchestrator.run(task):
                artifacts.write_message(msg)
                event = RunEvent.from_message(run_id, msg)
                artifacts.write_event(event)
                yield event
            artifacts.finish("completed")
            done = RunEvent.now("run_completed", run_id, content="运行完成")
            artifacts.write_event(done)
            yield done
        except Exception as exc:
            artifacts.finish("failed", error=str(exc))
            failed = RunEvent.now("run_failed", run_id, content=str(exc))
            artifacts.write_event(failed)
            yield failed
            raise

