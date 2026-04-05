"""Dispatch Worker — 消费 task.dispatch 事件，执行 nanobot agent 调用。

核心解决旧架构痛点：
- 旧: daemon 线程 + subprocess.run → kill -9 丢失一切
- 新: Redis Streams ACK 保证 → 崩溃后自动重新投递

流程:
1. 从 task.dispatch stream 消费事件
2. 调用 nanobot Python API 处理任务
3. 根据 agent 名称加载对应的 SOUL.md 作为 system prompt
4. ACK 事件
"""

import asyncio
import logging
import os
import signal
from pathlib import Path
from datetime import datetime, timezone

from ..config import get_settings
from ..services.event_bus import (
    EventBus,
    TOPIC_TASK_DISPATCH,
    TOPIC_TASK_STATUS,
    TOPIC_AGENT_THOUGHTS,
    TOPIC_AGENT_HEARTBEAT,
)

log = logging.getLogger("edict.dispatcher")

GROUP = "dispatcher"
CONSUMER = "disp-1"

# Agent SOUL.md 路径映射
AGENT_SOUL_DIR = Path(__file__).parent.parent.parent.parent.parent / "agents"


def load_agent_soul(agent_name: str) -> str:
    """加载 agent 的 SOUL.md 作为 system prompt。"""
    soul_path = AGENT_SOUL_DIR / agent_name / "SOUL.md"
    if soul_path.exists():
        return soul_path.read_text(encoding="utf-8")
    log.warning(f"SOUL.md not found for agent '{agent_name}' at {soul_path}")
    return f"你是 {agent_name} agent，请完成用户交给你的任务。"


