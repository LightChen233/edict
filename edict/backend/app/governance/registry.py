"""治理模型注册表 — 单例，启动时自动注册所有模型。"""

from .base import GovernanceModel, GovernanceType


class GovernanceRegistry:
    def __init__(self):
        self._models: dict[str, GovernanceModel] = {}

    def register(self, model: GovernanceModel):
        self._models[model.type.value] = model

    def get_model(self, governance_type: str) -> GovernanceModel:
        model = self._models.get(governance_type)
        if model is None:
            # 默认回退到三省六部
            model = self._models.get(GovernanceType.SAN_SHENG.value)
        return model

    def list_models(self) -> list[dict]:
        return [m.to_info() for m in self._models.values()]


registry = GovernanceRegistry()


def _auto_register():
    from .san_sheng import SanShengModel
    from .cheng_xiang import ChengXiangModel
    from .nei_ge import NeiGeModel
    from .yi_hui import YiHuiModel
    from .jun_ji_chu import JunJiChuModel
    from .feng_jian import FengJianModel
    from .wei_yuan_hui import WeiYuanHuiModel
    from .zong_tong import ZongTongModel
    from .lian_bang import LianBangModel
    from .athenian import AthenianModel
    from .roman import RomanModel
    from .venetian import VenetianModel
    from .kurultai import KurultaiModel
    from .ritsuryo import RitsuryoModel
    from .shura import ShuraModel

    for model in [
        SanShengModel(),
        ChengXiangModel(),
        NeiGeModel(),
        YiHuiModel(),
        JunJiChuModel(),
        FengJianModel(),
        WeiYuanHuiModel(),
        ZongTongModel(),
        LianBangModel(),
        AthenianModel(),
        RomanModel(),
        VenetianModel(),
        KurultaiModel(),
        RitsuryoModel(),
        ShuraModel(),
    ]:
        registry.register(model)


_auto_register()
