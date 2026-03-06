"""治理模型包 — 多制度治理策略。

支持 9 种基础治理制度 + 3 种跨制度机制。
每个任务可独立选择治理模式，编排器根据模型动态路由。
"""

from .base import GovernanceType, GovernanceModel, CrossCuttingType
from .registry import GovernanceRegistry, get_registry

__all__ = [
    "GovernanceType",
    "GovernanceModel",
    "CrossCuttingType",
    "GovernanceRegistry",
    "get_registry",
]
