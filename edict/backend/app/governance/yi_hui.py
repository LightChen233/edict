"""议会制 — 辩论投票治理模型。

流转: 提案 → 一读 → 委员会审查 → 二读辩论 → 投票 → [通过→执行→完成] / [否决→修正→重提]
核心: 多方辩论、多数表决、允许修正案
"""

from .base import GovernanceModel, GovernanceType, FlowPattern, RoleDefinition


class YiHuiModel(GovernanceModel):
    """议会制 — 辩论 + 投票表决。"""

    S_PENDING = "Pending"
    S_PROPOSED = "Proposed"
    S_FIRST_READING = "FirstReading"
    S_COMMITTEE_REVIEW = "CommitteeReview"
    S_DEBATE = "Debate"
    S_VOTING = "Voting"
    S_PASSED = "Passed"
    S_REJECTED = "Rejected"
    S_EXECUTING = "Executing"
    S_DONE = "Done"
    S_CANCELLED = "Cancelled"

    @property
    def type(self) -> GovernanceType:
        return GovernanceType.YI_HUI

    @property
    def name(self) -> str:
        return "议会制"

    @property
    def dynasty(self) -> str:
        return "现代"

    @property
    def description(self) -> str:
        return (
            "议会民主制度，通过辩论和投票表决来决策。"
            "包含一读、委员会审查、二读辩论、投票等环节，"
            "反对方可质疑和挑战，允许修正案。适合技术选型和架构评审。"
        )

    @property
    def flow_pattern(self) -> FlowPattern:
        return FlowPattern.DEBATE_VOTE

    @property
    def suitable_for(self) -> list[str]:
        return ["架构设计", "技术选型", "有争议的决策", "方案评审"]

    def get_states(self) -> list[str]:
        return [
            self.S_PENDING, self.S_PROPOSED, self.S_FIRST_READING,
            self.S_COMMITTEE_REVIEW, self.S_DEBATE, self.S_VOTING,
            self.S_PASSED, self.S_REJECTED, self.S_EXECUTING,
            self.S_DONE, self.S_CANCELLED,
        ]

    def get_initial_state(self) -> str:
        return self.S_PROPOSED

    def get_terminal_states(self) -> set[str]:
        return {self.S_DONE, self.S_CANCELLED}

    def get_transitions(self) -> dict[str, set[str]]:
        return {
            self.S_PROPOSED: {self.S_FIRST_READING, self.S_CANCELLED},
            self.S_FIRST_READING: {self.S_COMMITTEE_REVIEW, self.S_CANCELLED},
            self.S_COMMITTEE_REVIEW: {self.S_DEBATE, self.S_PROPOSED, self.S_CANCELLED},
            self.S_DEBATE: {self.S_VOTING, self.S_COMMITTEE_REVIEW, self.S_CANCELLED},
            self.S_VOTING: {self.S_PASSED, self.S_REJECTED},
            self.S_PASSED: {self.S_EXECUTING},
            self.S_REJECTED: {self.S_PROPOSED, self.S_CANCELLED},
            self.S_EXECUTING: {self.S_DONE, self.S_CANCELLED},
        }

    def get_roles(self) -> list[RoleDefinition]:
        return [
            RoleDefinition("yizhang", "议长", "主持辩论，维持秩序，宣布投票结果", "yizhang"),
            RoleDefinition("proposer", "提案方", "提出方案并答辩", "zhongshu"),
            RoleDefinition("opposition", "反对方", "质疑和挑战方案", "menxia"),
            RoleDefinition("committee", "委员会", "深入审查特定方面", "xingbu"),
            RoleDefinition("executor", "执行方", "通过后执行（复用六部）", None),
        ]

    def get_state_agent_map(self) -> dict[str, str]:
        return {
            self.S_PROPOSED: "yizhang",
            self.S_FIRST_READING: "zhongshu",
            self.S_COMMITTEE_REVIEW: "xingbu",
            self.S_DEBATE: "yizhang",
            self.S_VOTING: "yizhang",
            self.S_PASSED: "shangshu",
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
            "yizhang": {"zhongshu", "menxia", "xingbu", "shangshu"},
            "zhongshu": {"yizhang", "menxia"},
            "menxia": {"yizhang", "zhongshu"},
            "xingbu": {"yizhang"},
            "shangshu": {"yizhang", "hubu", "libu", "bingbu", "xingbu", "gongbu", "libu_hr"},
            "hubu": {"shangshu"},
            "libu": {"shangshu"},
            "bingbu": {"shangshu"},
            "gongbu": {"shangshu"},
            "libu_hr": {"shangshu"},
        }
