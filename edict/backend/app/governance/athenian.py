"""雅典民主制 (古希腊) — 抽签选官 + 公民大会直接民主。"""

from .base import GovernanceModel, GovernanceType


class AthenianModel(GovernanceModel):
    type = GovernanceType.ATHENIAN
    name = "雅典民主制"
    description = "古希腊雅典：抽签选执行者（非能力选拔）→公民大会提案辩论→直接投票→执行后审计"
    dynasty = "古希腊"
    topology = "direct-democracy"

    def get_states(self) -> list[str]:
        return [
            "Pending", "Sortition", "AgonProposal", "Debate",
            "Ostracism", "DirectVote", "Executing", "Euthyna", "Done", "Cancelled"
        ]

    def get_initial_state(self) -> str:
        return "Pending"

    def get_terminal_states(self) -> set[str]:
        return {"Done", "Cancelled"}

    def get_transitions(self) -> dict[str, set[str]]:
        return {
            "Pending":      {"Sortition", "Cancelled"},
            "Sortition":    {"AgonProposal", "Cancelled"},
            "AgonProposal": {"Debate", "Cancelled"},
            "Debate":       {"Ostracism", "DirectVote", "Cancelled"},  # 可选陶片放逐
            "Ostracism":    {"Debate", "Cancelled"},                    # 放逐后重新辩论
            "DirectVote":   {"Executing", "AgonProposal", "Cancelled"}, # 否决→重新提案
            "Executing":    {"Euthyna", "Cancelled"},
            "Euthyna":      {"Done", "Executing", "Cancelled"},         # 审计不通过→重做
        }

    def get_state_agent_map(self) -> dict[str, str]:
        return {
            "Pending":      "taizi",
            "Sortition":    "system",
            "AgonProposal": "citizen",
            "Debate":       "citizen",
            "Ostracism":    "system",
            "DirectVote":   "system",
            "Executing":    "allotted",
            "Euthyna":      "auditor",
        }

    def validate_transition(self, from_state: str, to_state: str, context: dict | None = None) -> bool:
        allowed = self.get_transitions().get(from_state, set())
        if to_state not in allowed:
            return False
        ctx = context or {}
        # 直接投票通过守卫：简单多数（无 context 时默认通过）
        if from_state == "DirectVote" and to_state == "Executing":
            yes = ctx.get("yes_votes", 1)
            total = ctx.get("total_votes", 1)
            threshold = ctx.get("vote_threshold", 0.5)
            return (yes / total) > threshold
        # 陶片放逐守卫：需要有明确异见者
        if from_state == "Debate" and to_state == "Ostracism":
            return ctx.get("has_dissenter", False)
        # 审计不通过守卫
        if from_state == "Euthyna" and to_state == "Executing":
            return not ctx.get("euthyna_passed", True)
        return True
