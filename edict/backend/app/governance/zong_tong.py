"""总统制 (现代) — 顾问团并发咨询 + 总统拍板，可否决重做。"""

from .base import GovernanceModel, GovernanceType


class ZongTongModel(GovernanceModel):
    type = GovernanceType.ZONG_TONG
    name = "总统制"
    description = "现代总统制：顾问团并发提交建议→总统收齐后拍板→可否决执行结果要求重做"
    dynasty = "现代"
    topology = "hub-advisors"

    def get_states(self) -> list[str]:
        return ["Pending", "Advisory", "Decision", "Doing", "Review", "Done", "Cancelled"]

    def get_initial_state(self) -> str:
        return "Pending"

    def get_terminal_states(self) -> set[str]:
        return {"Done", "Cancelled"}

    def get_transitions(self) -> dict[str, set[str]]:
        return {
            "Pending":  {"Advisory", "Cancelled"},
            "Advisory": {"Decision", "Cancelled"},
            "Decision": {"Doing", "Cancelled"},
            "Doing":    {"Review", "Cancelled"},
            "Review":   {"Done", "Doing", "Cancelled"},  # 否决→重做
        }

    def get_state_agent_map(self) -> dict[str, str]:
        return {
            "Pending":  "taizi",
            "Advisory": "advisor",
            "Decision": "zongtong",
            "Doing":    "shangshu",
            "Review":   "zongtong",
        }

    def validate_transition(self, from_state: str, to_state: str, context: dict | None = None) -> bool:
        allowed = self.get_transitions().get(from_state, set())
        if to_state not in allowed:
            return False
        # 顾问收齐守卫：所有顾问提交后才能进入 Decision
        if from_state == "Advisory" and to_state == "Decision":
            ctx = context or {}
            expected = ctx.get("advisor_count", 1)
            received = ctx.get("advisor_responses", 0)
            return received >= expected
        # 否决重做守卫：总统明确否决（veto=True）才退回 Doing
        if from_state == "Review" and to_state == "Doing":
            return (context or {}).get("veto", False)
        return True
