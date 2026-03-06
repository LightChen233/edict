"""内阁制 — 明代集体票拟治理模型。

流转: 用户 → 首辅主持 → 阁臣集体票拟 → 司礼监批红 → 派发执行 → 汇总 → 完成
核心: 多Agent集体商议，票拟+批红双层决策
"""

from .base import GovernanceModel, GovernanceType, FlowPattern, RoleDefinition


class NeiGeModel(GovernanceModel):
    """内阁制 — 集体票拟 + 御批。"""

    S_PENDING = "Pending"
    S_CABINET_REVIEW = "CabinetReview"
    S_PIAO_NI = "PiaoNi"
    S_PI_HONG = "PiHong"
    S_DISPATCHED = "Dispatched"
    S_EXECUTING = "Executing"
    S_REPORT = "Report"
    S_DONE = "Done"
    S_BLOCKED = "Blocked"
    S_CANCELLED = "Cancelled"

    @property
    def type(self) -> GovernanceType:
        return GovernanceType.NEI_GE

    @property
    def name(self) -> str:
        return "内阁制"

    @property
    def dynasty(self) -> str:
        return "明"

    @property
    def description(self) -> str:
        return (
            "明代内阁制度，由首辅主持，多位大学士集体商议拟定方案（票拟），"
            "再由司礼监代皇帝批准（批红）。智慧汇聚，皇帝有最终否决权。"
            "适合重大决策和需要多视角分析的任务。"
        )

    @property
    def flow_pattern(self) -> FlowPattern:
        return FlowPattern.COLLECTIVE_DELIBERATION

    @property
    def suitable_for(self) -> list[str]:
        return ["重大决策", "多视角分析", "需要集体智慧", "战略规划"]

    def get_states(self) -> list[str]:
        return [
            self.S_PENDING, self.S_CABINET_REVIEW, self.S_PIAO_NI,
            self.S_PI_HONG, self.S_DISPATCHED, self.S_EXECUTING,
            self.S_REPORT, self.S_DONE, self.S_BLOCKED, self.S_CANCELLED,
        ]

    def get_initial_state(self) -> str:
        return self.S_CABINET_REVIEW

    def get_terminal_states(self) -> set[str]:
        return {self.S_DONE, self.S_CANCELLED}

    def get_transitions(self) -> dict[str, set[str]]:
        return {
            self.S_CABINET_REVIEW: {self.S_PIAO_NI, self.S_CANCELLED},
            self.S_PIAO_NI: {self.S_PI_HONG, self.S_CABINET_REVIEW, self.S_CANCELLED},
            self.S_PI_HONG: {self.S_DISPATCHED, self.S_PIAO_NI, self.S_CANCELLED},
            self.S_DISPATCHED: {self.S_EXECUTING, self.S_CANCELLED},
            self.S_EXECUTING: {self.S_REPORT, self.S_DONE, self.S_BLOCKED, self.S_CANCELLED},
            self.S_REPORT: {self.S_DONE, self.S_EXECUTING, self.S_CANCELLED},
            self.S_BLOCKED: {self.S_CABINET_REVIEW, self.S_DISPATCHED, self.S_EXECUTING},
        }

    def get_roles(self) -> list[RoleDefinition]:
        return [
            RoleDefinition("shoufu", "首辅", "内阁首席大学士，主持集体讨论", "shoufu"),
            RoleDefinition("gechen_a", "阁臣甲", "大学士，参与票拟讨论", "zhongshu"),
            RoleDefinition("gechen_b", "阁臣乙", "大学士，参与票拟讨论", "menxia"),
            RoleDefinition("silijian", "司礼监", "代皇帝批红，最终审批", "taizi"),
            RoleDefinition("executor", "执行官", "具体执行（复用六部）", None),
        ]

    def get_state_agent_map(self) -> dict[str, str]:
        return {
            self.S_CABINET_REVIEW: "shoufu",
            self.S_PIAO_NI: "shoufu",
            self.S_PI_HONG: "taizi",
            self.S_DISPATCHED: "shangshu",
            self.S_REPORT: "shoufu",
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
            "shoufu": {"zhongshu", "menxia", "taizi", "shangshu"},
            "zhongshu": {"shoufu", "menxia"},
            "menxia": {"shoufu", "zhongshu"},
            "taizi": {"shoufu"},
            "shangshu": {"shoufu", "hubu", "libu", "bingbu", "xingbu", "gongbu", "libu_hr"},
            "hubu": {"shangshu"},
            "libu": {"shangshu"},
            "bingbu": {"shangshu"},
            "xingbu": {"shangshu"},
            "gongbu": {"shangshu"},
            "libu_hr": {"shangshu"},
        }
