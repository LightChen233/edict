"""Governance API — 查询可用治理模型。"""

from fastapi import APIRouter, HTTPException

from ..governance.registry import registry

router = APIRouter(prefix="/api/governance", tags=["governance"])


@router.get("")
async def list_governance():
    """列出所有可用治理模型。"""
    return {"models": registry.list_models()}


@router.get("/{governance_type}")
async def get_governance(governance_type: str):
    """获取指定治理模型详情。"""
    model = registry.get_model(governance_type)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Governance model not found: {governance_type}")
    return model.to_info()
