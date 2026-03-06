"""分封制 — 周代去中心化治理模型。

流转: 用户 → 天子分封 → 诸侯自治(独立规划+执行) → 朝贡回报 → 完成
核心: 高度自治、松耦合、各领域独立运行
"""

from .base import GovernanceModel, GovernanceType, FlowPattern, RoleDefinition


class FengJianModel(GovernanceModel):
    """分封制 — 去中心化自治。"""

    S_PENDING = "Pending"
    S_ENFEOFFED = "Enfeoffed"
    S_LORD_PLANNING = "LordPlanning"
    S_LORD_EXECUTING = "LordExecuting"
    S_TRIBUTE_REPORT = "TributeReport"
    S_DONE = "Done"
    S_BLOCKED = "Blocked"
    S_CANCELLED = "Cancelled"

    @property
    def type(self) -> GovernanceType:
        return GovernanceType.FENG_JIAN

    @property
    def name(self) -> str:
        return "分封制"

    @property
    def dynasty(self) -> str:
        return "周"

    @property
    def description(self) -> str:
        return (
            "西周分封制度，天子将领地分封给诸侯，诸侯在领地内有完全自治权，"
            "只需定期朝贡回报。去中心化、高度自治。"
            "适合多项目并行管理和独立模块开发。"
        )

    @property
    def flow_pattern(self) -> FlowPattern:
        return FlowPattern.DECENTRALIZED

    @property
    def suitable_for(self) -> list[str]:
        return ["多项目并行", "模块独立开发", "微服务架构", "松耦合协作"]

    def get_states(self) -> list[str]:
        return [
            self.S_PENDING, self.S_ENFEOFFED, self.S_LORD_PLANNING,
            self.S_LORD_EXECUTING, self.S_TRIBUTE_REPORT,
            self.S_DONE, self.S_BLOCKED, self.S_CANCELLED,
        ]

    def get_initial_state(self) -> str:
        return self.S_ENFEOFFED

    def get_terminal_states(self) -> set[str]:
        return {self.S_DONE, self.S_CANCELLED}

    def get_transitions(self) -> dict[str, set[str]]:
        return {
            self.S_ENFEOFFED: {self.S_LORD_PLANNING, self.S_CANCELLED},
            self.S_LORD_PLANNING: {self.S_LORD_EXECUTING, self.S_CANCELLED, self.S_BLOCKED},
            self.S_LORD_EXECUTING: {self.S_TRIBUTE_REPORT, self.S_DONE, self.S_BLOCKED, self.S_CANCELLED},
            self.S_TRIBUTE_REPORT: {self.S_DONE, self.S_LORD_EXECUTING, self.S_CANCELLED},
            self.S_BLOCKED: {self.S_ENFEOFFED, self.S_LORD_PLANNING, self.S_LORD_EXECUTING},
        }

    def get_roles(self) -> list[RoleDefinition]:
        return [
            RoleDefinition("tianzi", "天子", "最高统治者，分封领地、接受朝贡", "tianzi"),
            RoleDefinition("zhuhou", "诸侯", "领地自治者，独立规划和执行", None),
        ]

    def get_state_agent_map(self) -> dict[str, str]:
        return {
            self.S_ENFEOFFED: "tianzi",
            self.S_TRIBUTE_REPORT: "tianzi",
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
            "tianzi": {"hubu", "libu", "bingbu", "xingbu", "gongbu", "libu_hr"},
            "hubu": {"tianzi"},
            "libu": {"tianzi"},
            "bingbu": {"tianzi"},
            "xingbu": {"tianzi"},
            "gongbu": {"tianzi"},
            "libu_hr": {"tianzi"},
        }
