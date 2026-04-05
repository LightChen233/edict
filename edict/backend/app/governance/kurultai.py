"""蒙古忽里勒台制 (蒙古) — 威慑性强制共识 + 军事化执行。"""

from .base import GovernanceModel, GovernanceType


class KurultaiModel(GovernanceModel):
    type = GovernanceType.KURULTAI
    name = "忽里勒台制"
    description = "蒙古忽里勒台：强制召集各部落首领→威慑性协商（异见者承担后果）→强制共识→军事化执行→朝贡汇报"
    dynasty = "蒙古"
    topology = "coercive-consensus"

    def get_states(self) -> list[str]:
        return [
            "Pending", "Summons", "Kurultai",
            "Deliberation", "Consensus", "Decree",
            "MilitaryExec", "TributeReport", "Done", "Cancelled"
        ]

    def get_initial_state(self) -> str:
        return "Pending"

    def get_terminal_states(self) -> set[str]:
        return {"Done", "Cancelled"}

    def get_transitions(self) -> dict[str, set[str]]:
        return {
            "Pending":       {"Summons", "Cancelled"},
            "Summons":       {"Kurultai", "Cancelled"},
            "Kurultai":      {"Deliberation", "Cancelled"},
            "Deliberation":  {"Consensus", "Deliberation", "Cancelled"},  # 未达共识→继续协商
            "Consensus":     {"Decree", "Cancelled"},
            "Decree":        {"MilitaryExec", "Cancelled"},
            "MilitaryExec":  {"TributeReport", "Cancelled"},
            "TributeReport": {"Done", "MilitaryExec", "Cancelled"},       # 汇报不足→继续执行
        }

    def get_state_agent_map(self) -> dict[str, str]:
        return {
            "Pending":       "taizi",
            "Summons":       "tianzi",
            "Kurultai":      "tianzi",
            "Deliberation":  "lord",
            "Consensus":     "tianzi",
            "Decree":        "tianzi",
            "MilitaryExec":  "lord",
            "TributeReport": "tianzi",
        }

    def validate_transition(self, from_state: str, to_state: str, context: dict | None = None) -> bool:
        allowed = self.get_transitions().get(from_state, set())
        if to_state not in allowed:
            return False
        ctx = context or {}
        # 强制出席守卫：absent_chiefs > 0 时不能进入 Deliberation
        if from_state == "Kurultai" and to_state == "Deliberation":
            return ctx.get("absent_chiefs", 0) == 0
        # 威慑共识守卫：dissent_count==0（异见者已被处理）才能进入 Consensus
        if from_state == "Deliberation" and to_state == "Consensus":
            return ctx.get("dissent_count", 0) == 0
        # 继续协商守卫：还有异见且未超过最大轮次
        if from_state == "Deliberation" and to_state == "Deliberation":
            return (ctx.get("dissent_count", 0) > 0 and
                    ctx.get("deliberation_rounds", 0) < ctx.get("max_rounds", 3))
        # 汇报不足守卫
        if from_state == "TributeReport" and to_state == "MilitaryExec":
            return not ctx.get("tribute_sufficient", True)
        return True
