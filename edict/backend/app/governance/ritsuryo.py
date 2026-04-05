"""日本令制 (奈良) — 三省六部变形，太政官凌驾三省，对照组。"""

from .base import GovernanceModel, GovernanceType


class RitsuryoModel(GovernanceModel):
    type = GovernanceType.RITSURYO
    name = "令制"
    description = "日本奈良令制：太政官凌驾三省→中纳言规划→参议审议（权力弱于门下）→弁官局派发→国司地方执行"
    dynasty = "日本奈良"
    topology = "modified-pipeline"  # 与三省六部同源但太政官打破制衡，作为对照组

    def get_states(self) -> list[str]:
        return [
            "Pending", "Dajokan", "Chunagon",
            "Sangi", "Benkan", "Executing", "Zuryo", "Done", "Cancelled"
        ]

    def get_initial_state(self) -> str:
        return "Pending"

    def get_terminal_states(self) -> set[str]:
        return {"Done", "Cancelled"}

    def get_transitions(self) -> dict[str, set[str]]:
        return {
            "Pending":    {"Dajokan", "Cancelled"},
            "Dajokan":    {"Chunagon", "Executing", "Cancelled"},  # 太政官可绕过三省直接执行
            "Chunagon":   {"Sangi", "Dajokan", "Cancelled"},       # 退回太政官重审
            "Sangi":      {"Benkan", "Chunagon", "Cancelled"},     # 参议审议（弱封驳）
            "Benkan":     {"Executing", "Cancelled"},
            "Executing":  {"Zuryo", "Done", "Cancelled"},
            "Zuryo":      {"Done", "Executing", "Cancelled"},      # 国司执行不力→重做
        }

    def get_state_agent_map(self) -> dict[str, str]:
        return {
            "Pending":   "taizi",
            "Dajokan":   "dajokan",    # 太政官，凌驾三省
            "Chunagon":  "zhongshu",   # 中纳言≈中书
            "Sangi":     "menxia",     # 参议≈门下（但权力更弱）
            "Benkan":    "shangshu",   # 弁官局≈尚书
            "Executing": "shangshu",
            "Zuryo":     "lord",       # 国司≈地方官
        }

    def validate_transition(self, from_state: str, to_state: str, context: dict | None = None) -> bool:
        allowed = self.get_transitions().get(from_state, set())
        if to_state not in allowed:
            return False
        ctx = context or {}
        # 太政官绕过守卫：dajokan_override=True 时可跳过三省直接执行（无 context 时不允许绕过）
        if from_state == "Dajokan" and to_state == "Executing":
            return ctx.get("dajokan_override", False)
        # 参议弱封驳守卫：只有 quality_score < 5 才退回（比门下省宽松，无 context 默认放行）
        if from_state == "Sangi" and to_state == "Chunagon":
            return ctx.get("quality_score", 10) < 5
        if from_state == "Dajokan" and to_state == "Executing":
            return ctx.get("dajokan_override", False)
        # 国司执行不力守卫
        if from_state == "Zuryo" and to_state == "Executing":
            return not ctx.get("zuryo_passed", True)
        return True
