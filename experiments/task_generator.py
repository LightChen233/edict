"""
task_generator.py — 生成450个标准化实验任务（5层级 × 5领域 × 18个/组）

用法：
    python task_generator.py --out results/tasks.json
"""

import json
import random
import argparse
import uuid
from dataclasses import dataclass, asdict


# T1–T5 层级定义
TIERS = {
    1: {"name": "Atomic",       "decomposable": False, "verifiable": True,  "controversial": False},
    2: {"name": "Sequential",   "decomposable": True,  "verifiable": True,  "controversial": False},
    3: {"name": "Parallel",     "decomposable": True,  "verifiable": "partial", "controversial": False},
    4: {"name": "Deliberative", "decomposable": True,  "verifiable": "partial", "controversial": True},
    5: {"name": "Complex",      "decomposable": True,  "verifiable": False, "controversial": True},
}

DOMAINS = ["code", "writing", "analysis", "design", "research"]

# 每个 (tier, domain) 组合的任务模板
TASK_TEMPLATES: dict[tuple[int, str], list[str]] = {
    (1, "code"):     ["修复函数中的语法错误", "补全缺失的 import 语句", "重命名变量为符合规范的名称"],
    (1, "writing"):  ["修正段落中的拼写错误", "将被动语态改为主动语态", "补全缺失的标点符号"],
    (1, "analysis"): ["计算数据集的均值和标准差", "统计词频并排序", "验证 JSON 格式是否合法"],
    (1, "design"):   ["调整按钮颜色符合品牌规范", "修正图标尺寸为 24×24px", "对齐表单元素间距"],
    (1, "research"): ["查找某 API 的官方文档链接", "确认某库的最新版本号", "核实某统计数据的来源"],

    (2, "code"):     ["实现并测试一个 REST 接口", "编写带单元测试的排序算法", "重构函数并保持测试通过"],
    (2, "writing"):  ["撰写产品功能说明（含示例）", "将技术文档翻译为用户友好语言", "编写 API 使用教程"],
    (2, "analysis"): ["清洗数据集并生成描述性统计", "对比两个模型的性能指标", "生成带图表的周报"],
    (2, "design"):   ["设计登录页面线框图", "制作组件库色板", "输出响应式布局方案"],
    (2, "research"): ["综述某技术的发展现状", "对比3个竞品的核心功能", "整理某领域近5年论文摘要"],

    (3, "code"):     ["跨3个微服务生成集成测试报告", "并行爬取5个数据源并合并", "多模块重构并更新文档"],
    (3, "writing"):  ["从3个数据源生成综合周报", "多角度撰写产品发布公告", "整合用户反馈生成改进建议"],
    (3, "analysis"): ["跨部门数据汇总分析", "多维度用户行为分析", "并行处理多个数据集并对比"],
    (3, "design"):   ["设计多平台适配的UI系统", "输出完整的设计规范文档", "并行设计多个页面模板"],
    (3, "research"): ["跨领域文献综述", "多来源数据交叉验证", "并行调研多个技术方向"],

    (4, "code"):     ["PostgreSQL vs MongoDB 技术选型", "单体 vs 微服务架构决策", "选择前端框架并论证"],
    (4, "writing"):  ["制定内容策略并评估风险", "撰写有争议话题的平衡报告", "设计用户调研方案"],
    (4, "analysis"): ["评估多个商业模式的可行性", "分析有争议的A/B测试结果", "制定数据治理策略"],
    (4, "design"):   ["在易用性与功能性间做设计权衡", "评估多套设计方案并推荐", "制定无障碍设计标准"],
    (4, "research"): ["评估新兴技术的采用时机", "分析竞争格局并制定策略", "论证研究方向的可行性"],

    (5, "code"):     ["设计可扩展的微服务架构", "规划技术债务清理路线图", "设计多租户 SaaS 平台架构"],
    (5, "writing"):  ["制定公司技术博客内容战略", "撰写年度技术趋势报告", "设计知识管理体系"],
    (5, "analysis"): ["构建端到端数据分析平台方案", "设计实验评估框架", "制定长期数据战略"],
    (5, "design"):   ["设计完整的产品设计系统", "规划用户体验改进路线图", "制定设计语言规范"],
    (5, "research"): ["制定3年技术研究路线图", "设计跨学科研究框架", "规划开源生态建设策略"],
}

# 每个层级推荐的治理模型（用于实验设计参考，不强制）
TIER_GOVERNANCE_HINTS = {
    1: ["jun_ji_chu", "cheng_xiang"],
    2: ["cheng_xiang", "zong_tong", "san_sheng"],
    3: ["san_sheng", "feng_jian", "lian_bang", "ritsuryo"],
    4: ["yi_hui", "wei_yuan_hui", "nei_ge", "athenian", "roman"],
    5: ["san_sheng", "nei_ge", "venetian", "shura", "kurultai"],
}


@dataclass
class ExperimentTask:
    id: str
    tier: int
    tier_name: str
    domain: str
    title: str
    governance_hints: list[str]
    priority: str  # urgent / normal
    multi_domain: bool


def generate_tasks(per_group: int = 18, seed: int = 42) -> list[ExperimentTask]:
    """生成 5×5×per_group = 450 个任务（默认 per_group=18）。"""
    random.seed(seed)
    tasks = []
    for tier in range(1, 6):
        for domain in DOMAINS:
            templates = TASK_TEMPLATES.get((tier, domain), [f"T{tier} {domain} 任务"])
            for i in range(per_group):
                template = templates[i % len(templates)]
                suffix = f"（变体{i+1}）" if i >= len(templates) else ""
                tasks.append(ExperimentTask(
                    id=str(uuid.uuid4()),
                    tier=tier,
                    tier_name=TIERS[tier]["name"],
                    domain=domain,
                    title=template + suffix,
                    governance_hints=TIER_GOVERNANCE_HINTS[tier],
                    priority="urgent" if tier == 1 and random.random() < 0.3 else "normal",
                    multi_domain=(tier >= 3 and random.random() < 0.4),
                ))
    return tasks


def main():
    parser = argparse.ArgumentParser(description="生成实验任务集")
    parser.add_argument("--out", default="results/tasks.json")
    parser.add_argument("--per-group", type=int, default=18)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    tasks = generate_tasks(per_group=args.per_group, seed=args.seed)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump([asdict(t) for t in tasks], f, ensure_ascii=False, indent=2)

    print(f"生成 {len(tasks)} 个任务 → {args.out}")
    # 统计分布
    for tier in range(1, 6):
        count = sum(1 for t in tasks if t.tier == tier)
        print(f"  T{tier}: {count} 个")


if __name__ == "__main__":
    main()
