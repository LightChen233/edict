"""三省六部制 — 唐代分权制衡治理模型。

流转: 太子 → 中书省 → 门下省 → 尚书省 → 六部 → 审查 → 完成
核心: 起草/审核/执行三权分立，门下省可封驳（最多3轮）
"""

from .base import GovernanceModel, GovernanceType, FlowPattern, RoleDefinition


class SanShengModel(GovernanceModel):
    """三省六部制 — 线性流水线 + 强制审核关卡。"""

    # ── 状态常量 ──
    S_PENDING = "Pending"
    S_TAIZI = "Taizi"
    S_ZHONGSHU = "Zhongshu"
    S_MENXIA = "Menxia"
    S_ASSIGNED = "Assigned"
    S_NEXT = "Next"
    S_DOING = "Doing"
    S_REVIEW = "Review"
    S_DONE = "Done"
    S_BLOCKED = "Blocked"
    S_CANCELLED = "Cancelled"

    @property
    def type(self) -> GovernanceType:
        return GovernanceType.SAN_SHENG

    @property
    def name(self) -> str:
        return "三省六部制"

    @property
    def dynasty(self) -> str:
        return "唐"

    @property
    def description(self) -> str:
        return (
            "隋唐确立的中央行政制度。中书省起草、门下省审核、尚书省执行，"
            "三权分立、制度性审核（门下可封驳）。适合复杂任务的高质量保证。"
        )

    @property
    def flow_pattern(self) -> FlowPattern:
        return FlowPattern.LINEAR

    @property
    def suitable_for(self) -> list[str]:
        return ["复杂任务", "高质量保证", "需要审核把关", "多环节协作"]

    def get_states(self) -> list[str]:
        return [
            self.S_PENDING, self.S_TAIZI, self.S_ZHONGSHU, self.S_MENXIA,
            self.S_ASSIGNED, self.S_NEXT, self.S_DOING, self.S_REVIEW,
            self.S_DONE, self.S_BLOCKED, self.S_CANCELLED,
        ]

    def get_initial_state(self) -> str:
        return self.S_TAIZI

    def get_terminal_states(self) -> set[str]:
        return {self.S_DONE, self.S_CANCELLED}

    def get_transitions(self) -> dict[str, set[str]]:
        return {
            self.S_TAIZI: {self.S_ZHONGSHU, self.S_CANCELLED},
            self.S_ZHONGSHU: {self.S_MENXIA, self.S_CANCELLED, self.S_BLOCKED},
            self.S_MENXIA: {self.S_ASSIGNED, self.S_ZHONGSHU, self.S_CANCELLED},
            self.S_ASSIGNED: {self.S_DOING, self.S_NEXT, self.S_CANCELLED, self.S_BLOCKED},
            self.S_NEXT: {self.S_DOING, self.S_CANCELLED},
            self.S_DOING: {self.S_REVIEW, self.S_DONE, self.S_BLOCKED, self.S_CANCELLED},
            self.S_REVIEW: {self.S_DONE, self.S_DOING, self.S_CANCELLED},
            self.S_BLOCKED: {
                self.S_TAIZI, self.S_ZHONGSHU, self.S_MENXIA,
                self.S_ASSIGNED, self.S_DOING,
            },
        }

    def get_roles(self) -> list[RoleDefinition]:
        return [
            RoleDefinition("taizi", "太子", "消息分拣、需求整理", "taizi"),
            RoleDefinition("zhongshu", "中书省", "接旨、规划、拆解", "zhongshu"),
            RoleDefinition("menxia", "门下省", "审议、把关、封驳", "menxia"),
            RoleDefinition("shangshu", "尚书省", "派发、协调、汇总", "shangshu"),
            RoleDefinition("hubu", "户部", "数据、资源、核算", "hubu"),
            RoleDefinition("libu", "礼部", "文档、规范、报告", "libu"),
            RoleDefinition("bingbu", "兵部", "代码、算法、巡检", "bingbu"),
            RoleDefinition("xingbu", "刑部", "安全、合规、审计", "xingbu"),
            RoleDefinition("gongbu", "工部", "CI/CD、部署、工具", "gongbu"),
            RoleDefinition("libu_hr", "吏部", "人事、Agent管理", "libu_hr"),
        ]

    def get_state_agent_map(self) -> dict[str, str]:
        return {
            self.S_TAIZI: "taizi",
            self.S_ZHONGSHU: "zhongshu",
            self.S_MENXIA: "menxia",
            self.S_ASSIGNED: "shangshu",
            self.S_REVIEW: "shangshu",
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
            "taizi": {"zhongshu"},
            "zhongshu": {"taizi", "menxia", "shangshu"},
            "menxia": {"zhongshu", "shangshu"},
            "shangshu": {"zhongshu", "menxia", "hubu", "libu", "bingbu", "xingbu", "gongbu", "libu_hr"},
            "hubu": {"shangshu"},
            "libu": {"shangshu"},
            "bingbu": {"shangshu"},
            "xingbu": {"shangshu"},
            "gongbu": {"shangshu"},
            "libu_hr": {"shangshu"},
        }
