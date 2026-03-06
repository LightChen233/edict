"""治理模型抽象基类 + 枚举定义。

每种治理制度实现 GovernanceModel 接口，提供：
- 状态机（状态集、初始/终态、合法流转）
- 角色定义与状态→Agent映射
- 权限矩阵
- 流转模式描述
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class GovernanceType(str, enum.Enum):
    """基础治理制度类型。"""
    SAN_SHENG = "san_sheng"          # 三省六部制（唐）
    CHENG_XIANG = "cheng_xiang"      # 丞相制（秦汉）
    NEI_GE = "nei_ge"                # 内阁制（明）
    YI_HUI = "yi_hui"                # 议会制
    JUN_JI_CHU = "jun_ji_chu"        # 军机处制（清）
    FENG_JIAN = "feng_jian"          # 分封制（周）
    WEI_YUAN_HUI = "wei_yuan_hui"    # 委员会制
    ZONG_TONG = "zong_tong"          # 总统制
    LIAN_BANG = "lian_bang"           # 联邦制


class CrossCuttingType(str, enum.Enum):
    """跨制度机制类型。"""
    KE_JU = "ke_ju"              # 科举制 — Agent 竞选
    YU_SHI_TAI = "yu_shi_tai"   # 御史台 — 独立监察
    GONG_GUO_BU = "gong_guo_bu" # 功过簿 — 绩效追踪


class FlowPattern(str, enum.Enum):
    """流转模式。"""
    LINEAR = "linear"                          # 线性流水线
    HUB_SPOKE = "hub_spoke"                    # 中心辐射
    COLLECTIVE_DELIBERATION = "collective"      # 集体商议
    DEBATE_VOTE = "debate_vote"                # 辩论投票
    FAST_TRACK = "fast_track"                  # 极简快速
    DECENTRALIZED = "decentralized"            # 去中心化
    FLAT_CONSENSUS = "flat_consensus"          # 扁平共识
    EXECUTIVE_ADVISORY = "executive_advisory"  # 强执行+顾问
    MULTI_LEVEL = "multi_level"                # 多级治理


@dataclass
class RoleDefinition:
    """角色定义。"""
    role_id: str
    name: str
    description: str
    agent_id: str | None = None  # 对应的 OpenClaw Agent ID


@dataclass
class GovernanceInfo:
    """治理模型的可序列化摘要，用于 API 返回。"""
    type: str
    name: str
    dynasty: str
    description: str
    flow_pattern: str
    states: list[str]
    initial_state: str
    terminal_states: list[str]
    transitions: dict[str, list[str]]
    roles: list[dict[str, str]]
    state_agent_map: dict[str, str]
    permission_matrix: dict[str, list[str]]
    suitable_for: list[str]


class GovernanceModel(ABC):
    """治理模型抽象基类。

    每种制度实现此接口，编排器通过 GovernanceRegistry 获取
    对应模型来驱动任务状态机。
    """

    @property
    @abstractmethod
    def type(self) -> GovernanceType: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def dynasty(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def flow_pattern(self) -> FlowPattern: ...

    @property
    @abstractmethod
    def suitable_for(self) -> list[str]: ...

    @abstractmethod
    def get_states(self) -> list[str]:
        """返回该制度下所有合法状态名。"""

    @abstractmethod
    def get_initial_state(self) -> str:
        """返回任务创建时的初始状态。"""

    @abstractmethod
    def get_terminal_states(self) -> set[str]:
        """返回终态集合。"""

    @abstractmethod
    def get_transitions(self) -> dict[str, set[str]]:
        """返回状态合法流转路径: {from_state: {to_states}}。"""

    @abstractmethod
    def get_roles(self) -> list[RoleDefinition]:
        """返回该制度下的角色列表。"""

    @abstractmethod
    def get_state_agent_map(self) -> dict[str, str]:
        """返回 状态→Agent ID 映射。"""

    @abstractmethod
    def get_org_agent_map(self) -> dict[str, str]:
        """返回 组织/部门→Agent ID 映射（执行层）。"""

    @abstractmethod
    def get_permission_matrix(self) -> dict[str, set[str]]:
        """返回权限矩阵: {from_role: {to_roles}}。"""

    def validate_transition(self, from_state: str, to_state: str) -> bool:
        """校验状态流转是否合法。"""
        transitions = self.get_transitions()
        return to_state in transitions.get(from_state, set())

    def get_next_agent(self, state: str, context: dict | None = None) -> str | None:
        """根据状态和上下文确定下一个处理 Agent。

        子类可覆盖以实现更复杂的派发逻辑（如内阁制的集体讨论、
        议会制的投票等）。
        """
        agent = self.get_state_agent_map().get(state)
        if agent is None and context:
            org = context.get("assignee_org", "")
            agent = self.get_org_agent_map().get(org)
        return agent

    def to_info(self) -> GovernanceInfo:
        """序列化为 API 友好的摘要。"""
        return GovernanceInfo(
            type=self.type.value,
            name=self.name,
            dynasty=self.dynasty,
            description=self.description,
            flow_pattern=self.flow_pattern.value,
            states=self.get_states(),
            initial_state=self.get_initial_state(),
            terminal_states=sorted(self.get_terminal_states()),
            transitions={k: sorted(v) for k, v in self.get_transitions().items()},
            roles=[
                {"role_id": r.role_id, "name": r.name, "description": r.description, "agent_id": r.agent_id or ""}
                for r in self.get_roles()
            ],
            state_agent_map=self.get_state_agent_map(),
            permission_matrix={k: sorted(v) for k, v in self.get_permission_matrix().items()},
            suitable_for=self.suitable_for,
        )


class CrossCuttingMechanism(ABC):
    """跨制度机制抽象基类。

    可叠加到任何基础治理模型上，在事件流中插入额外逻辑。
    """

    @property
    @abstractmethod
    def type(self) -> CrossCuttingType: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    async def on_before_dispatch(self, task_id: str, agent: str, context: dict) -> dict:
        """派发前拦截。返回可能修改后的 context（如替换 agent）。"""

    @abstractmethod
    async def on_state_change(self, task_id: str, from_state: str, to_state: str, context: dict) -> None:
        """状态变更后回调。"""

    @abstractmethod
    async def on_task_complete(self, task_id: str, context: dict) -> None:
        """任务完成后回调。"""
