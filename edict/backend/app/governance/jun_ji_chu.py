"""军机处制 — 清代快速直报治理模型。

流转: 用户 → 军机大臣(快速研判) → 直接执行 → 快速复核 → 完成
核心: 小圈子直报、极简流程、信任驱动
"""

from .base import GovernanceModel, GovernanceType, FlowPattern, RoleDefinition


class JunJiChuModel(GovernanceModel):
    """军机处制 — 极简快速通道。"""

    S_PENDING = "Pending"
    S_COUNCIL_BRIEFING = "CouncilBriefing"
    S_QUICK_DECISION = "QuickDecision"
    S_DIRECT_EXECUTION = "DirectExecution"
    S_QUICK_REVIEW = "QuickReview"
    S_DONE = "Done"
    S_CANCELLED = "Cancelled"

    @property
    def type(self) -> GovernanceType:
        return GovernanceType.JUN_JI_CHU

    @property
    def name(self) -> str:
        return "军机处制"

    @property
    def dynasty(self) -> str:
        return "清"

    @property
    def description(self) -> str:
        return (
            "清代军机处制度，由2-3名军机大臣直接承接皇帝指令，"
            "跳过常规官僚体系，极速研判和执行。"
            "适合紧急任务、hotfix和关键事件响应。"
        )

    @property
    def flow_pattern(self) -> FlowPattern:
        return FlowPattern.FAST_TRACK

    @property
    def suitable_for(self) -> list[str]:
        return ["紧急任务", "hotfix", "关键事件响应", "时间敏感"]

    def get_states(self) -> list[str]:
        return [
            self.S_PENDING, self.S_COUNCIL_BRIEFING, self.S_QUICK_DECISION,
            self.S_DIRECT_EXECUTION, self.S_QUICK_REVIEW,
            self.S_DONE, self.S_CANCELLED,
        ]

    def get_initial_state(self) -> str:
        return self.S_COUNCIL_BRIEFING

    def get_terminal_states(self) -> set[str]:
        return {self.S_DONE, self.S_CANCELLED}

    def get_transitions(self) -> dict[str, set[str]]:
        return {
            self.S_COUNCIL_BRIEFING: {self.S_QUICK_DECISION, self.S_CANCELLED},
            self.S_QUICK_DECISION: {self.S_DIRECT_EXECUTION, self.S_CANCELLED},
            self.S_DIRECT_EXECUTION: {self.S_QUICK_REVIEW, self.S_DONE, self.S_CANCELLED},
            self.S_QUICK_REVIEW: {self.S_DONE, self.S_DIRECT_EXECUTION, self.S_CANCELLED},
        }

    def get_roles(self) -> list[RoleDefinition]:
        return [
            RoleDefinition("junji_dachen", "军机大臣", "皇帝最信任的决策顾问，快速研判和决策", "junji_dachen"),
            RoleDefinition("zhangjing", "军机章京", "处理文书和协调的辅助官员", "shangshu"),
            RoleDefinition("executor", "执行者", "直接执行（复用六部中最适合的）", None),
        ]

    def get_state_agent_map(self) -> dict[str, str]:
        return {
            self.S_COUNCIL_BRIEFING: "junji_dachen",
            self.S_QUICK_DECISION: "junji_dachen",
            self.S_DIRECT_EXECUTION: "shangshu",
            self.S_QUICK_REVIEW: "junji_dachen",
        }

    def get_org_agent_map(self) -> dict[str, str]:
        return {
            "户部": "hubu",
            "礼部": "libu",
            "兵部": "bingbu",
            "刑部": "xingbu",
            "工部": "gongbu",
            "吏部": "libu_hr",
        }

    def get_permission_matrix(self) -> dict[str, set[str]]:
        return {
            "junji_dachen": {"shangshu", "hubu", "libu", "bingbu", "xingbu", "gongbu", "libu_hr"},
            "shangshu": {"junji_dachen", "hubu", "libu", "bingbu", "xingbu", "gongbu", "libu_hr"},
            "hubu": {"junji_dachen", "shangshu"},
            "libu": {"junji_dachen", "shangshu"},
            "bingbu": {"junji_dachen", "shangshu"},
            "xingbu": {"junji_dachen", "shangshu"},
            "gongbu": {"junji_dachen", "shangshu"},
            "libu_hr": {"junji_dachen", "shangshu"},
        }
