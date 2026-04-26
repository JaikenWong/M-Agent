"""RunService: 统一 run 生命周期与事件流。"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator, Optional

from .artifacts import RunArtifacts
from .config_models import AppConfig
from .orchestrator import AgentMessage, build_orchestrator
from .run_events import RunEvent


class RunService:
    def __init__(self, config: AppConfig):
        self.config = config
        self._cancel: Optional[asyncio.Event] = None

    def cancel(self) -> None:
        if self._cancel:
            self._cancel.set()

    async def run(self, task: str) -> AsyncIterator[RunEvent]:
        self._cancel = asyncio.Event()
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

        callback_queue: asyncio.Queue[AgentMessage] = asyncio.Queue()

        def _on_agent_message(msg: AgentMessage) -> None:
            callback_queue.put_nowait(msg)

        orchestrator = build_orchestrator(self.config, event_callback=_on_agent_message)
        initialized = RunEvent.now(
            "run_state_changed",
            run_id,
            content="orchestrator_initialized",
            metadata={"orchestrator": orchestrator.__class__.__name__},
        )
        artifacts.write_event(initialized)
        yield initialized

        try:
            orch_iter = orchestrator.run(task).__aiter__()
            orch_done = False

            while not self._cancel.is_set():
                tasks = []
                if not orch_done:
                    tasks.append(asyncio.create_task(orch_iter.__anext__(), name="orch"))
                tasks.append(asyncio.create_task(callback_queue.get(), name="callback"))

                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for p in pending:
                    p.cancel()

                for task_done in done:
                    try:
                        result = task_done.result()
                    except StopAsyncIteration:
                        if task_done.get_name() == "orch":
                            orch_done = True
                        continue
                    except Exception:
                        continue

                    msg = result
                    artifacts.write_message(msg)
                    event = RunEvent.from_message(run_id, msg)
                    artifacts.write_event(event)
                    yield event

                if orch_done and callback_queue.empty():
                    break

            # Drain remaining callback messages
            while not callback_queue.empty():
                msg = callback_queue.get_nowait()
                artifacts.write_message(msg)
                event = RunEvent.from_message(run_id, msg)
                artifacts.write_event(event)
                yield event

            if self._cancel.is_set():
                artifacts.finish("cancelled")
                cancelled = RunEvent.now("run_failed", run_id, content="用户取消")
                artifacts.write_event(cancelled)
                yield cancelled
                return

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
