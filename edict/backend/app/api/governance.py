"""Governance API — 治理制度查询与管理。

提供治理模型列表、详情、跨制度机制信息的查询接口。
"""

import logging

from fastapi import APIRouter, HTTPException

from ..governance import get_registry, GovernanceType, CrossCuttingType

log = logging.getLogger("edict.api.governance")
router = APIRouter()


@router.get("")
async def list_governance_models():
    """列出所有可用的治理制度。"""
    registry = get_registry()
    models = []
    for m in registry.list_models():
        models.append({
            "type": m.type.value,
            "name": m.name,
            "dynasty": m.dynasty,
            "description": m.description,
            "flow_pattern": m.flow_pattern.value,
            "suitable_for": m.suitable_for,
            "states_count": len(m.get_states()),
            "roles_count": len(m.get_roles()),
        })
    return {"models": models, "count": len(models)}


@router.get("/types")
async def list_governance_types():
    """列出所有治理制度类型枚举值。"""
    return {
        "governance_types": [
            {"value": t.value, "label": t.value}
            for t in GovernanceType
        ],
        "mechanism_types": [
            {"value": t.value, "label": t.value}
            for t in CrossCuttingType
        ],
    }


@router.get("/{gov_type}")
async def get_governance_detail(gov_type: str):
    """获取治理制度的完整详情（状态机、角色、权限矩阵等）。"""
    registry = get_registry()
    try:
        model = registry.get_model(gov_type)
    except (KeyError, ValueError):
        raise HTTPException(status_code=404, detail=f"Unknown governance type: {gov_type}")

    info = model.to_info()
    return {
        "type": info.type,
        "name": info.name,
        "dynasty": info.dynasty,
        "description": info.description,
        "flow_pattern": info.flow_pattern,
        "states": info.states,
        "initial_state": info.initial_state,
        "terminal_states": info.terminal_states,
        "transitions": info.transitions,
        "roles": info.roles,
        "state_agent_map": info.state_agent_map,
        "permission_matrix": info.permission_matrix,
        "suitable_for": info.suitable_for,
    }


@router.get("/{gov_type}/states")
async def get_governance_states(gov_type: str):
    """获取治理制度的状态列表和流转关系。"""
    registry = get_registry()
    try:
        model = registry.get_model(gov_type)
    except (KeyError, ValueError):
        raise HTTPException(status_code=404, detail=f"Unknown governance type: {gov_type}")

    return {
        "type": gov_type,
        "states": model.get_states(),
        "initial_state": model.get_initial_state(),
        "terminal_states": sorted(model.get_terminal_states()),
        "transitions": {k: sorted(v) for k, v in model.get_transitions().items()},
    }


@router.get("/{gov_type}/roles")
async def get_governance_roles(gov_type: str):
    """获取治理制度的角色列表和权限矩阵。"""
    registry = get_registry()
    try:
        model = registry.get_model(gov_type)
    except (KeyError, ValueError):
        raise HTTPException(status_code=404, detail=f"Unknown governance type: {gov_type}")

    return {
        "type": gov_type,
        "roles": [
            {
                "role_id": r.role_id,
                "name": r.name,
                "description": r.description,
                "agent_id": r.agent_id or "",
            }
            for r in model.get_roles()
        ],
        "permission_matrix": {k: sorted(v) for k, v in model.get_permission_matrix().items()},
        "state_agent_map": model.get_state_agent_map(),
    }


@router.get("/mechanisms/list")
async def list_mechanisms():
    """列出所有可用的跨制度机制。"""
    registry = get_registry()
    mechanisms = []
    for m in registry.list_mechanisms():
        mechanisms.append({
            "type": m.type.value,
            "name": m.name,
            "description": m.description,
        })
    return {"mechanisms": mechanisms, "count": len(mechanisms)}
