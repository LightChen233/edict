"""丞相制 — 秦汉中央集权治理模型。

流转: 用户 → 丞相(规划+审核) → 派发属吏 → 执行 → 丞相审查 → 完成
核心: 单一权力中心，Hub-and-Spoke 模式，决策快、流程短
"""

from .base import GovernanceModel, GovernanceType, FlowPattern, RoleDefinition


class ChengXiangModel(GovernanceModel):
    """丞相制 — 中心辐射型，单一权力中心。"""

    S_PENDING = "Pending"
    S_CHANCELLOR = "Chancellor"
    S_DISPATCHED = "Dispatched"
    S_EXECUTING = "Executing"
    S_CHANCELLOR_REVIEW = "ChancellorReview"
    S_DONE = "Done"
    S_BLOCKED = "Blocked"
    S_CANCELLED = "Cancelled"

    @property
    def type(self) -> GovernanceType:
        return GovernanceType.CHENG_XIANG

    @property
    def name(self) -> str:
        return "丞相制"

    @property
    def dynasty(self) -> str:
        return "秦汉"

    @property
    def description(self) -> str:
        return (
            "秦汉时期的丞相制度，丞相为百官之长，集规划、决策、协调于一身。"
            "流程短、决策快，无独立审核层。适合简单/中等任务的快速交付。"
        )

    @property
    def flow_pattern(self) -> FlowPattern:
        return FlowPattern.HUB_SPOKE

    @property
    def suitable_for(self) -> list[str]:
        return ["简单任务", "快速交付", "中等复杂度", "追求效率"]

    def get_states(self) -> list[str]:
        return [
            self.S_PENDING, self.S_CHANCELLOR, self.S_DISPATCHED,
            self.S_EXECUTING, self.S_CHANCELLOR_REVIEW,
            self.S_DONE, self.S_BLOCKED, self.S_CANCELLED,
        ]

    def get_initial_state(self) -> str:
        return self.S_CHANCELLOR

    def get_terminal_states(self) -> set[str]:
        return {self.S_DONE, self.S_CANCELLED}

    def get_transitions(self) -> dict[str, set[str]]:
        return {
            self.S_CHANCELLOR: {self.S_DISPATCHED, self.S_CANCELLED, self.S_BLOCKED},
            self.S_DISPATCHED: {self.S_EXECUTING, self.S_CANCELLED},
            self.S_EXECUTING: {self.S_CHANCELLOR_REVIEW, self.S_DONE, self.S_BLOCKED, self.S_CANCELLED},
            self.S_CHANCELLOR_REVIEW: {self.S_DONE, self.S_EXECUTING, self.S_CANCELLED},
            self.S_BLOCKED: {self.S_CHANCELLOR, self.S_DISPATCHED, self.S_EXECUTING},
        }

    def get_roles(self) -> list[RoleDefinition]:
        return [
            RoleDefinition("chengxiang", "丞相", "百官之长，集规划/决策/协调于一身", "chengxiang"),
            RoleDefinition("shuli", "属吏", "具体执行的下属官员", None),
        ]

    def get_state_agent_map(self) -> dict[str, str]:
        return {
            self.S_CHANCELLOR: "chengxiang",
            self.S_DISPATCHED: "chengxiang",
            self.S_CHANCELLOR_REVIEW: "chengxiang",
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
            "chengxiang": {"hubu", "libu", "bingbu", "xingbu", "gongbu", "libu_hr"},
            "hubu": {"chengxiang"},
            "libu": {"chengxiang"},
            "bingbu": {"chengxiang"},
            "xingbu": {"chengxiang"},
            "gongbu": {"chengxiang"},
            "libu_hr": {"chengxiang"},
        }
