"""任务服务层 — CRUD + 动态治理模型状态机。

所有业务规则集中在此：
- 创建任务 → 选择治理制度 → 发布 task.created 事件
- 状态流转 → 通过 GovernanceModel 校验合法性 → 发布状态事件
- 跨制度机制拦截 → 科举/御史台/功过簿
- 查询、过滤、聚合
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.task import Task, TaskState, STATE_TRANSITIONS, TERMINAL_STATES, is_terminal_state
from ..governance import GovernanceType, get_registry
from .event_bus import (
    EventBus,
    TOPIC_TASK_CREATED,
    TOPIC_TASK_STATUS,
    TOPIC_TASK_COMPLETED,
    TOPIC_TASK_DISPATCH,
)

log = logging.getLogger("edict.task_service")


class TaskService:
    def __init__(self, db: AsyncSession, event_bus: EventBus):
        self.db = db
        self.bus = event_bus
        self._registry = get_registry()

    # ── 创建 ──

    async def create_task(
        self,
        title: str,
        description: str = "",
        priority: str = "中",
        assignee_org: str | None = None,
        creator: str = "emperor",
        tags: list[str] | None = None,
        initial_state: TaskState | str | None = None,
        meta: dict | None = None,
        governance_type: str = "san_sheng",
        governance_config: dict | None = None,
        mechanisms: list[str] | None = None,
    ) -> Task:
        """创建任务并发布 task.created 事件。

        governance_type 决定使用哪种治理模型，
        initial_state 若不指定则使用该模型的默认初始状态。
        """
        now = datetime.now(timezone.utc)
        trace_id = str(uuid.uuid4())

        gov_model = self._registry.get_model(governance_type)

        if initial_state is None:
            state_str = gov_model.get_initial_state()
        elif isinstance(initial_state, TaskState):
            state_str = initial_state.value
        else:
            state_str = initial_state

        if state_str not in gov_model.get_states():
            raise ValueError(
                f"State '{state_str}' is not valid for governance model '{governance_type}'. "
                f"Valid states: {gov_model.get_states()}"
            )

        task = Task(
            trace_id=trace_id,
            title=title,
            description=description,
            priority=priority,
            state=state_str,
            assignee_org=assignee_org,
            creator=creator,
            tags=tags or [],
            governance_type=governance_type,
            governance_config=governance_config or {},
            mechanisms=mechanisms or [],
            flow_log=[
                {
                    "from": None,
                    "to": state_str,
                    "agent": "system",
                    "reason": f"任务创建 (制度: {gov_model.name})",
                    "ts": now.isoformat(),
                }
            ],
            progress_log=[],
            todos=[],
            scheduler=None,
            meta=meta or {},
        )
        self.db.add(task)
        await self.db.flush()

        await self.bus.publish(
            topic=TOPIC_TASK_CREATED,
            trace_id=trace_id,
            event_type="task.created",
            producer="task_service",
            payload={
                "task_id": str(task.task_id),
                "title": title,
                "state": state_str,
                "priority": priority,
                "assignee_org": assignee_org,
                "governance_type": governance_type,
                "mechanisms": mechanisms or [],
            },
        )

        await self.db.commit()
        log.info(f"Created task {task.task_id}: {title} [{state_str}] (制度: {gov_model.name})")
        return task

    # ── 状态流转 ──

    async def transition_state(
        self,
        task_id: uuid.UUID,
        new_state: TaskState | str,
        agent: str = "system",
        reason: str = "",
    ) -> Task:
        """执行状态流转，通过治理模型校验合法性。"""
        task = await self._get_task(task_id)
        old_state_str = task.state if isinstance(task.state, str) else task.state.value
        new_state_str = new_state if isinstance(new_state, str) else new_state.value

        gov_model = self._registry.get_model(task.governance_type or "san_sheng")

        if not gov_model.validate_transition(old_state_str, new_state_str):
            allowed = gov_model.get_transitions().get(old_state_str, set())
            raise ValueError(
                f"Invalid transition: {old_state_str} → {new_state_str} "
                f"(制度: {gov_model.name}). "
                f"Allowed: {sorted(allowed)}"
            )

        task.state = new_state_str
        task.updated_at = datetime.now(timezone.utc)

        flow_entry = {
            "from": old_state_str,
            "to": new_state_str,
            "agent": agent,
            "reason": reason,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        if task.flow_log is None:
            task.flow_log = []
        task.flow_log = [*task.flow_log, flow_entry]

        is_terminal = new_state_str in gov_model.get_terminal_states()
        topic = TOPIC_TASK_COMPLETED if is_terminal else TOPIC_TASK_STATUS
        await self.bus.publish(
            topic=topic,
            trace_id=str(task.trace_id),
            event_type=f"task.state.{new_state_str}",
            producer=agent,
            payload={
                "task_id": str(task_id),
                "from": old_state_str,
                "to": new_state_str,
                "reason": reason,
                "governance_type": task.governance_type,
            },
        )

        # 触发跨制度机制回调
        for mech_type in (task.mechanisms or []):
            try:
                mechanism = self._registry.get_mechanism(mech_type)
                await mechanism.on_state_change(
                    str(task_id), old_state_str, new_state_str,
                    {"flow_log": task.flow_log, "task_state": new_state_str},
                )
            except KeyError:
                log.warning(f"Unknown mechanism: {mech_type}")

        await self.db.commit()
        log.info(f"Task {task_id} state: {old_state_str} → {new_state_str} by {agent}")
        return task

    # ── 派发请求 ──

    async def request_dispatch(
        self,
        task_id: uuid.UUID,
        target_agent: str,
        message: str = "",
    ):
        """发布 task.dispatch 事件，由 DispatchWorker 消费执行。"""
        task = await self._get_task(task_id)
        state_str = task.state if isinstance(task.state, str) else task.state.value

        context = {
            "task_id": str(task_id),
            "agent": target_agent,
            "governance_type": task.governance_type,
        }

        # 跨制度机制拦截（如科举制竞选）
        for mech_type in (task.mechanisms or []):
            try:
                mechanism = self._registry.get_mechanism(mech_type)
                context = await mechanism.on_before_dispatch(str(task_id), target_agent, context)
                if "selected_agent" in context:
                    target_agent = context["selected_agent"]
            except KeyError:
                pass

        await self.bus.publish(
            topic=TOPIC_TASK_DISPATCH,
            trace_id=str(task.trace_id),
            event_type="task.dispatch.request",
            producer="task_service",
            payload={
                "task_id": str(task_id),
                "agent": target_agent,
                "message": message,
                "state": state_str,
                "governance_type": task.governance_type,
            },
        )
        log.info(f"Dispatch requested: task {task_id} → agent {target_agent}")

    # ── 治理模型查询 ──

    def get_governance_info(self, governance_type: str) -> dict:
        """获取治理模型的详细信息。"""
        gov_model = self._registry.get_model(governance_type)
        info = gov_model.to_info()
        return {
            "type": info.type,
            "name": info.name,
            "dynasty": info.dynasty,
            "description": info.description,
            "flow_pattern": info.flow_pattern,
            "states": info.states,
            "initial_state": info.initial_state,
            "terminal_states": info.terminal_states,
            "transitions": info.transitions,
            "roles": info.roles,
            "state_agent_map": info.state_agent_map,
            "permission_matrix": info.permission_matrix,
            "suitable_for": info.suitable_for,
        }

    def list_governance_models(self) -> list[dict]:
        """列出所有可用的治理模型摘要。"""
        return [
            {
                "type": m.type.value,
                "name": m.name,
                "dynasty": m.dynasty,
                "description": m.description,
                "flow_pattern": m.flow_pattern.value,
                "suitable_for": m.suitable_for,
            }
            for m in self._registry.list_models()
        ]

    # ── 进度/备注更新 ──

    async def add_progress(
        self,
        task_id: uuid.UUID,
        agent: str,
        content: str,
    ) -> Task:
        task = await self._get_task(task_id)
        entry = {
            "agent": agent,
            "content": content,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        if task.progress_log is None:
            task.progress_log = []
        task.progress_log = [*task.progress_log, entry]
        task.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        return task

    async def update_todos(
        self,
        task_id: uuid.UUID,
        todos: list[dict],
    ) -> Task:
        task = await self._get_task(task_id)
        task.todos = todos
        task.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        return task

    async def update_scheduler(
        self,
        task_id: uuid.UUID,
        scheduler: dict,
    ) -> Task:
        task = await self._get_task(task_id)
        task.scheduler = scheduler
        task.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        return task

    # ── 查询 ──

    async def get_task(self, task_id: uuid.UUID) -> Task:
        return await self._get_task(task_id)

    async def list_tasks(
        self,
        state: TaskState | str | None = None,
        assignee_org: str | None = None,
        priority: str | None = None,
        governance_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Task]:
        stmt = select(Task)
        conditions = []
        if state is not None:
            state_val = state.value if isinstance(state, TaskState) else state
            conditions.append(Task.state == state_val)
        if assignee_org is not None:
            conditions.append(Task.assignee_org == assignee_org)
        if priority is not None:
            conditions.append(Task.priority == priority)
        if governance_type is not None:
            conditions.append(Task.governance_type == governance_type)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(Task.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_live_status(self) -> dict[str, Any]:
        """生成兼容旧 live_status.json 格式的全局状态。"""
        tasks = await self.list_tasks(limit=200)
        active_tasks = {}
        completed_tasks = {}
        for t in tasks:
            d = t.to_dict()
            state_str = t.state if isinstance(t.state, str) else t.state.value
            if is_terminal_state(state_str):
                completed_tasks[str(t.task_id)] = d
            else:
                active_tasks[str(t.task_id)] = d
        return {
            "tasks": active_tasks,
            "completed_tasks": completed_tasks,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    async def count_tasks(self, state: TaskState | str | None = None) -> int:
        stmt = select(func.count(Task.task_id))
        if state is not None:
            state_val = state.value if isinstance(state, TaskState) else state
            stmt = stmt.where(Task.state == state_val)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    # ── 内部 ──

    async def _get_task(self, task_id: uuid.UUID) -> Task:
        task = await self.db.get(Task, task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        return task