class DispatchWorker:
    """Agent 派发 Worker — 调用 nanobot Python API 执行 agent 任务。"""

    def __init__(self, max_concurrent: int = 20):
        self.bus = EventBus()
        self._running = False
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._nanobot_loop = None  # 延迟初始化

    async def start(self):
        await self.bus.connect()
        await self.bus.ensure_consumer_group(TOPIC_TASK_DISPATCH, GROUP)
        self._running = True
        log.info("🚀 Dispatch worker started")

        # 初始化 nanobot
        await self._init_nanobot()

        # 恢复崩溃遗留
        await self._recover_pending()

        while self._running:
            try:
                await self._poll_cycle()
            except Exception as e:
                log.error(f"Dispatch poll error: {e}", exc_info=True)
                await asyncio.sleep(2)

    async def stop(self):
        self._running = False
        # 等待进行中的 agent 调用完成
        if self._active_tasks:
            log.info(f"Waiting for {len(self._active_tasks)} active dispatches...")
            await asyncio.gather(*self._active_tasks.values(), return_exceptions=True)
        # 关闭 nanobot
        if self._nanobot_loop:
            await self._nanobot_loop.close_mcp()
        await self.bus.close()
        log.info("Dispatch worker stopped")

    async def _init_nanobot(self):
        """初始化 nanobot AgentLoop。"""
        try:
            from nanobot.agent.loop import AgentLoop
            from nanobot.bus.queue import MessageBus
            from nanobot.config.loader import load_config
            from nanobot.config.paths import get_cron_dir
            from nanobot.cron.service import CronService

            # 加载 nanobot 配置
            config = load_config()

            # 设置环境变量（LiteLLM 需要）
            api_key = config.providers.openai.api_key
            if api_key:
                os.environ["OPENAI_API_KEY"] = api_key
            if config.providers.openai.api_base:
                os.environ["OPENAI_API_BASE"] = config.providers.openai.api_base

            # 创建 provider
            from nanobot.providers.litellm_provider import LiteLLMProvider
            provider = LiteLLMProvider(
                api_key=api_key,
                api_base=config.providers.openai.api_base,
                default_model=config.agents.defaults.model,
            )

            # 创建 nanobot 组件
            bus = MessageBus()
            cron_store_path = get_cron_dir() / "jobs.json"
            cron = CronService(cron_store_path)

            # 创建 AgentLoop
            self._nanobot_loop = AgentLoop(
                bus=bus,
                provider=provider,
                workspace=Path(config.agents.defaults.workspace).expanduser(),
                model=config.agents.defaults.model,
                max_iterations=config.agents.defaults.max_tool_iterations,
                context_window_tokens=config.agents.defaults.context_window_tokens,
                web_search_config=config.tools.web.search,
                exec_config=config.tools.exec,
                cron_service=cron,
                restrict_to_workspace=config.tools.restrict_to_workspace,
            )
            log.info("✅ Nanobot initialized")
        except Exception as e:
            log.error(f"Failed to initialize nanobot: {e}", exc_info=True)
            raise

    async def _recover_pending(self):
        events = await self.bus.claim_stale(
            TOPIC_TASK_DISPATCH, GROUP, CONSUMER, min_idle_ms=60000, count=20
        )
        if events:
            log.info(f"Recovering {len(events)} stale dispatch events")
            for entry_id, event in events:
                await self._dispatch(entry_id, event)

    async def _poll_cycle(self):
        events = await self.bus.consume(
            TOPIC_TASK_DISPATCH, GROUP, CONSUMER, count=3, block_ms=2000
        )
        for entry_id, event in events:
            # 每个派发在独立任务中执行，带并发控制
            task = asyncio.create_task(self._dispatch(entry_id, event))
            task_id = event.get("payload", {}).get("task_id", entry_id)
            self._active_tasks[task_id] = task
            task.add_done_callback(lambda t, tid=task_id: self._active_tasks.pop(tid, None))

    async def _dispatch(self, entry_id: str, event: dict):
        """执行一次 agent 派发。"""
        async with self._semaphore:
            payload = event.get("payload", {})
            task_id = payload.get("task_id", "")
            agent = payload.get("agent", "")
            message = payload.get("message", "")
            trace_id = event.get("trace_id", "")
            state = payload.get("state", "")

            log.info(f"🔄 Dispatching task {task_id} → agent '{agent}' state={state}")

            # 发布心跳
            await self.bus.publish(
                topic=TOPIC_AGENT_HEARTBEAT,
                trace_id=trace_id,
                event_type="agent.dispatch.start",
                producer="dispatcher",
                payload={"task_id": task_id, "agent": agent},
            )

            try:
                result = await self._call_nanobot(agent, message, task_id, trace_id)

                # 发布 agent 输出
                await self.bus.publish(
                    topic=TOPIC_AGENT_THOUGHTS,
                    trace_id=trace_id,
                    event_type="agent.output",
                    producer=f"agent.{agent}",
                    payload={
                        "task_id": task_id,
                        "agent": agent,
                        "output": result.get("output", ""),
                        "success": result.get("success", False),
                    },
                )

                if result.get("success"):
                    log.info(f"✅ Agent '{agent}' completed task {task_id}")
                    # 更新任务进度并触发状态流转
                    await self._complete_agent_work(task_id, agent, state, result.get("output", ""))
                else:
                    log.warning(f"⚠️ Agent '{agent}' failed task {task_id}")

                # ACK — 事件处理完毕
                await self.bus.ack(TOPIC_TASK_DISPATCH, GROUP, entry_id)

            except Exception as e:
                log.error(f"❌ Dispatch failed: task {task_id} → {agent}: {e}", exc_info=True)
                # 不 ACK → Redis 会重新投递给其他消费者

    async def _call_nanobot(
        self,
        agent: str,
        message: str,
        task_id: str,
        trace_id: str,
    ) -> dict:
        """调用 nanobot 处理任务。"""
        if not self._nanobot_loop:
            return {"success": False, "output": "Nanobot not initialized"}

        try:
            # 加载 agent 的 SOUL.md
            soul = load_agent_soul(agent)

            # 构造完整的 prompt：SOUL + 任务
            full_prompt = f"""{soul}

---

## 当前任务

任务ID: {task_id}
追踪ID: {trace_id}

{message}

请按照你的角色定义完成上述任务，并输出结果。"""

            log.debug(f"Calling nanobot for agent '{agent}'")

            # 调用 nanobot
            response = await self._nanobot_loop.process_direct(
                content=full_prompt,
                session_key=f"edict:{agent}:{task_id}",
                channel="edict",
                chat_id=task_id,
            )

            return {
                "success": True,
                "output": response,
            }

        except Exception as e:
            log.error(f"Nanobot call failed: {e}", exc_info=True)
            return {
                "success": False,
                "output": f"Error: {str(e)}",
            }

    async def _update_task_progress(self, task_id: str, agent: str, output: str):
        """更新任务进度，通过 HTTP API。"""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                # 添加进度日志
                async with session.post(
                    f"http://localhost:8000/api/tasks/{task_id}/progress",
                    json={"agent": agent, "content": output[:500]},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        log.warning(f"Failed to update progress: {resp.status}")
        except Exception as e:
            log.error(f"Error updating task progress: {e}")

    async def _complete_agent_work(self, task_id: str, agent: str, current_state: str, output: str):
        """Agent 完成工作后，触发状态流转。"""
        import aiohttp
        try:
            # 1. 添加进度日志
            await self._update_task_progress(task_id, agent, output)

            # 2. 获取任务信息
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://localhost:8000/api/tasks/{task_id}",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        log.error(f"Failed to get task: {resp.status}")
                        return
                    task_data = await resp.json()

                # 3. 从治理模型获取下一个状态
                from ..governance.registry import registry as governance_registry
                governance_type = task_data.get("governance_type", "san_sheng")
                gov_model = governance_registry.get_model(governance_type)

                # 获取所有可能的下一个状态
                transitions = gov_model.get_transitions()
                next_states = transitions.get(current_state, set())
                if not next_states:
                    log.warning(f"No valid transitions from {current_state}")
                    return

                # 构建验证上下文
                context = {
                    "priority": task_data.get("priority", "normal"),
                    "agent": agent,
                }

                # 选择第一个通过验证的下一个状态
                # 终态排最后，向前推进的状态优先于回退状态，最后按字母排序
                terminal = gov_model.get_terminal_states()
                states_list = gov_model.get_states()
                state_order = {s: i for i, s in enumerate(states_list)}
                current_idx = state_order.get(current_state, 0)
                sorted_candidates = sorted(next_states, key=lambda s: (
                    s in terminal,
                    state_order.get(s, 999) <= current_idx,  # 回退状态排后
                    s,
                ))
                next_state = None
                for candidate in sorted_candidates:
                    if gov_model.validate_transition(current_state, candidate, context):
                        next_state = candidate
                        break

                if not next_state:
                    log.warning(f"No valid transitions from {current_state} for task {task_id} (context: {context})")
                    return

                # 4. 流转状态
                async with session.post(
                    f"http://localhost:8000/api/tasks/{task_id}/transition",
                    json={
                        "new_state": next_state,
                        "agent": agent,
                        "reason": f"Agent {agent} completed work",
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        log.info(f"✅ Transitioned task {task_id}: {current_state} → {next_state}")
                    else:
                        log.error(f"Failed to transition task: {resp.status}")
        except Exception as e:
            log.error(f"Error completing agent work: {e}", exc_info=True)



async def run_dispatcher():
    """入口函数 — 用于直接运行 worker。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    worker = DispatchWorker()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(worker.stop()))

    await worker.start()


if __name__ == "__main__":
    asyncio.run(run_dispatcher())
