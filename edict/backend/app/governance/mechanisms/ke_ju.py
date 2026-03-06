"""科举制 — Agent 竞选机制。

在派发执行者之前，让多个候选 Agent「应试」（提交方案摘要），择优录用。
可叠加到任何基础治理制度的「派发」环节。
"""

from __future__ import annotations

import logging
from typing import Any

from ..base import CrossCuttingMechanism, CrossCuttingType

log = logging.getLogger("edict.mechanism.ke_ju")


class KeJuMechanism(CrossCuttingMechanism):
    """科举制 — 竞争性 Agent 选拔。"""

    @property
    def type(self) -> CrossCuttingType:
        return CrossCuttingType.KE_JU

    @property
    def name(self) -> str:
        return "科举制"

    @property
    def description(self) -> str:
        return (
            "竞争性 Agent 选拔机制。在派发执行者前，让多个候选 Agent 提交方案摘要，"
            "由评审 Agent 择优录用。提高任务与 Agent 的匹配度。"
        )

    async def on_before_dispatch(self, task_id: str, agent: str, context: dict) -> dict:
        """派发前拦截：插入科举竞选环节。

        流程:
        1. 收集候选 Agent 列表
        2. 向每个候选者发送「应试」请求
        3. 评估响应质量
        4. 选出最佳人选替换原 agent

        当前为框架实现，具体竞选逻辑在集成 OpenClaw 时完善。
        """
        candidates = context.get("ke_ju_candidates", [])
        if not candidates:
            log.debug(f"Task {task_id}: 科举制未配置候选人，跳过竞选")
            return context

        log.info(f"Task {task_id}: 科举竞选启动，候选人 {candidates}")

        # TODO: 实现竞选评估逻辑
        # 1. 并发调用候选 agent，获取方案摘要
        # 2. 由评审 agent（如门下省）打分
        # 3. 选出最高分者

        best_candidate = candidates[0] if candidates else agent
        context["selected_agent"] = best_candidate
        context["ke_ju_result"] = {
            "task_id": task_id,
            "candidates": candidates,
            "selected": best_candidate,
            "method": "ke_ju",
        }

        log.info(f"Task {task_id}: 科举结果 — 录用 {best_candidate}")
        return context

    async def on_state_change(self, task_id: str, from_state: str, to_state: str, context: dict) -> None:
        log.debug(f"Task {task_id}: 科举制观测状态变更 {from_state} → {to_state}")

    async def on_task_complete(self, task_id: str, context: dict) -> None:
        ke_ju_result = context.get("ke_ju_result")
        if ke_ju_result:
            log.info(f"Task {task_id}: 科举制任务完成，录用者 {ke_ju_result.get('selected')} 表现记录")
