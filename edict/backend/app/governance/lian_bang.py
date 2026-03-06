"""联邦制 — 多级治理模型。

流转: 用户 → 联邦接收 → 分配州 → 州自治执行 → 联邦协调 → 汇总 → 完成
核心: 中央与地方的平衡，跨域协调
"""

from .base import GovernanceModel, GovernanceType, FlowPattern, RoleDefinition


class LianBangModel(GovernanceModel):
    """联邦制 — 多级治理。"""

    S_PENDING = "Pending"
    S_FEDERAL_RECEIVED = "FederalReceived"
    S_STATE_ASSIGNMENT = "StateAssignment"
    S_STATE_AUTONOMOUS = "StateAutonomous"
    S_FEDERAL_COORDINATION = "FederalCoordination"
    S_SUMMARY = "Summary"
    S_DONE = "Done"
    S_BLOCKED = "Blocked"
    S_CANCELLED = "Cancelled"

    @property
    def type(self) -> GovernanceType:
        return GovernanceType.LIAN_BANG

    @property
    def name(self) -> str:
        return "联邦制"

    @property
    def dynasty(self) -> str:
        return "现代"

    @property
    def description(self) -> str:
        return (
            "联邦制度，联邦政府负责跨域协调和全局规则，"
            "州政府在各自领域内自治执行。中央与地方的平衡。"
            "适合复杂的跨领域任务，既需协调又需自主。"
        )

    @property
    def flow_pattern(self) -> FlowPattern:
        return FlowPattern.MULTI_LEVEL

    @property
    def suitable_for(self) -> list[str]:
        return ["跨领域协作", "中央与地方平衡", "复杂系统", "多团队协作"]

    def get_states(self) -> list[str]:
        return [
            self.S_PENDING, self.S_FEDERAL_RECEIVED, self.S_STATE_ASSIGNMENT,
            self.S_STATE_AUTONOMOUS, self.S_FEDERAL_COORDINATION,
            self.S_SUMMARY, self.S_DONE, self.S_BLOCKED, self.S_CANCELLED,
        ]

    def get_initial_state(self) -> str:
        return self.S_FEDERAL_RECEIVED

    def get_terminal_states(self) -> set[str]:
        return {self.S_DONE, self.S_CANCELLED}

    def get_transitions(self) -> dict[str, set[str]]:
        return {
            self.S_FEDERAL_RECEIVED: {self.S_STATE_ASSIGNMENT, self.S_CANCELLED},
            self.S_STATE_ASSIGNMENT: {self.S_STATE_AUTONOMOUS, self.S_CANCELLED},
            self.S_STATE_AUTONOMOUS: {
                self.S_FEDERAL_COORDINATION, self.S_SUMMARY,
                self.S_DONE, self.S_BLOCKED, self.S_CANCELLED,
            },
            self.S_FEDERAL_COORDINATION: {self.S_STATE_AUTONOMOUS, self.S_SUMMARY, self.S_CANCELLED},
            self.S_SUMMARY: {self.S_DONE, self.S_STATE_AUTONOMOUS, self.S_CANCELLED},
            self.S_BLOCKED: {self.S_FEDERAL_RECEIVED, self.S_STATE_AUTONOMOUS},
        }

    def get_roles(self) -> list[RoleDefinition]:
        return [
            RoleDefinition("lianbang", "联邦政府", "跨域协调、全局规则制定", "zhongshu"),
            RoleDefinition("zhou_a", "州政府甲", "域内自治执行", "gongbu"),
            RoleDefinition("zhou_b", "州政府乙", "域内自治执行", "bingbu"),
            RoleDefinition("zhou_c", "州政府丙", "域内自治执行", "hubu"),
        ]

    def get_state_agent_map(self) -> dict[str, str]:
        return {
            self.S_FEDERAL_RECEIVED: "zhongshu",
            self.S_STATE_ASSIGNMENT: "shangshu",
            self.S_FEDERAL_COORDINATION: "zhongshu",
            self.S_SUMMARY: "zhongshu",
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
            "zhongshu": {"shangshu", "gongbu", "bingbu", "hubu", "libu", "xingbu", "libu_hr"},
            "shangshu": {"zhongshu", "gongbu", "bingbu", "hubu", "libu", "xingbu", "libu_hr"},
            "gongbu": {"zhongshu", "shangshu"},
            "bingbu": {"zhongshu", "shangshu"},
            "hubu": {"zhongshu", "shangshu"},
            "libu": {"zhongshu", "shangshu"},
            "xingbu": {"zhongshu", "shangshu"},
            "libu_hr": {"zhongshu", "shangshu"},
        }
