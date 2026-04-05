"""伊斯兰舒拉制 — 义务性协商 + 宗教法硬约束 + 领袖最终决定权。"""

from .base import GovernanceModel, GovernanceType


class ShuraModel(GovernanceModel):
    type = GovernanceType.SHURA
    name = "舒拉制"
    description = "伊斯兰舒拉：义务性协商（建议性非决策权）→伊斯兰法合规检查（硬约束不可绕过）→领袖最终决定→道德监察"
    dynasty = "伊斯兰"
    topology = "advisory-with-hard-constraint"

    def get_states(self) -> list[str]:
        return [
            "Pending", "ShuraConvened", "Consultation",
            "FiqhCheck", "LeaderDecision", "Executing", "Hisba", "Done", "Cancelled"
        ]

    def get_initial_state(self) -> str:
        return "Pending"

    def get_terminal_states(self) -> set[str]:
        return {"Done", "Cancelled"}

    def get_transitions(self) -> dict[str, set[str]]:
        return {
            "Pending":        {"ShuraConvened", "Cancelled"},
            "ShuraConvened":  {"Consultation", "Cancelled"},
            "Consultation":   {"FiqhCheck", "Cancelled"},
            "FiqhCheck":      {"LeaderDecision", "Cancelled"},   # 违反宗教法→直接取消，不可绕过
            "LeaderDecision": {"Executing", "Consultation", "Cancelled"},  # 领袖可要求重新协商
            "Executing":      {"Hisba", "Cancelled"},
            "Hisba":          {"Done", "Executing", "Cancelled"},  # 道德监察不通过→重做
        }

    def get_state_agent_map(self) -> dict[str, str]:
        return {
            "Pending":        "taizi",
            "ShuraConvened":  "shura_council",
            "Consultation":   "shura_council",
            "FiqhCheck":      "faqih",          # 法学家，宗教法裁定者
            "LeaderDecision": "leader",          # 领袖，最终决定权
            "Executing":      "shangshu",
            "Hisba":          "muhtasib",        # 市场/道德监察官
        }

    def validate_transition(self, from_state: str, to_state: str, context: dict | None = None) -> bool:
        allowed = self.get_transitions().get(from_state, set())
        if to_state not in allowed:
            return False
        ctx = context or {}
        # 宗教法硬约束：fiqh_compliant=False 时必须取消，不可绕过
        if from_state == "FiqhCheck" and to_state == "LeaderDecision":
            if not ctx.get("fiqh_compliant", True):
                return False  # 硬约束，无论如何不允许
            return True
        if from_state == "FiqhCheck" and to_state == "Cancelled":
            return not ctx.get("fiqh_compliant", True)
        # 领袖要求重新协商守卫
        if from_state == "LeaderDecision" and to_state == "Consultation":
            return ctx.get("leader_requires_reconsult", False)
        # 道德监察不通过守卫
        if from_state == "Hisba" and to_state == "Executing":
            return not ctx.get("hisba_passed", True)
        return True
