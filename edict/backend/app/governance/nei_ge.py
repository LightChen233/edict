"""内阁制 (明) — 票拟+批红，并发阁臣意见汇聚。"""

from .base import GovernanceModel, GovernanceType


class NeiGeModel(GovernanceModel):
    type = GovernanceType.NEI_GE
    name = "内阁制"
    description = "明代内阁：首辅票拟→阁臣并发意见→司礼监批红（用户可驳回/留中，超时自动批红）"
    dynasty = "明"
    topology = "parallel-converge"

    def get_states(self) -> list[str]:
        return ["Pending", "Piaoni", "Collecting", "Pihong", "Assigned", "Doing", "Done", "Cancelled"]

    def get_initial_state(self) -> str:
        return "Pending"

    def get_terminal_states(self) -> set[str]:
        return {"Done", "Cancelled"}

    def get_transitions(self) -> dict[str, set[str]]:
        return {
            "Pending":    {"Piaoni", "Cancelled"},
            "Piaoni":     {"Collecting", "Cancelled"},
            "Collecting": {"Pihong", "Cancelled"},
            "Pihong":     {"Assigned", "Piaoni", "Cancelled"},  # 驳回重新票拟
            "Assigned":   {"Doing", "Cancelled"},
            "Doing":      {"Done", "Cancelled"},
        }

    def get_state_agent_map(self) -> dict[str, str]:
        return {
            "Pending":    "taizi",
            "Piaoni":     "shoufu",
            "Collecting": "shoufu",
            "Pihong":     "system",   # 用户/司礼监
            "Assigned":   "shangshu",
        }

    def validate_transition(self, from_state: str, to_state: str, context: dict | None = None) -> bool:
        allowed = self.get_transitions().get(from_state, set())
        if to_state not in allowed:
            return False
        # 阁臣意见收齐守卫：cabinet_size 个阁臣全部提交才能进入批红
        if from_state == "Collecting" and to_state == "Pihong":
            ctx = context or {}
            cabinet_size = ctx.get("cabinet_size", 3)
            opinions = ctx.get("cabinet_opinions", 0)
            return opinions >= cabinet_size
        # 批红驳回守卫：司礼监明确驳回（pihong_rejected=True）才退回票拟
        if from_state == "Pihong" and to_state == "Piaoni":
            return (context or {}).get("pihong_rejected", False)
        # 留中超时自动批红：pihong_timeout=True 时强制放行
        if from_state == "Pihong" and to_state == "Assigned":
            ctx = context or {}
            return ctx.get("pihong_approved", False) or ctx.get("pihong_timeout", False)
        return True
