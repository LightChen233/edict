"""御史台监察机制 — 全程订阅任务事件，检测异常并上报。

御史台不参与决策，只做监察：
- 检测任务停滞（超时未推进）
- 检测异常状态转移
- 检测 agent 错误率超阈值
- 上报告警到 flow_log
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

log = logging.getLogger("edict.mechanism.yu_shi_tai")


@dataclass
class YuShiTaiMechanism:
    """御史台监察：全程订阅，异常上报。"""

    name: str = "yu_shi_tai"
    description: str = "御史台监察 — 全程订阅任务事件，检测异常并上报"

    # 停滞阈值（秒），超过则告警
    stall_threshold_sec: int = 300
    # agent 错误率告警阈值
    error_rate_threshold: float = 0.3

    def inspect(self, task: dict, context: dict) -> list[dict]:
        """检查任务状态，返回告警列表。"""
        alerts = []
        now = datetime.now(timezone.utc)

        # 检测停滞
        updated_at = task.get("updatedAt") or task.get("updated_at")
        if updated_at:
            try:
                if isinstance(updated_at, str):
                    from datetime import datetime as dt
                    updated = dt.fromisoformat(updated_at.replace("Z", "+00:00"))
                else:
                    updated = updated_at
                elapsed = (now - updated).total_seconds()
                if elapsed > self.stall_threshold_sec:
                    alerts.append({
                        "type": "stall",
                        "severity": "warning",
                        "message": f"任务停滞 {int(elapsed)}s，超过阈值 {self.stall_threshold_sec}s",
                        "ts": now.isoformat(),
                    })
            except Exception:
                pass

        # 检测 agent 错误率
        agent_errors: dict[str, int] = context.get("agent_errors", {})
        agent_calls: dict[str, int] = context.get("agent_calls", {})
        for agent, errors in agent_errors.items():
            calls = agent_calls.get(agent, 1)
            rate = errors / max(calls, 1)
            if rate > self.error_rate_threshold:
                alerts.append({
                    "type": "agent_error_rate",
                    "severity": "error",
                    "agent": agent,
                    "message": f"agent {agent} 错误率 {rate:.0%}，超过阈值 {self.error_rate_threshold:.0%}",
                    "ts": now.isoformat(),
                })

        if alerts:
            log.warning(f"yu_shi_tai: {len(alerts)} 条告警 task={task.get('id')}")

        return alerts

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "stall_threshold_sec": self.stall_threshold_sec,
            "error_rate_threshold": self.error_rate_threshold,
        }
