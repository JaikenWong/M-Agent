"""RunService: 统一 run 生命周期与事件流。"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, Optional

log = logging.getLogger(__name__)

from .artifacts import RunArtifacts
from .config_models import AppConfig
from .orchestrator import AgentMessage, build_orchestrator
from .run_events import RunEvent

# 编排流结束哨兵（用 object() 与 AgentMessage 区分）
_ORCH_END = object()


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

        # 编排器单独跑在 pump 里，避免用 asyncio.wait 与 callback 竞态时
        # cancel 掉 __anext__，导致 async gen 报 GeneratorExit，进而让 OpenTelemetry
        # 在 “wrong Context” 上 detach 报错（见 trace_invoke_agent_span / run_stream）。
        orch_q: asyncio.Queue[AgentMessage | object] = asyncio.Queue()
        pump_error: list[BaseException] = []

        async def _pump_orchestrator() -> None:
            try:
                async for msg in orchestrator.run(task):
                    if self._cancel and self._cancel.is_set():
                        return
                    await orch_q.put(msg)
            except BaseException as exc:  # noqa: BLE001 — 记录后由主循环统一处理
                pump_error.append(exc)
            finally:
                await orch_q.put(_ORCH_END)

        pump_task = asyncio.create_task(_pump_orchestrator(), name="orchestrator_pump")
        orch_ended = False

        try:
            while not self._cancel.is_set():
                if orch_ended and callback_queue.empty():
                    break
                if orch_ended:
                    t_cb = asyncio.create_task(callback_queue.get(), name="callback")
                    done, pending = await asyncio.wait([t_cb], return_when=asyncio.FIRST_COMPLETED)
                else:
                    t_cb = asyncio.create_task(callback_queue.get(), name="callback")
                    t_orch = asyncio.create_task(orch_q.get(), name="orch_q")
                    done, pending = await asyncio.wait(
                        {t_cb, t_orch}, return_when=asyncio.FIRST_COMPLETED
                    )
                for p in pending:
                    p.cancel()
                    try:
                        await p
                    except asyncio.CancelledError:
                        pass

                task_done = next(iter(done))
                try:
                    result = task_done.result()
                except Exception as e:  # noqa: BLE001
                    log.exception("编排任务失败 (%s): %s", task_done.get_name(), e)
                    raise

                if task_done.get_name() == "orch_q":
                    if result is _ORCH_END:
                        orch_ended = True
                        if pump_error:
                            break
                        continue
                    assert isinstance(result, AgentMessage)
                    msg = result
                else:
                    assert isinstance(result, AgentMessage)
                    msg = result

                artifacts.write_message(msg)
                event = RunEvent.from_message(run_id, msg)
                artifacts.write_event(event)
                yield event

            if pump_error:
                raise pump_error[0]

            while not callback_queue.empty() and not self._cancel.is_set():
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
        finally:
            if not pump_task.done():
                pump_task.cancel()
                try:
                    await pump_task
                except asyncio.CancelledError:
                    pass
