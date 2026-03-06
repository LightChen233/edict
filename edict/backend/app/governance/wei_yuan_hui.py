"""委员会制 — 扁平化集体领导治理模型。

流转: 用户 → 委员会接收 → 全体讨论 → 共识决策 → 集体执行 → 总结 → 完成
核心: 无等级、纯共识、集体负责
"""

from .base import GovernanceModel, GovernanceType, FlowPattern, RoleDefinition


class WeiYuanHuiModel(GovernanceModel):
    """委员会制 — 扁平化集体领导。"""

    S_PENDING = "Pending"
    S_COMMITTEE_RECEIVED = "CommitteeReceived"
    S_DISCUSSION = "Discussion"
    S_CONSENSUS = "Consensus"
    S_COLLECTIVE_EXECUTION = "CollectiveExecution"
    S_SUMMARY = "Summary"
    S_DONE = "Done"
    S_BLOCKED = "Blocked"
    S_CANCELLED = "Cancelled"

    @property
    def type(self) -> GovernanceType:
        return GovernanceType.WEI_YUAN_HUI

    @property
    def name(self) -> str:
        return "委员会制"

    @property
    def dynasty(self) -> str:
        return "现代"

    @property
    def description(self) -> str:
        return (
            "委员会集体领导制度，所有成员地位平等，轮值主席主持但无特权。"
            "通过充分讨论达成共识后集体执行。"
            "适合头脑风暴、研究型任务和创意工作。"
        )

    @property
    def flow_pattern(self) -> FlowPattern:
        return FlowPattern.FLAT_CONSENSUS

    @property
    def suitable_for(self) -> list[str]:
        return ["头脑风暴", "研究型任务", "创意工作", "需要多方参与"]

    def get_states(self) -> list[str]:
        return [
            self.S_PENDING, self.S_COMMITTEE_RECEIVED, self.S_DISCUSSION,
            self.S_CONSENSUS, self.S_COLLECTIVE_EXECUTION, self.S_SUMMARY,
            self.S_DONE, self.S_BLOCKED, self.S_CANCELLED,
        ]

    def get_initial_state(self) -> str:
        return self.S_COMMITTEE_RECEIVED

    def get_terminal_states(self) -> set[str]:
        return {self.S_DONE, self.S_CANCELLED}

    def get_transitions(self) -> dict[str, set[str]]:
        return {
            self.S_COMMITTEE_RECEIVED: {self.S_DISCUSSION, self.S_CANCELLED},
            self.S_DISCUSSION: {self.S_CONSENSUS, self.S_CANCELLED, self.S_BLOCKED},
            self.S_CONSENSUS: {self.S_COLLECTIVE_EXECUTION, self.S_DISCUSSION, self.S_CANCELLED},
            self.S_COLLECTIVE_EXECUTION: {self.S_SUMMARY, self.S_DONE, self.S_BLOCKED, self.S_CANCELLED},
            self.S_SUMMARY: {self.S_DONE, self.S_COLLECTIVE_EXECUTION, self.S_CANCELLED},
            self.S_BLOCKED: {self.S_COMMITTEE_RECEIVED, self.S_DISCUSSION, self.S_COLLECTIVE_EXECUTION},
        }

    def get_roles(self) -> list[RoleDefinition]:
        return [
            RoleDefinition("lunzhi_zhuxi", "轮值主席", "轮流主持讨论，无特权", "zhongshu"),
            RoleDefinition("weiyuan_a", "委员甲", "平等参与讨论和执行", "menxia"),
            RoleDefinition("weiyuan_b", "委员乙", "平等参与讨论和执行", "shangshu"),
            RoleDefinition("weiyuan_c", "委员丙", "平等参与讨论和执行", "gongbu"),
        ]

    def get_state_agent_map(self) -> dict[str, str]:
        return {
            self.S_COMMITTEE_RECEIVED: "zhongshu",
            self.S_DISCUSSION: "zhongshu",
            self.S_CONSENSUS: "menxia",
            self.S_SUMMARY: "shangshu",
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
            "zhongshu": {"menxia", "shangshu", "gongbu"},
            "menxia": {"zhongshu", "shangshu", "gongbu"},
            "shangshu": {"zhongshu", "menxia", "gongbu", "hubu", "libu", "bingbu", "xingbu", "libu_hr"},
            "gongbu": {"zhongshu", "menxia", "shangshu"},
            "hubu": {"shangshu"},
            "libu": {"shangshu"},
            "bingbu": {"shangshu"},
            "xingbu": {"shangshu"},
            "libu_hr": {"shangshu"},
        }
