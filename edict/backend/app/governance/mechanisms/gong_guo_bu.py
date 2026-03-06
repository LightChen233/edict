"""功过簿 — Agent 绩效追踪机制。

记录每个 Agent 的任务成功率、响应时间、被封驳次数等，
影响未来任务的 Agent 选择权重。可叠加到任何基础治理制度。
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any

from ..base import CrossCuttingMechanism, CrossCuttingType

log = logging.getLogger("edict.mechanism.gong_guo_bu")


class AgentRecord:
    """单个 Agent 的绩效记录。"""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.tasks_completed: int = 0
        self.tasks_failed: int = 0
        self.rejections: int = 0
        self.total_response_time_ms: float = 0
        self.task_count: int = 0
        self.merits: list[dict] = []   # 功
        self.demerits: list[dict] = []  # 过

    @property
    def success_rate(self) -> float:
        total = self.tasks_completed + self.tasks_failed
        return self.tasks_completed / total if total > 0 else 0.0

    @property
    def avg_response_time_ms(self) -> float:
        return self.total_response_time_ms / self.task_count if self.task_count > 0 else 0.0

    @property
    def score(self) -> float:
        """综合评分 (0-100)。"""
        base = 50.0
        base += self.success_rate * 30
        base -= min(self.rejections * 5, 20)
        base += len(self.merits) * 2
        base -= len(self.demerits) * 3
        return max(0.0, min(100.0, base))

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "rejections": self.rejections,
            "success_rate": round(self.success_rate, 3),
            "avg_response_time_ms": round(self.avg_response_time_ms, 1),
            "score": round(self.score, 1),
            "merits_count": len(self.merits),
            "demerits_count": len(self.demerits),
        }


class GongGuoBuMechanism(CrossCuttingMechanism):
    """功过簿 — 绩效追踪。"""

    def __init__(self) -> None:
        self._records: dict[str, AgentRecord] = defaultdict(lambda: AgentRecord(""))

    @property
    def type(self) -> CrossCuttingType:
        return CrossCuttingType.GONG_GUO_BU

    @property
    def name(self) -> str:
        return "功过簿"

    @property
    def description(self) -> str:
        return (
            "Agent 绩效追踪机制，记录任务成功率、响应时间、被封驳次数等。"
            "生成综合评分，影响未来任务的 Agent 选择权重。"
        )

    def _get_record(self, agent_id: str) -> AgentRecord:
        if agent_id not in self._records:
            self._records[agent_id] = AgentRecord(agent_id)
        return self._records[agent_id]

    async def on_before_dispatch(self, task_id: str, agent: str, context: dict) -> dict:
        """派发前：记录开始时间，注入 Agent 绩效信息。"""
        record = self._get_record(agent)
        record.task_count += 1
        context["_gongguobu_dispatch_time"] = time.monotonic()
        context["_gongguobu_agent"] = agent
        context["agent_score"] = record.score
        return context

    async def on_state_change(self, task_id: str, from_state: str, to_state: str, context: dict) -> None:
        """状态变更：检测打回和阻塞。"""
        agent = context.get("_gongguobu_agent", "")
        if not agent:
            return

        record = self._get_record(agent)

        rejection_states = {"Zhongshu", "Proposed", "Discussion", "CabinetReview"}
        review_states = {"Menxia", "Rejected", "Consensus", "CommitteeReview"}
        if to_state in rejection_states and from_state in review_states:
            record.rejections += 1
            record.demerits.append({
                "task_id": task_id,
                "type": "rejection",
                "detail": f"方案被打回: {from_state} → {to_state}",
            })
            log.info(f"功过簿: Agent {agent} 记过 — 方案被打回 (累计 {record.rejections} 次)")

    async def on_task_complete(self, task_id: str, context: dict) -> None:
        """任务完成：更新绩效记录。"""
        agent = context.get("_gongguobu_agent", "")
        if not agent:
            return

        record = self._get_record(agent)
        dispatch_time = context.get("_gongguobu_dispatch_time")
        if dispatch_time:
            elapsed = (time.monotonic() - dispatch_time) * 1000
            record.total_response_time_ms += elapsed

        is_success = context.get("task_state") not in ("Cancelled", "Failed")
        if is_success:
            record.tasks_completed += 1
            record.merits.append({
                "task_id": task_id,
                "type": "completion",
                "detail": "任务成功完成",
            })
        else:
            record.tasks_failed += 1
            record.demerits.append({
                "task_id": task_id,
                "type": "failure",
                "detail": "任务未成功完成",
            })

        log.info(f"功过簿: Agent {agent} 当前评分 {record.score:.1f}")

    def get_all_records(self) -> list[dict]:
        """返回所有 Agent 的绩效记录。"""
        return [r.to_dict() for r in self._records.values() if r.agent_id]

    def get_agent_record(self, agent_id: str) -> dict:
        return self._get_record(agent_id).to_dict()
