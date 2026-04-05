"""三省六部制 (唐) — 线性流水线 + 门下省封驳 + 六部并发。"""

from .base import GovernanceModel, GovernanceType


class SanShengModel(GovernanceModel):
    type = GovernanceType.SAN_SHENG
    name = "三省六部制"
    description = "唐代三省六部：中书起草→门下审议（可封驳≤3次）→尚书派发→六部并发执行"
    dynasty = "唐"
    topology = "pipeline+fork"

    def get_states(self) -> list[str]:
        return ["Taizi", "Zhongshu", "Menxia", "Assigned", "Doing", "Review", "Done", "Blocked", "Cancelled"]

    def get_initial_state(self) -> str:
        return "Taizi"

    def get_terminal_states(self) -> set[str]:
        return {"Done", "Cancelled"}

    def get_transitions(self) -> dict[str, set[str]]:
        return {
            "Taizi":    {"Zhongshu", "Cancelled"},
            "Zhongshu": {"Menxia", "Cancelled", "Blocked"},
            "Menxia":   {"Assigned", "Zhongshu", "Cancelled"},  # 封驳退回中书
            "Assigned": {"Doing", "Cancelled", "Blocked"},
            "Doing":    {"Review", "Done", "Blocked", "Cancelled"},
            "Review":   {"Done", "Doing", "Cancelled"},          # 审查不通过退回
            "Blocked":  {"Taizi", "Zhongshu", "Menxia", "Assigned", "Doing"},
        }

    def get_state_agent_map(self) -> dict[str, str]:
        return {
            "Taizi":    "taizi",
            "Zhongshu": "zhongshu",
            "Menxia":   "menxia",
            "Assigned": "shangshu",
            "Review":   "shangshu",
        }

    def validate_transition(self, from_state: str, to_state: str, context: dict | None = None) -> bool:
        allowed = self.get_transitions().get(from_state, set())
        if to_state not in allowed:
            return False
        # 封驳守卫：rejection_count < 3 才能再次封驳
        if from_state == "Menxia" and to_state == "Zhongshu":
            count = (context or {}).get("rejection_count", 0)
            return count < 3
        return True
