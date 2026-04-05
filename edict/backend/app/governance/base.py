"""治理模型抽象基类。

每种治理模型定义自己的：
- 状态列表与初始/终态
- 合法状态转移
- 状态→Agent 映射
- 权限矩阵
"""

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class GovernanceType(str, enum.Enum):
    SAN_SHENG    = "san_sheng"
    CHENG_XIANG  = "cheng_xiang"
    NEI_GE       = "nei_ge"
    YI_HUI       = "yi_hui"
    JUN_JI_CHU   = "jun_ji_chu"
    FENG_JIAN    = "feng_jian"
    WEI_YUAN_HUI = "wei_yuan_hui"
    ZONG_TONG    = "zong_tong"
    LIAN_BANG    = "lian_bang"
    # 拓展实验：6种新历史模型
    ATHENIAN     = "athenian"
    ROMAN        = "roman"
    VENETIAN     = "venetian"
    KURULTAI     = "kurultai"
    RITSURYO     = "ritsuryo"
    SHURA        = "shura"


@dataclass
class Transition:
    """带守卫条件的状态转移。"""
    from_state: str
    to_state: str
    guard: Any = None   # Callable[[dict], bool] | None
    action: Any = None  # Callable[[dict], None] | None

    def is_allowed(self, context: dict) -> bool:
        if self.guard is None:
            return True
        return self.guard(context)


class GovernanceModel(ABC):
    """所有治理模型的抽象基类。"""

    type: GovernanceType
    name: str
    description: str
    dynasty: str    # 历史朝代/来源
    topology: str   # hub-and-spoke / pipeline / consensus / parallel / ...

    @abstractmethod
    def get_states(self) -> list[str]: ...

    @abstractmethod
    def get_initial_state(self) -> str: ...

    @abstractmethod
    def get_terminal_states(self) -> set[str]: ...

    @abstractmethod
    def get_transitions(self) -> dict[str, set[str]]: ...

    @abstractmethod
    def get_state_agent_map(self) -> dict[str, str]: ...

    def get_permission_matrix(self) -> dict[str, set[str]]:
        """默认权限矩阵：每个状态允许所有 agent。子类可覆盖。"""
        return {s: {"*"} for s in self.get_states()}

    def validate_transition(self, from_state: str, to_state: str, context: dict | None = None) -> bool:
        return to_state in self.get_transitions().get(from_state, set())

    def get_next_agent(self, state: str, context: dict | None = None) -> str | None:
        return self.get_state_agent_map().get(state)

    def to_info(self) -> dict:
        return {
            "type": self.type.value,
            "name": self.name,
            "description": self.description,
            "dynasty": self.dynasty,
            "topology": self.topology,
            "states": self.get_states(),
            "initial_state": self.get_initial_state(),
            "terminal_states": list(self.get_terminal_states()),
        }
