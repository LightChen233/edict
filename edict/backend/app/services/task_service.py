"""任务服务层 — CRUD + 状态机逻辑。

所有业务规则集中在此：
- 创建任务 → 发布 task.created 事件
- 状态流转 → 校验合法性 + 发布状态事件
- 查询、过滤、聚合
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.task import Task, TERMINAL_STATES
from ..governance.registry import registry as governance_registry
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

    # ── 创建 ──

    async def create_task(
        self,
        title: str,
        priority: str = "中",
        assignee_org: str | None = None,
        initial_state: str = "Taizi",
        governance_type: str = "san_sheng",
        governance_config: dict | None = None,
        mechanisms: list[str] | None = None,
    ) -> Task:
        """创建任务并发布 task.created 事件。"""
        now = datetime.now(timezone.utc)
        trace_id = str(uuid.uuid4())

        # 从治理模型获取初始状态
        gov_model = governance_registry.get_model(governance_type)
        resolved_initial = initial_state if initial_state != "Taizi" else gov_model.get_initial_state()

        task = Task(
            id=trace_id,
            title=title,
            state=resolved_initial,
            priority=priority,
            org=assignee_org or "太子",
            governance_type=governance_type,
            governance_config=governance_config or {},
            mechanisms=mechanisms or [],
            flow_log=[
                {
                    "from": None,
                    "to": resolved_initial,
                    "agent": "system",
                    "reason": "任务创建",
                    "ts": now.isoformat(),
                }
            ],
            progress_log=[],
            todos=[],
        )
        self.db.add(task)
        await self.db.flush()

        # 发布事件
        await self.bus.publish(
            topic=TOPIC_TASK_CREATED,
            trace_id=trace_id,
            event_type="task.created",
            producer="task_service",
            payload={
                "task_id": task.id,
                "title": title,
                "state": resolved_initial,
                "priority": priority,
                "assignee_org": assignee_org,
                "governance_type": governance_type,
            },
        )

        await self.db.commit()
        log.info(f"Created task {task.id}: {title} [{resolved_initial}]")
        return task

    # ── 状态流转 ──

    async def transition_state(
        self,
        task_id: uuid.UUID,
        new_state: str,
        agent: str = "system",
        reason: str = "",
        context: dict | None = None,
    ) -> Task:
        """执行状态流转，校验合法性。"""
        task = await self._get_task(task_id)
        old_state = task.state

        # 从治理模型校验转移合法性
        gov_model = governance_registry.get_model(task.governance_type or "san_sheng")
        if not gov_model.validate_transition(old_state, new_state, context):
            raise ValueError(
                f"Invalid transition: {old_state} → {new_state} "
                f"under governance '{task.governance_type}'"
            )

        task.state = new_state
        task.updated_at = datetime.now(timezone.utc)

        # 记入 flow_log
        flow_entry = {
            "from": old_state,
            "to": new_state,
            "agent": agent,
            "reason": reason,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        if task.flow_log is None:
            task.flow_log = []
        task.flow_log = [*task.flow_log, flow_entry]

        # 发布状态变更事件
        topic = TOPIC_TASK_COMPLETED if new_state in TERMINAL_STATES else TOPIC_TASK_STATUS
        await self.bus.publish(
            topic=topic,
            trace_id=str(task.id),
            event_type=f"task.state.{new_state}",
            producer=agent,
            payload={
                "task_id": str(task_id),
                "from": old_state,
                "to": new_state,
                "reason": reason,
                "governance_type": task.governance_type,
            },
        )

        await self.db.commit()
        log.info(f"Task {task_id} state: {old_state} → {new_state} by {agent}")
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
        await self.bus.publish(
            topic=TOPIC_TASK_DISPATCH,
            trace_id=str(task.trace_id),
            event_type="task.dispatch.request",
            producer="task_service",
            payload={
                "task_id": str(task_id),
                "agent": target_agent,
                "message": message,
                "state": task.state,
            },
        )
        log.info(f"Dispatch requested: task {task_id} → agent {target_agent}")

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
        state: str | None = None,
        assignee_org: str | None = None,
        priority: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Task]:
        stmt = select(Task)
        conditions = []
        if state is not None:
            conditions.append(Task.state == state)
        if assignee_org is not None:
            conditions.append(Task.assignee_org == assignee_org)
        if priority is not None:
            conditions.append(Task.priority == priority)
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
            if t.state in TERMINAL_STATES:
                completed_tasks[str(t.task_id)] = d
            else:
                active_tasks[str(t.task_id)] = d
        return {
            "tasks": active_tasks,
            "completed_tasks": completed_tasks,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    async def count_tasks(self, state: str | None = None) -> int:
        stmt = select(func.count(Task.task_id))
        if state is not None:
            stmt = stmt.where(Task.state == state)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    # ── 内部 ──

    async def _get_task(self, task_id) -> Task:
        task = await self.db.get(Task, str(task_id))
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        return task
