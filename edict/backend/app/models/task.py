"""Task 模型 — 多制度治理任务核心表。

支持多种治理制度（三省六部制、丞相制、内阁制、议会制等），
每个任务绑定一种治理模型，state 字段为动态字符串以适配不同制度。

默认制度: 三省六部制 (san_sheng)
  Taizi → Zhongshu → Menxia → Assigned → Doing → Review → Done
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    String,
    Text,
    Boolean,
    Integer,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ..db import Base


# ── 向后兼容: 保留 TaskState 枚举供三省六部制使用 ──

class TaskState(str, enum.Enum):
    """三省六部制任务状态枚举（向后兼容）。

    新代码应通过 GovernanceModel.get_states() 获取状态列表，
    不再硬依赖此枚举。
    """
    Taizi = "Taizi"
    Zhongshu = "Zhongshu"
    Menxia = "Menxia"
    Assigned = "Assigned"
    Next = "Next"
    Doing = "Doing"
    Review = "Review"
    Done = "Done"
    Blocked = "Blocked"
    Cancelled = "Cancelled"
    Pending = "Pending"


# 向后兼容: 静态常量（仅供三省六部制和旧代码使用）
TERMINAL_STATES = {TaskState.Done, TaskState.Cancelled}

STATE_TRANSITIONS = {
    TaskState.Taizi: {TaskState.Zhongshu, TaskState.Cancelled},
    TaskState.Zhongshu: {TaskState.Menxia, TaskState.Cancelled, TaskState.Blocked},
    TaskState.Menxia: {TaskState.Assigned, TaskState.Zhongshu, TaskState.Cancelled},
    TaskState.Assigned: {TaskState.Doing, TaskState.Next, TaskState.Cancelled, TaskState.Blocked},
    TaskState.Next: {TaskState.Doing, TaskState.Cancelled},
    TaskState.Doing: {TaskState.Review, TaskState.Done, TaskState.Blocked, TaskState.Cancelled},
    TaskState.Review: {TaskState.Done, TaskState.Doing, TaskState.Cancelled},
    TaskState.Blocked: {TaskState.Taizi, TaskState.Zhongshu, TaskState.Menxia, TaskState.Assigned, TaskState.Doing},
}

STATE_AGENT_MAP = {
    TaskState.Taizi: "taizi",
    TaskState.Zhongshu: "zhongshu",
    TaskState.Menxia: "menxia",
    TaskState.Assigned: "shangshu",
    TaskState.Review: "shangshu",
}

ORG_AGENT_MAP = {
    "户部": "hubu",
    "礼部": "libu",
    "兵部": "bingbu",
    "刑部": "xingbu",
    "工部": "gongbu",
    "吏部": "libu_hr",
}

# 通用终态名（所有制度共享）
UNIVERSAL_TERMINAL_STATES = {"Done", "Cancelled"}


def is_terminal_state(state: str) -> bool:
    """判断状态是否为终态（跨制度通用）。"""
    return state in UNIVERSAL_TERMINAL_STATES


class Task(Base):
    """多制度治理任务表。"""
    __tablename__ = "tasks"

    id = Column(String(32), primary_key=True, comment="任务ID, e.g. JJC-20260301-001")
    title = Column(Text, nullable=False, comment="任务标题")
    state = Column(String(64), nullable=False, default="Taizi", index=True, comment="当前状态（动态，取决于治理制度）")
    org = Column(String(32), nullable=False, default="太子", comment="当前执行部门")
    official = Column(String(32), default="", comment="责任官员")
    now = Column(Text, default="", comment="当前进展描述")
    eta = Column(String(64), default="-", comment="预计完成时间")
    block = Column(Text, default="无", comment="阻塞原因")
    output = Column(Text, default="", comment="最终产出")
    priority = Column(String(16), default="normal", comment="优先级")
    archived = Column(Boolean, default=False, index=True)

    # 治理制度
    governance_type = Column(String(32), nullable=False, default="san_sheng", comment="治理制度类型")
    governance_config = Column(JSONB, default=dict, comment="制度特有配置")
    mechanisms = Column(JSONB, default=list, comment="叠加的跨制度机制 ['ke_ju', 'yu_shi_tai']")

    # JSONB 灵活字段
    flow_log = Column(JSONB, default=list, comment="流转日志 [{at, from, to, remark}]")
    progress_log = Column(JSONB, default=list, comment="进展日志 [{at, agent, text, todos}]")
    todos = Column(JSONB, default=list, comment="子任务 [{id, title, status, detail}]")
    scheduler = Column(JSONB, default=dict, comment="调度器元数据")
    template_id = Column(String(64), default="", comment="模板ID")
    template_params = Column(JSONB, default=dict, comment="模板参数")
    ac = Column(Text, default="", comment="验收标准")
    target_dept = Column(String(64), default="", comment="目标部门")

    # 时间戳
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_tasks_state_archived", "state", "archived"),
        Index("ix_tasks_updated_at", "updated_at"),
        Index("ix_tasks_governance_type", "governance_type"),
    )

    def to_dict(self) -> dict:
        """序列化为 API 响应格式（兼容旧 live_status 格式）。"""
        state_val = self.state
        if hasattr(state_val, "value"):
            state_val = state_val.value
        return {
            "id": self.id,
            "title": self.title,
            "state": state_val or "",
            "org": self.org,
            "official": self.official,
            "now": self.now,
            "eta": self.eta,
            "block": self.block,
            "output": self.output,
            "priority": self.priority,
            "archived": self.archived,
            "governance_type": self.governance_type or "san_sheng",
            "governance_config": self.governance_config or {},
            "mechanisms": self.mechanisms or [],
            "flow_log": self.flow_log or [],
            "progress_log": self.progress_log or [],
            "todos": self.todos or [],
            "templateId": self.template_id,
            "templateParams": self.template_params or {},
            "ac": self.ac,
            "targetDept": self.target_dept,
            "_scheduler": self.scheduler or {},
            "createdAt": self.created_at.isoformat() if self.created_at else "",
            "updatedAt": self.updated_at.isoformat() if self.updated_at else "",
        }
