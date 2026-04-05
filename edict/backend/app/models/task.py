"""Task 模型 — 三省六部任务核心表。

对应当前 tasks_source.json 中的每一条任务记录。
state 对应三省六部流转状态机：
  Taizi → Zhongshu → Menxia → Assigned → Doing → Review → Done
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    String,
    Text,
    Boolean,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ..db import Base


# 终态集合（字符串，不再依赖枚举）
TERMINAL_STATES = {"Done", "Cancelled"}

# 向后兼容：保留 TaskState 作为常量容器
class TaskState:
    Taizi     = "Taizi"
    Zhongshu  = "Zhongshu"
    Menxia    = "Menxia"
    Assigned  = "Assigned"
    Next      = "Next"
    Doing     = "Doing"
    Review    = "Review"
    Done      = "Done"
    Blocked   = "Blocked"
    Cancelled = "Cancelled"
    Pending   = "Pending"

# 向后兼容：三省六部默认路由（OrchestratorWorker 动态加载前的兜底）
STATE_TRANSITIONS = {
    "Taizi":    {"Zhongshu", "Cancelled"},
    "Zhongshu": {"Menxia", "Cancelled", "Blocked"},
    "Menxia":   {"Assigned", "Zhongshu", "Cancelled"},
    "Assigned": {"Doing", "Next", "Cancelled", "Blocked"},
    "Next":     {"Doing", "Cancelled"},
    "Doing":    {"Review", "Done", "Blocked", "Cancelled"},
    "Review":   {"Done", "Doing", "Cancelled"},
    "Blocked":  {"Taizi", "Zhongshu", "Menxia", "Assigned", "Doing"},
}

STATE_AGENT_MAP = {
    "Taizi":    "taizi",
    "Zhongshu": "zhongshu",
    "Menxia":   "menxia",
    "Assigned": "shangshu",
    "Review":   "shangshu",
}

ORG_AGENT_MAP = {
    "户部": "hubu",
    "礼部": "libu",
    "兵部": "bingbu",
    "刑部": "xingbu",
    "工部": "gongbu",
    "吏部": "libu_hr",
}


class Task(Base):
    """三省六部任务表。"""
    __tablename__ = "tasks"

    id = Column(String(64), primary_key=True, comment="任务ID, e.g. JJC-20260301-001")
    title = Column(Text, nullable=False, comment="任务标题")
    state = Column(String(64), nullable=False, default="Taizi", index=True)
    governance_type = Column(String(32), nullable=False, default="san_sheng", comment="治理模型类型")
    governance_config = Column(JSONB, default=dict, comment="治理模型配置参数")
    mechanisms = Column(JSONB, default=list, comment="启用的跨制度机制 [ke_ju, yu_shi_tai, gong_guo_bu]")
    org = Column(String(32), nullable=False, default="太子", comment="当前执行部门")
    official = Column(String(32), default="", comment="责任官员")
    now = Column(Text, default="", comment="当前进展描述")
    eta = Column(String(64), default="-", comment="预计完成时间")
    block = Column(Text, default="无", comment="阻塞原因")
    output = Column(Text, default="", comment="最终产出")
    priority = Column(String(16), default="normal", comment="优先级")
    archived = Column(Boolean, default=False, index=True)

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
    )

    def to_dict(self) -> dict:
        """序列化为 API 响应格式（兼容旧 live_status 格式）。"""
        return {
            "id": self.id,
            "title": self.title,
            "state": self.state or "",
            "governance_type": self.governance_type or "san_sheng",
            "governance_config": self.governance_config or {},
            "mechanisms": self.mechanisms or [],
            "org": self.org,
            "official": self.official,
            "now": self.now,
            "eta": self.eta,
            "block": self.block,
            "output": self.output,
            "priority": self.priority,
            "archived": self.archived,
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
