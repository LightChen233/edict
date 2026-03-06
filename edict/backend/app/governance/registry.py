"""治理模型注册表 — 工厂 + 查询。

所有治理模型在此注册，编排器和服务层通过 get_registry() 获取。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .base import GovernanceType, GovernanceModel, CrossCuttingType, CrossCuttingMechanism

if TYPE_CHECKING:
    from .base import GovernanceInfo

log = logging.getLogger("edict.governance")


class GovernanceRegistry:
    """治理模型注册表 — 单例。"""

    def __init__(self) -> None:
        self._models: dict[GovernanceType, GovernanceModel] = {}
        self._mechanisms: dict[CrossCuttingType, CrossCuttingMechanism] = {}

    def register_model(self, model: GovernanceModel) -> None:
        self._models[model.type] = model
        log.info(f"Registered governance model: {model.type.value} ({model.name})")

    def register_mechanism(self, mechanism: CrossCuttingMechanism) -> None:
        self._mechanisms[mechanism.type] = mechanism
        log.info(f"Registered cross-cutting mechanism: {mechanism.type.value} ({mechanism.name})")

    def get_model(self, gov_type: GovernanceType | str) -> GovernanceModel:
        """获取治理模型，不存在则 raise KeyError。"""
        if isinstance(gov_type, str):
            gov_type = GovernanceType(gov_type)
        if gov_type not in self._models:
            raise KeyError(f"Unknown governance type: {gov_type.value}")
        return self._models[gov_type]

    def get_mechanism(self, mech_type: CrossCuttingType | str) -> CrossCuttingMechanism:
        if isinstance(mech_type, str):
            mech_type = CrossCuttingType(mech_type)
        if mech_type not in self._mechanisms:
            raise KeyError(f"Unknown mechanism type: {mech_type.value}")
        return self._mechanisms[mech_type]

    def list_models(self) -> list[GovernanceModel]:
        return list(self._models.values())

    def list_model_infos(self) -> list[GovernanceInfo]:
        return [m.to_info() for m in self._models.values()]

    def list_mechanisms(self) -> list[CrossCuttingMechanism]:
        return list(self._mechanisms.values())

    def has_model(self, gov_type: GovernanceType | str) -> bool:
        if isinstance(gov_type, str):
            try:
                gov_type = GovernanceType(gov_type)
            except ValueError:
                return False
        return gov_type in self._models


def _build_registry() -> GovernanceRegistry:
    """构建并填充注册表（延迟导入避免循环）。"""
    registry = GovernanceRegistry()

    from .san_sheng import SanShengModel
    from .cheng_xiang import ChengXiangModel
    from .nei_ge import NeiGeModel
    from .yi_hui import YiHuiModel
    from .jun_ji_chu import JunJiChuModel
    from .feng_jian import FengJianModel
    from .wei_yuan_hui import WeiYuanHuiModel
    from .zong_tong import ZongTongModel
    from .lian_bang import LianBangModel

    for cls in (
        SanShengModel,
        ChengXiangModel,
        NeiGeModel,
        YiHuiModel,
        JunJiChuModel,
        FengJianModel,
        WeiYuanHuiModel,
        ZongTongModel,
        LianBangModel,
    ):
        registry.register_model(cls())

    from .mechanisms.ke_ju import KeJuMechanism
    from .mechanisms.yu_shi_tai import YuShiTaiMechanism
    from .mechanisms.gong_guo_bu import GongGuoBuMechanism

    for cls in (KeJuMechanism, YuShiTaiMechanism, GongGuoBuMechanism):
        registry.register_mechanism(cls())

    return registry


_registry: GovernanceRegistry | None = None


def get_registry() -> GovernanceRegistry:
    """获取全局注册表单例。"""
    global _registry
    if _registry is None:
        _registry = _build_registry()
    return _registry
