"""科举竞选机制 — 任务派发前通过竞争选拔最优 agent。

在 dispatch 前向多个候选 agent 发出竞标请求，
选择评分最高者执行，实现能力导向的动态路由。
"""

import logging
from dataclasses import dataclass, field

log = logging.getLogger("edict.mechanism.ke_ju")


@dataclass
class KeJuMechanism:
    """科举竞选：dispatch 前竞争选拔。"""

    name: str = "ke_ju"
    description: str = "科举竞选 — 多 agent 竞标，择优派发"

    # 候选 agent 列表，为空时使用治理模型默认路由
    candidates: list[str] = field(default_factory=list)
    # 竞标超时（秒）
    bid_timeout_sec: int = 30

    def select_agent(self, state: str, candidates: list[str], context: dict) -> str | None:
        """从候选 agent 中选拔最优者。

        当前实现：按 context 中的 agent_scores 选最高分；
        无评分数据时返回 None（回退到治理模型默认路由）。
        """
        scores: dict[str, float] = context.get("agent_scores", {})
        if not scores:
            log.debug("ke_ju: 无评分数据，回退默认路由")
            return None

        ranked = sorted(
            [(a, scores.get(a, 0.0)) for a in candidates],
            key=lambda x: x[1],
            reverse=True,
        )
        if not ranked:
            return None

        winner, score = ranked[0]
        log.info(f"ke_ju: 选拔 {winner}（得分 {score:.2f}）for state={state}")
        return winner

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "candidates": self.candidates,
            "bid_timeout_sec": self.bid_timeout_sec,
        }
