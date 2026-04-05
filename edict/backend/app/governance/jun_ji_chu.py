"""军机处 (清) — 极简直路，无审核层，紧急任务专用。"""

from .base import GovernanceModel, GovernanceType


class JunJiChuModel(GovernanceModel):
    type = GovernanceType.JUN_JI_CHU
    name = "军机处"
    description = "清代军机处：无审核层，皇帝→军机大臣→直接执行，不可回退，紧急任务专用"
    dynasty = "清"
    topology = "direct"

    def get_states(self) -> list[str]:
        return ["Pending", "JunJiReview", "Doing", "Done", "Cancelled"]

    def get_initial_state(self) -> str:
        return "Pending"

    def get_terminal_states(self) -> set[str]:
        return {"Done", "Cancelled"}

    def get_transitions(self) -> dict[str, set[str]]:
        return {
            "Pending":     {"JunJiReview", "Cancelled"},
            "JunJiReview": {"Doing", "Cancelled"},
            "Doing":       {"Done", "Cancelled"},
        }

    def get_state_agent_map(self) -> dict[str, str]:
        return {
            "Pending":     "taizi",
            "JunJiReview": "junji_dachen",
            "Doing":       "junji_dachen",
        }

    def validate_transition(self, from_state: str, to_state: str, context: dict | None = None) -> bool:
        allowed = self.get_transitions().get(from_state, set())
        if to_state not in allowed:
            return False
        # 紧急度守卫：Pending→JunJiReview 要求 priority==urgent
        if from_state == "Pending" and to_state == "JunJiReview":
            return (context or {}).get("priority") == "urgent"
        # 超时强制推进守卫：state_timeout_expired=True 时允许跳过当前状态
        if (context or {}).get("state_timeout_expired"):
            return True
        return True
