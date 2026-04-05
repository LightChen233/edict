"""威尼斯共和国制 (中世纪) — 多层嵌套委员会，刻意复杂化防止权力集中。"""

from .base import GovernanceModel, GovernanceType


class VenetianModel(GovernanceModel):
    type = GovernanceType.VENETIAN
    name = "威尼斯共和国制"
    description = "中世纪威尼斯：大议会提名→多轮抽签+投票混合选举→小议会审查→十人委员会安全审查→总督提案（无实权）→执行→审计"
    dynasty = "中世纪威尼斯"
    topology = "nested-committees"

    def get_states(self) -> list[str]:
        return [
            "Pending", "GrandCouncil", "Balloting",
            "SmallCouncil", "TenCouncil", "DogeProposes",
            "Executing", "Audit", "Done", "Cancelled"
        ]

    def get_initial_state(self) -> str:
        return "Pending"

    def get_terminal_states(self) -> set[str]:
        return {"Done", "Cancelled"}

    def get_transitions(self) -> dict[str, set[str]]:
        return {
            "Pending":      {"GrandCouncil", "Cancelled"},
            "GrandCouncil": {"Balloting", "Cancelled"},
            "Balloting":    {"SmallCouncil", "GrandCouncil", "Cancelled"},  # 选举失败→重新提名
            "SmallCouncil": {"TenCouncil", "GrandCouncil", "Cancelled"},    # 审查不通过→重提名
            "TenCouncil":   {"DogeProposes", "Cancelled"},                  # 安全否决→直接取消
            "DogeProposes": {"Executing", "SmallCouncil", "Cancelled"},     # 小议会可否决总督
            "Executing":    {"Audit", "Cancelled"},
            "Audit":        {"Done", "Executing", "Cancelled"},
        }

    def get_state_agent_map(self) -> dict[str, str]:
        return {
            "Pending":      "taizi",
            "GrandCouncil": "grand_council",
            "Balloting":    "system",         # 抽签+投票混合
            "SmallCouncil": "small_council",
            "TenCouncil":   "ten_council",
            "DogeProposes": "doge",           # 总督，象征性角色
            "Executing":    "shangshu",
            "Audit":        "auditor",
        }

    def validate_transition(self, from_state: str, to_state: str, context: dict | None = None) -> bool:
        allowed = self.get_transitions().get(from_state, set())
        if to_state not in allowed:
            return False
        ctx = context or {}
        # 抽签+投票通过守卫：需要通过随机轮次（无 context 时默认通过）
        if from_state == "Balloting" and to_state == "SmallCouncil":
            return ctx.get("balloting_passed", True)
        # 十人委员会安全否决：security_threat=True 直接取消
        if from_state == "TenCouncil" and to_state == "Cancelled":
            return ctx.get("security_threat", False)
        # 防集权守卫：任何单一 agent 不能连续主导超过 max_consecutive 个状态（无 context 时不触发）
        if ctx.get("power_concentration_detected", False):
            return to_state == "Cancelled"
        return True
