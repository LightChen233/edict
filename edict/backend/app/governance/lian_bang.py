"""联邦制 (现代) — 多级并发，联邦协调 + 州自治。"""

from .base import GovernanceModel, GovernanceType


class LianBangModel(GovernanceModel):
    type = GovernanceType.LIAN_BANG
    name = "联邦制"
    description = "现代联邦制：联邦协调跨域任务→各州并发自治执行→联邦汇总边界冲突"
    dynasty = "现代"
    topology = "multi-level-parallel"

    def get_states(self) -> list[str]:
        return ["Pending", "FederalCoord", "StateDoing", "FederalReview", "Done", "Cancelled"]

    def get_initial_state(self) -> str:
        return "Pending"

    def get_terminal_states(self) -> set[str]:
        return {"Done", "Cancelled"}

    def get_transitions(self) -> dict[str, set[str]]:
        return {
            "Pending":      {"FederalCoord", "Cancelled"},
            "FederalCoord": {"StateDoing", "Cancelled"},
            "StateDoing":   {"FederalReview", "Cancelled"},
            "FederalReview": {"Done", "StateDoing", "Cancelled"},  # 冲突→重新协调
        }

    def get_state_agent_map(self) -> dict[str, str]:
        return {
            "Pending":       "taizi",
            "FederalCoord":  "tianzi",
            "StateDoing":    "lord",      # 各州 agent，由 assignee_org 决定
            "FederalReview": "tianzi",
        }

    def validate_transition(self, from_state: str, to_state: str, context: dict | None = None) -> bool:
        allowed = self.get_transitions().get(from_state, set())
        if to_state not in allowed:
            return False
        # 跨州协调守卫：只有 multi_domain=True 的任务才触发 FederalCoord
        if from_state == "Pending" and to_state == "FederalCoord":
            return (context or {}).get("multi_domain", True)
        # 冲突重协调守卫：有边界冲突才退回 StateDoing
        if from_state == "FederalReview" and to_state == "StateDoing":
            return (context or {}).get("boundary_conflict", False)
        return True
