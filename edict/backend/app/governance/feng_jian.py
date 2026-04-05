"""分封制 (周) — 并发自治，诸侯各自执行，天子干预兜底。"""

from .base import GovernanceModel, GovernanceType


class FengJianModel(GovernanceModel):
    type = GovernanceType.FENG_JIAN
    name = "分封制"
    description = "周代分封制：天子分派→诸侯并发自治执行→朝贡汇报，失联诸侯由天子接管"
    dynasty = "周"
    topology = "parallel-autonomous"

    def get_states(self) -> list[str]:
        return ["Pending", "Dispatched", "Doing", "Tribute", "Done", "Cancelled"]

    def get_initial_state(self) -> str:
        return "Pending"

    def get_terminal_states(self) -> set[str]:
        return {"Done", "Cancelled"}

    def get_transitions(self) -> dict[str, set[str]]:
        return {
            "Pending":    {"Dispatched", "Cancelled"},
            "Dispatched": {"Doing", "Cancelled"},
            "Doing":      {"Tribute", "Cancelled"},
            "Tribute":    {"Done", "Doing", "Cancelled"},  # 汇报不合格→重做
        }

    def get_state_agent_map(self) -> dict[str, str]:
        return {
            "Pending":    "tianzi",
            "Dispatched": "tianzi",
            "Doing":      "lord",    # 诸侯，具体由 assignee_org 决定
            "Tribute":    "tianzi",
        }

    def validate_transition(self, from_state: str, to_state: str, context: dict | None = None) -> bool:
        allowed = self.get_transitions().get(from_state, set())
        if to_state not in allowed:
            return False
        # 朝贡汇报不合格守卫：tribute_passed=False 才退回 Doing
        if from_state == "Tribute" and to_state == "Doing":
            return not (context or {}).get("tribute_passed", True)
        # 天子干预守卫：lost_lords 超过阈值时天子可强制接管（外部逻辑触发 Cancelled）
        if from_state == "Doing" and to_state == "Cancelled":
            ctx = context or {}
            lost = ctx.get("lost_lords", 0)
            threshold = ctx.get("intervention_threshold", 2)
            return lost >= threshold or ctx.get("tianzi_intervene", False)
        return True
