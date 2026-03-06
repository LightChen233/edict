"""御史台 — 独立监察机制。

独立监察 Agent 全程旁听任务流转，可随时上疏弹劾（标记异常/暂停任务）。
可叠加到任何基础治理制度。
"""

from __future__ import annotations

import logging
from typing import Any

from ..base import CrossCuttingMechanism, CrossCuttingType

log = logging.getLogger("edict.mechanism.yu_shi_tai")

# 需要特别关注的状态变更模式
SUSPICIOUS_PATTERNS = {
    "rapid_state_change": "状态变更过于频繁，可能存在循环",
    "skip_review": "跳过审核环节",
    "repeated_rejection": "多次被打回，可能方案存在根本问题",
}


class YuShiTaiMechanism(CrossCuttingMechanism):
    """御史台 — 独立监察。"""

    @property
    def type(self) -> CrossCuttingType:
        return CrossCuttingType.YU_SHI_TAI

    @property
    def name(self) -> str:
        return "御史台"

    @property
    def description(self) -> str:
        return (
            "独立监察机制，御史 Agent 全程旁听任务流转，"
            "监控异常模式（循环、跳过审核、频繁打回等），"
            "可上疏弹劾（标记异常/暂停任务/通知管理员）。"
        )

    async def on_before_dispatch(self, task_id: str, agent: str, context: dict) -> dict:
        """派发前监察：检查权限是否合规。"""
        log.debug(f"Task {task_id}: 御史台审查派发 → {agent}")

        violations = context.get("_yushi_violations", [])
        if len(violations) >= 3:
            log.warning(f"Task {task_id}: 御史台弹劾 — 累计 {len(violations)} 次违规，建议暂停")
            context["_yushi_alert"] = {
                "level": "critical",
                "message": f"累计 {len(violations)} 次违规",
                "violations": violations,
            }

        return context

    async def on_state_change(self, task_id: str, from_state: str, to_state: str, context: dict) -> None:
        """状态变更后监察。"""
        flow_log = context.get("flow_log", [])
        violations = context.get("_yushi_violations", [])

        # 检测循环：同一对 from→to 出现超过3次
        transition_key = f"{from_state}→{to_state}"
        transition_count = sum(1 for entry in flow_log if f"{entry.get('from')}→{entry.get('to')}" == transition_key)
        if transition_count >= 3:
            violation = {
                "pattern": "rapid_state_change",
                "detail": f"{transition_key} 已出现 {transition_count} 次",
                "severity": "warning",
            }
            violations.append(violation)
            log.warning(f"Task {task_id}: 御史台察觉 — {violation['detail']}")

        # 检测频繁打回
        rejection_count = sum(
            1 for entry in flow_log
            if entry.get("to") in ("Zhongshu", "Proposed", "Discussion")
            and entry.get("from") in ("Menxia", "Rejected", "Consensus")
        )
        if rejection_count >= 3:
            violation = {
                "pattern": "repeated_rejection",
                "detail": f"已被打回 {rejection_count} 次",
                "severity": "critical",
            }
            violations.append(violation)
            log.warning(f"Task {task_id}: 御史台弹劾 — {violation['detail']}")

        context["_yushi_violations"] = violations

    async def on_task_complete(self, task_id: str, context: dict) -> None:
        """任务完成后出具监察报告。"""
        violations = context.get("_yushi_violations", [])
        if violations:
            log.info(
                f"Task {task_id}: 御史台结案报告 — "
                f"共 {len(violations)} 条违规记录"
            )
        else:
            log.info(f"Task {task_id}: 御史台结案报告 — 流程合规，无异常")
