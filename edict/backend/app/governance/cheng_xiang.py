"""丞相制 (秦汉) — Hub-spoke，丞相单点决策。"""

from .base import GovernanceModel, GovernanceType


class ChengXiangModel(GovernanceModel):
    type = GovernanceType.CHENG_XIANG
    name = "丞相制"
    description = "秦汉丞相制：皇帝→丞相单点决策→属吏执行，皇帝可在超时前否决"
    dynasty = "秦汉"
    topology = "hub-and-spoke"

    def get_states(self) -> list[str]:
        return ["Pending", "ChengXiangReview", "Assigned", "Doing", "Done", "Cancelled"]

    def get_initial_state(self) -> str:
        return "Pending"

    def get_terminal_states(self) -> set[str]:
        return {"Done", "Cancelled"}

    def get_transitions(self) -> dict[str, set[str]]:
        return {
            "Pending":         {"ChengXiangReview", "Cancelled"},
            "ChengXiangReview": {"Assigned", "Cancelled"},
            "Assigned":        {"Doing", "Cancelled"},
            "Doing":           {"Done", "Cancelled"},
        }

    def get_state_agent_map(self) -> dict[str, str]:
        return {
            "Pending":          "taizi",
            "ChengXiangReview": "chengxiang",
            "Assigned":         "chengxiang",
            "Doing":            "shangshu",
        }

    def validate_transition(self, from_state: str, to_state: str, context: dict | None = None) -> bool:
        allowed = self.get_transitions().get(from_state, set())
        if to_state not in allowed:
            return False
        # 皇帝否决守卫：veto_deadline 未过期时用户可取消，超时则自动确认（外部超时逻辑设置 veto_expired=True）
        if from_state == "ChengXiangReview" and to_state == "Cancelled":
            ctx = context or {}
            return not ctx.get("veto_expired", False)
        return True
