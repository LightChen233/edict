"""罗马元老院制 (古罗马) — 双执政官互相否决 + 元老院咨询 + 独裁官紧急机制。"""

from .base import GovernanceModel, GovernanceType


class RomanModel(GovernanceModel):
    type = GovernanceType.ROMAN
    name = "罗马元老院制"
    description = "古罗马：元老院咨询→执政官A决策→执政官B可否决（互相制衡）→执行→凯旋/弹劾"
    dynasty = "古罗马"
    topology = "dual-veto"

    def get_states(self) -> list[str]:
        return [
            "Pending", "SenateConsult", "ConsulDecision",
            "ConsulVeto", "Executing", "TriumphCensure", "Done", "Cancelled"
        ]

    def get_initial_state(self) -> str:
        return "Pending"

    def get_terminal_states(self) -> set[str]:
        return {"Done", "Cancelled"}

    def get_transitions(self) -> dict[str, set[str]]:
        return {
            "Pending":        {"SenateConsult", "Executing", "Cancelled"},  # 紧急→独裁官直接执行
            "SenateConsult":  {"ConsulDecision", "Cancelled"},
            "ConsulDecision": {"ConsulVeto", "Executing", "Cancelled"},
            "ConsulVeto":     {"ConsulDecision", "Cancelled"},              # 否决→重新决策
            "Executing":      {"TriumphCensure", "Cancelled"},
            "TriumphCensure": {"Done", "Cancelled"},
        }

    def get_state_agent_map(self) -> dict[str, str]:
        return {
            "Pending":        "taizi",
            "SenateConsult":  "senate",
            "ConsulDecision": "consul_a",
            "ConsulVeto":     "consul_b",
            "Executing":      "shangshu",
            "TriumphCensure": "senate",
        }

    def validate_transition(self, from_state: str, to_state: str, context: dict | None = None) -> bool:
        allowed = self.get_transitions().get(from_state, set())
        if to_state not in allowed:
            return False
        ctx = context or {}
        # 独裁官紧急机制：emergency=True 时跳过元老院直接执行
        if from_state == "Pending" and to_state == "Executing":
            return ctx.get("emergency", False)
        # 执政官B否决守卫：consul_b_veto=True 才触发
        if from_state == "ConsulDecision" and to_state == "ConsulVeto":
            return ctx.get("consul_b_veto", False)
        # 否决后重议守卫：veto_count < 2（任期内最多否决2次）
        if from_state == "ConsulVeto" and to_state == "ConsulDecision":
            return ctx.get("veto_count", 0) < 2
        # 任期制守卫：term_expired=True 时强制结束
        if to_state == "Cancelled" and ctx.get("term_expired", False):
            return True
        return True
