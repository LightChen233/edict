"""议会制 (现代) — 辩论+投票，多数阈值硬约束。"""

from .base import GovernanceModel, GovernanceType


class YiHuiModel(GovernanceModel):
    type = GovernanceType.YI_HUI
    name = "议会制"
    description = "现代议会制：委员会并发审查→辩论→投票（可配置多数阈值）→修正案循环≤3轮"
    dynasty = "现代"
    topology = "debate-vote"

    def get_states(self) -> list[str]:
        return ["Pending", "Committee", "Debate", "Vote", "Amendment", "Assigned", "Doing", "Done", "Cancelled"]

    def get_initial_state(self) -> str:
        return "Pending"

    def get_terminal_states(self) -> set[str]:
        return {"Done", "Cancelled"}

    def get_transitions(self) -> dict[str, set[str]]:
        return {
            "Pending":   {"Committee", "Cancelled"},
            "Committee": {"Debate", "Cancelled"},
            "Debate":    {"Vote", "Cancelled"},
            "Vote":      {"Assigned", "Amendment", "Cancelled"},  # 否决→修正案
            "Amendment": {"Debate", "Cancelled"},                  # 修正案→重新辩论
            "Assigned":  {"Doing", "Cancelled"},
            "Doing":     {"Done", "Cancelled"},
        }

    def get_state_agent_map(self) -> dict[str, str]:
        return {
            "Pending":   "taizi",
            "Committee": "yizhang",
            "Debate":    "yizhang",
            "Vote":      "system",
            "Amendment": "yizhang",
            "Assigned":  "shangshu",
            "Doing":     "shangshu",
        }

    def validate_transition(self, from_state: str, to_state: str, context: dict | None = None) -> bool:
        allowed = self.get_transitions().get(from_state, set())
        if to_state not in allowed:
            return False
        # 修正案循环守卫：最多3轮
        if from_state == "Vote" and to_state == "Amendment":
            return (context or {}).get("amendment_count", 0) < 3
        return True
