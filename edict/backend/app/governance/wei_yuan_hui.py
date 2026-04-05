"""委员会制 (现代) — 扁平共识，轮值主席，死锁检测。"""

from .base import GovernanceModel, GovernanceType


class WeiYuanHuiModel(GovernanceModel):
    type = GovernanceType.WEI_YUAN_HUI
    name = "委员会制"
    description = "现代委员会制：轮值主席主持→全员共识讨论→死锁时强制投票打破僵局"
    dynasty = "现代"
    topology = "flat-consensus"

    def get_states(self) -> list[str]:
        return ["Pending", "Discussion", "Consensus", "Voting", "Assigned", "Doing", "Done", "Cancelled"]

    def get_initial_state(self) -> str:
        return "Pending"

    def get_terminal_states(self) -> set[str]:
        return {"Done", "Cancelled"}

    def get_transitions(self) -> dict[str, set[str]]:
        return {
            "Pending":    {"Discussion", "Cancelled"},
            "Discussion": {"Consensus", "Voting", "Cancelled"},  # 死锁→强制投票
            "Consensus":  {"Assigned", "Discussion", "Cancelled"},
            "Voting":     {"Assigned", "Cancelled"},
            "Assigned":   {"Doing", "Cancelled"},
            "Doing":      {"Done", "Cancelled"},
        }

    def get_state_agent_map(self) -> dict[str, str]:
        return {
            "Pending":    "taizi",
            "Discussion": "weiyuanhui",
            "Consensus":  "weiyuanhui",
            "Voting":     "system",
            "Assigned":   "shangshu",
            "Doing":      "shangshu",
        }

    def validate_transition(self, from_state: str, to_state: str, context: dict | None = None) -> bool:
        allowed = self.get_transitions().get(from_state, set())
        if to_state not in allowed:
            return False
        # 共识守卫：dissent_count==0 才能进入 Consensus，否则继续讨论
        if from_state == "Discussion" and to_state == "Consensus":
            return (context or {}).get("dissent_count", 0) == 0
        # 死锁检测：讨论轮次超过 max_rounds 才能强制投票
        if from_state == "Discussion" and to_state == "Voting":
            ctx = context or {}
            return ctx.get("discussion_rounds", 0) >= ctx.get("max_rounds", 5)
        return True
