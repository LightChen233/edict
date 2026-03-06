"""总统制 — 强执行者治理模型。

流转: 用户 → 总统接收 → 咨询顾问团 → 总统拍板 → 部长执行 → 总统审查 → 完成
核心: 果断领导，有参谋但不受制约
"""

from .base import GovernanceModel, GovernanceType, FlowPattern, RoleDefinition


class ZongTongModel(GovernanceModel):
    """总统制 — 强执行者 + 顾问团。"""

    S_PENDING = "Pending"
    S_PRESIDENT_RECEIVED = "PresidentReceived"
    S_ADVISORY = "AdvisoryConsultation"
    S_PRESIDENT_DECISION = "PresidentDecision"
    S_CABINET_EXECUTION = "CabinetExecution"
    S_PRESIDENT_REVIEW = "PresidentReview"
    S_DONE = "Done"
    S_BLOCKED = "Blocked"
    S_CANCELLED = "Cancelled"

    @property
    def type(self) -> GovernanceType:
        return GovernanceType.ZONG_TONG

    @property
    def name(self) -> str:
        return "总统制"

    @property
    def dynasty(self) -> str:
        return "现代"

    @property
    def description(self) -> str:
        return (
            "总统制，总统拥有最终决定权，顾问团提供建议但不做决策。"
            "强执行导向，果断领导。适合需要快速决断且有方向感的任务。"
        )

    @property
    def flow_pattern(self) -> FlowPattern:
        return FlowPattern.EXECUTIVE_ADVISORY

    @property
    def suitable_for(self) -> list[str]:
        return ["快速决断", "方向明确的任务", "需要强领导力", "执行导向"]

    def get_states(self) -> list[str]:
        return [
            self.S_PENDING, self.S_PRESIDENT_RECEIVED, self.S_ADVISORY,
            self.S_PRESIDENT_DECISION, self.S_CABINET_EXECUTION,
            self.S_PRESIDENT_REVIEW, self.S_DONE, self.S_BLOCKED, self.S_CANCELLED,
        ]

    def get_initial_state(self) -> str:
        return self.S_PRESIDENT_RECEIVED

    def get_terminal_states(self) -> set[str]:
        return {self.S_DONE, self.S_CANCELLED}

    def get_transitions(self) -> dict[str, set[str]]:
        return {
            self.S_PRESIDENT_RECEIVED: {self.S_ADVISORY, self.S_PRESIDENT_DECISION, self.S_CANCELLED},
            self.S_ADVISORY: {self.S_PRESIDENT_DECISION, self.S_CANCELLED},
            self.S_PRESIDENT_DECISION: {self.S_CABINET_EXECUTION, self.S_CANCELLED},
            self.S_CABINET_EXECUTION: {self.S_PRESIDENT_REVIEW, self.S_DONE, self.S_BLOCKED, self.S_CANCELLED},
            self.S_PRESIDENT_REVIEW: {self.S_DONE, self.S_CABINET_EXECUTION, self.S_CANCELLED},
            self.S_BLOCKED: {self.S_PRESIDENT_RECEIVED, self.S_CABINET_EXECUTION},
        }

    def get_roles(self) -> list[RoleDefinition]:
        return [
            RoleDefinition("zongtong", "总统", "最高决策者，有最终决定权", "zhongshu"),
            RoleDefinition("guwen_a", "顾问甲", "提供专业建议", "menxia"),
            RoleDefinition("guwen_b", "顾问乙", "提供专业建议", "xingbu"),
            RoleDefinition("buzhang", "部长", "具体执行", "shangshu"),
        ]

    def get_state_agent_map(self) -> dict[str, str]:
        return {
            self.S_PRESIDENT_RECEIVED: "zhongshu",
            self.S_ADVISORY: "menxia",
            self.S_PRESIDENT_DECISION: "zhongshu",
            self.S_CABINET_EXECUTION: "shangshu",
            self.S_PRESIDENT_REVIEW: "zhongshu",
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
            "zhongshu": {"menxia", "xingbu", "shangshu"},
            "menxia": {"zhongshu"},
            "xingbu": {"zhongshu"},
            "shangshu": {"zhongshu", "hubu", "libu", "bingbu", "xingbu", "gongbu", "libu_hr"},
            "hubu": {"shangshu"},
            "libu": {"shangshu"},
            "bingbu": {"shangshu"},
            "gongbu": {"shangshu"},
            "libu_hr": {"shangshu"},
        }
