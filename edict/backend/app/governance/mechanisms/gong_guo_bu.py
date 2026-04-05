"""功过簿绩效机制 — 追踪 agent 历史表现，动态调整路由权重。

功过簿记录每个 agent 的历史质量分、完成时长、错误次数，
为科举竞选提供评分依据，并支持效率随任务数单调提升（H5）。
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

log = logging.getLogger("edict.mechanism.gong_guo_bu")


@dataclass
class GongGuoBuRecord:
    """单个 agent 的功过记录。"""
    agent: str
    total_tasks: int = 0
    total_quality: float = 0.0
    total_completion_sec: float = 0.0
    error_count: int = 0
    last_updated: str = ""

    @property
    def avg_quality(self) -> float:
        if self.total_tasks == 0:
            return 5.0  # 无记录时给中性分
        return self.total_quality / self.total_tasks

    @property
    def avg_completion_sec(self) -> float:
        if self.total_tasks == 0:
            return 60.0
        return self.total_completion_sec / self.total_tasks

    @property
    def error_rate(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return self.error_count / self.total_tasks

    def score(self, quality_weight: float = 0.6,
              speed_weight: float = 0.3,
              error_weight: float = 0.1) -> float:
        """综合评分 0–10，用于科举竞选排名。"""
        quality_score = self.avg_quality
        # 速度分：完成越快越高，以 60s 为基准
        speed_score = min(10.0, 60.0 / max(self.avg_completion_sec, 1) * 6)
        error_penalty = self.error_rate * 10
        return (
            quality_score * quality_weight
            + speed_score * speed_weight
            - error_penalty * error_weight
        )


@dataclass
class GongGuoBuMechanism:
    """功过簿绩效：追踪 agent 历史表现，为科举提供评分。"""

    name: str = "gong_guo_bu"
    description: str = "功过簿绩效 — 追踪 agent 历史表现，动态调整路由权重"

    # agent_id → 功过记录
    records: dict[str, GongGuoBuRecord] = field(default_factory=dict)

    def record_completion(
        self,
        agent: str,
        quality_score: float,
        completion_sec: float,
        had_error: bool = False,
    ):
        """记录一次任务完成结果。"""
        if agent not in self.records:
            self.records[agent] = GongGuoBuRecord(agent=agent)
        r = self.records[agent]
        r.total_tasks += 1
        r.total_quality += quality_score
        r.total_completion_sec += completion_sec
        if had_error:
            r.error_count += 1
        r.last_updated = datetime.now(timezone.utc).isoformat()
        log.debug(f"gong_guo_bu: 更新 {agent} 记录，综合分={r.score():.2f}")

    def get_scores(self, agents: list[str]) -> dict[str, float]:
        """返回指定 agents 的综合评分，供科举竞选使用。"""
        return {a: self.records[a].score() if a in self.records else 5.0
                for a in agents}

    def get_record(self, agent: str) -> dict:
        if agent not in self.records:
            return {"agent": agent, "total_tasks": 0, "score": 5.0}
        r = self.records[agent]
        return {
            "agent": r.agent,
            "total_tasks": r.total_tasks,
            "avg_quality": round(r.avg_quality, 2),
            "avg_completion_sec": round(r.avg_completion_sec, 1),
            "error_rate": round(r.error_rate, 3),
            "score": round(r.score(), 2),
            "last_updated": r.last_updated,
        }

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "records": {a: self.get_record(a) for a in self.records},
        }
