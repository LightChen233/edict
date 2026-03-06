"""Orchestrator Worker — 消费事件总线，驱动多制度任务状态机。

监听 topic:
- task.created → 根据治理模型派发给对应初始 agent
- task.status → 根据治理模型确定下一个 agent 并派发
- task.completed → 记录完成，触发跨制度机制回调
- task.stalled → 处理停滞任务

核心改造: 不再硬编码三省六部的映射，而是通过 GovernanceRegistry
动态获取任务对应的治理模型来确定状态流转和 Agent 派发。
"""

import asyncio
import logging
import signal

from ..config import get_settings
from ..db import async_session
from ..governance import get_registry
from ..models.task import is_terminal_state
from ..services.event_bus import (
    EventBus,
    TOPIC_TASK_CREATED,
    TOPIC_TASK_STATUS,
    TOPIC_TASK_DISPATCH,
    TOPIC_TASK_COMPLETED,
    TOPIC_TASK_STALLED,
)
from ..services.task_service import TaskService

log = logging.getLogger("edict.orchestrator")

GROUP = "orchestrator"
CONSUMER = "orch-1"

WATCHED_TOPICS = [
    TOPIC_TASK_CREATED,
    TOPIC_TASK_STATUS,
    TOPIC_TASK_COMPLETED,
    TOPIC_TASK_STALLED,
]


class OrchestratorWorker:
    """事件驱动的多制度编排器 Worker。"""

    def __init__(self):
        self.bus = EventBus()
        self._running = False
        self._registry = get_registry()

    async def start(self):
        """启动 worker 主循环。"""
        await self.bus.connect()

        for topic in WATCHED_TOPICS:
            await self.bus.ensure_consumer_group(topic, GROUP)

        self._running = True
        log.info("Orchestrator worker started (multi-governance)")

        await self._recover_pending()

        while self._running:
            try:
                await self._poll_cycle()
            except Exception as e:
                log.error(f"Orchestrator poll error: {e}", exc_info=True)
                await asyncio.sleep(2)

    async def stop(self):
        self._running = False
        await self.bus.close()
        log.info("Orchestrator worker stopped")

    async def _recover_pending(self):
        """恢复崩溃前未 ACK 的事件。"""
        for topic in WATCHED_TOPICS:
            events = await self.bus.claim_stale(
                topic, GROUP, CONSUMER, min_idle_ms=30000, count=50
            )
            if events:
                log.info(f"Recovering {len(events)} stale events from {topic}")
                for entry_id, event in events:
                    await self._handle_event(topic, entry_id, event)

    async def _poll_cycle(self):
        """一次轮询周期：从所有 topic 消费事件。"""
        for topic in WATCHED_TOPICS:
            events = await self.bus.consume(
                topic, GROUP, CONSUMER, count=5, block_ms=1000
            )
            for entry_id, event in events:
                try:
                    await self._handle_event(topic, entry_id, event)
                    await self.bus.ack(topic, GROUP, entry_id)
                except Exception as e:
                    log.error(
                        f"Error handling event {entry_id} from {topic}: {e}",
                        exc_info=True,
                    )

    async def _handle_event(self, topic: str, entry_id: str, event: dict):
        """根据 topic 分发处理。"""
        event_type = event.get("event_type", "")
        trace_id = event.get("trace_id", "")
        payload = event.get("payload", {})

        log.info(f"{topic}/{event_type} trace={trace_id}")

        if topic == TOPIC_TASK_CREATED:
            await self._on_task_created(payload, trace_id)
        elif topic == TOPIC_TASK_STATUS:
            await self._on_task_status(event_type, payload, trace_id)
        elif topic == TOPIC_TASK_COMPLETED:
            await self._on_task_completed(payload, trace_id)
        elif topic == TOPIC_TASK_STALLED:
            await self._on_task_stalled(payload, trace_id)

    def _resolve_agent(self, gov_type: str, state: str, payload: dict) -> str | None:
        """通过治理模型解析目标 Agent。"""
        try:
            model = self._registry.get_model(gov_type)
        except KeyError:
            log.warning(f"Unknown governance type '{gov_type}', falling back to san_sheng")
            model = self._registry.get_model("san_sheng")

        context = {
            "assignee_org": payload.get("assignee_org", ""),
            "task_id": payload.get("task_id", ""),
        }
        return model.get_next_agent(state, context)

    async def _on_task_created(self, payload: dict, trace_id: str):
        """任务创建 → 根据治理模型派发给初始 agent。"""
        task_id = payload.get("task_id")
        state = payload.get("state", "Taizi")
        gov_type = payload.get("governance_type", "san_sheng")

        agent = self._resolve_agent(gov_type, state, payload)
        if not agent:
            log.warning(f"No agent for state '{state}' in governance '{gov_type}'")
            return

        await self.bus.publish(
            topic=TOPIC_TASK_DISPATCH,
            trace_id=trace_id,
            event_type="task.dispatch.request",
            producer="orchestrator",
            payload={
                "task_id": task_id,
                "agent": agent,
                "state": state,
                "governance_type": gov_type,
                "message": f"新任务已创建: {payload.get('title', '')}",
            },
        )

    async def _on_task_status(self, event_type: str, payload: dict, trace_id: str):
        """状态变更 → 通过治理模型自动派发下一个 agent。"""
        task_id = payload.get("task_id")
        new_state = payload.get("to", "")
        gov_type = payload.get("governance_type", "san_sheng")

        if is_terminal_state(new_state):
            return

        agent = self._resolve_agent(gov_type, new_state, payload)
        if agent:
            await self.bus.publish(
                topic=TOPIC_TASK_DISPATCH,
                trace_id=trace_id,
                event_type="task.dispatch.request",
                producer="orchestrator",
                payload={
                    "task_id": task_id,
                    "agent": agent,
                    "state": new_state,
                    "governance_type": gov_type,
                    "message": f"任务已流转到 {new_state}",
                },
            )

    async def _on_task_completed(self, payload: dict, trace_id: str):
        """任务完成 → 触发跨制度机制回调。"""
        task_id = payload.get("task_id")
        mechanisms = payload.get("mechanisms", [])

        for mech_type in mechanisms:
            try:
                mechanism = self._registry.get_mechanism(mech_type)
                await mechanism.on_task_complete(task_id, payload)
            except KeyError:
                pass

        log.info(f"Task {task_id} completed. trace={trace_id}")

    async def _on_task_stalled(self, payload: dict, trace_id: str):
        """任务停滞 → 通知或重新派发。"""
        task_id = payload.get("task_id")
        log.warning(f"Task {task_id} stalled! Requesting intervention. trace={trace_id}")


async def run_orchestrator():
    """入口函数 — 用于直接运行 worker。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    worker = OrchestratorWorker()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(worker.stop()))

    await worker.start()
