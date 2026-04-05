#!/usr/bin/env python3
"""
exp-1.py — 标准实验：对所有15种治理模型跑 pinchbench governance suite，输出对比报告

用法：
    # 跑全部15种模型
    python experiments/exp-1.py --model anthropic/claude-sonnet-4-6

    # 只跑指定模型
    python experiments/exp-1.py --model anthropic/claude-sonnet-4-6 --governance san_sheng,jun_ji_chu

    # dry-run（不实际调用 pinchbench，用随机分数验证流程）
    python experiments/exp-1.py --model anthropic/claude-sonnet-4-6 --dry-run

    # 多次运行取平均
    python experiments/exp-1.py --model anthropic/claude-sonnet-4-6 --runs 3
"""

import argparse
import json
import math
import subprocess
import sys
import random
from datetime import datetime, timezone
from pathlib import Path

# ── 常量 ──────────────────────────────────────────────────────────────────────

REPO_ROOT    = Path(__file__).parent.parent
PINCHBENCH   = REPO_ROOT / "pinchbench"
RESULTS_DIR  = REPO_ROOT / "experiments" / "results" / "exp-1"

# governance suite：task_23–27
GOVERNANCE_SUITE = (
    "task_23_governance_routing,"
    "task_24_governance_state_machine,"
    "task_25_governance_tradeoff_analysis,"
    "task_26_governance_mechanism_composition,"
    "task_27_governance_historical_mapping"
)

# 15种治理模型（按拓扑类型分组，便于报告展示）
ALL_GOVERNANCE_MODELS = [
    # 中国历史模型
    "san_sheng", "cheng_xiang", "nei_ge", "jun_ji_chu", "feng_jian",
    # 现代模型
    "yi_hui", "wei_yuan_hui", "zong_tong", "lian_bang",
    # 拓展历史模型
    "athenian", "roman", "venetian", "kurultai", "ritsuryo", "shura",
]

MODEL_META = {
    "san_sheng":    {"name": "三省六部",   "dynasty": "唐",      "topology": "pipeline+fork"},
    "cheng_xiang":  {"name": "丞相制",     "dynasty": "秦汉",    "topology": "hub-and-spoke"},
    "nei_ge":       {"name": "内阁制",     "dynasty": "明",      "topology": "parallel-converge"},
    "jun_ji_chu":   {"name": "军机处",     "dynasty": "清",      "topology": "direct"},
    "feng_jian":    {"name": "分封制",     "dynasty": "周",      "topology": "parallel-autonomous"},
    "yi_hui":       {"name": "议会制",     "dynasty": "现代",    "topology": "debate-vote"},
    "wei_yuan_hui": {"name": "委员会制",   "dynasty": "现代",    "topology": "flat-consensus"},
    "zong_tong":    {"name": "总统制",     "dynasty": "现代",    "topology": "hub-advisors"},
    "lian_bang":    {"name": "联邦制",     "dynasty": "现代",    "topology": "multi-level-parallel"},
    "athenian":     {"name": "雅典民主",   "dynasty": "古希腊",  "topology": "direct-democracy"},
    "roman":        {"name": "罗马元老院", "dynasty": "古罗马",  "topology": "dual-veto"},
    "venetian":     {"name": "威尼斯共和", "dynasty": "中世纪",  "topology": "nested-committees"},
    "kurultai":     {"name": "忽里勒台",   "dynasty": "蒙古",    "topology": "coercive-consensus"},
    "ritsuryo":     {"name": "令制",       "dynasty": "日本奈良","topology": "modified-pipeline"},
    "shura":        {"name": "舒拉制",     "dynasty": "伊斯兰",  "topology": "advisory-hard-constraint"},
}

# task 权重（用于加权总分）
TASK_WEIGHTS = {
    "task_23_governance_routing":             0.25,  # 路由决策：考察模型理解
    "task_24_governance_state_machine":       0.20,  # 状态机：考察精确性
    "task_25_governance_tradeoff_analysis":   0.25,  # 权衡分析：考察推理
    "task_26_governance_mechanism_composition": 0.20, # 机制组合：考察统计
    "task_27_governance_historical_mapping":  0.10,  # 历史映射：考察知识
}


# ── pinchbench 调用 ───────────────────────────────────────────────────────────

def run_pinchbench(model: str, governance: str, runs: int,
                   out_dir: Path, timeout_multiplier: float,
                   dry_run: bool) -> dict | None:
    """调用 pinchbench，返回解析后的结果 JSON，失败返回 None。"""
    out_dir.mkdir(parents=True, exist_ok=True)

    if dry_run:
        return _fake_result(model, governance, runs)

    cmd = [
        "uv", "run", "scripts/benchmark.py",
        "--model", model,
        "--suite", GOVERNANCE_SUITE,
        "--runs", str(runs),
        "--timeout-multiplier", str(timeout_multiplier),
        "--output-dir", str(out_dir),
        "--no-upload",
    ]

    print(f"  运行: {' '.join(cmd[-6:])}")
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PINCHBENCH),
            capture_output=True,
            text=True,
            timeout=600 * timeout_multiplier,
        )
    except subprocess.TimeoutExpired:
        print(f"  [超时] governance={governance}")
        return None
    except FileNotFoundError:
        print("  [错误] uv 未找到，请先安装 uv: https://docs.astral.sh/uv/")
        sys.exit(1)

    if proc.returncode != 0:
        print(f"  [失败] returncode={proc.returncode}")
        print(proc.stderr[-500:] if proc.stderr else "")
        return None

    # 找最新生成的结果文件
    result_files = sorted(out_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    if not result_files:
        print("  [错误] 未找到结果文件")
        return None

    with open(result_files[-1], encoding="utf-8") as f:
        return json.load(f)


def _fake_result(model: str, governance: str, runs: int = 1) -> dict:
    """dry-run 用的模拟结果。"""
    random.seed(hash(governance) % 2**32)
    tasks = []
    for task_id in TASK_WEIGHTS:
        base = random.uniform(0.4, 0.95)
        tasks.append({
            "task_id": task_id,
            "status": "success",
            "timed_out": False,
            "execution_time": random.uniform(30, 180),
            "usage": {
                "total_tokens": random.randint(2000, 15000),
                "cost_usd": random.uniform(0.01, 0.15),
            },
            "grading": {
                "mean": round(base, 4),
                "std": round(random.uniform(0, 0.1), 4),
                "min": round(base - 0.05, 4),
                "max": round(base + 0.05, 4),
            },
        })
    return {"model": model, "tasks": tasks, "governance_type": governance}


# ── 分数提取 ──────────────────────────────────────────────────────────────────

def extract_scores(result: dict) -> dict[str, float]:
    """从 pinchbench 结果中提取每个 task 的得分（0–1）。"""
    scores = {}
    for task_entry in result.get("tasks", []):
        task_id = task_entry["task_id"]
        grading = task_entry.get("grading", {})
        score = grading.get("mean", 0.0)
        scores[task_id] = round(float(score), 4)
    return scores


def compute_weighted_score(scores: dict[str, float]) -> float:
    """加权总分（0–1）。"""
    total = 0.0
    weight_sum = 0.0
    for task_id, weight in TASK_WEIGHTS.items():
        if task_id in scores:
            total += scores[task_id] * weight
            weight_sum += weight
    return round(total / weight_sum, 4) if weight_sum > 0 else 0.0


def compute_efficiency_index(scores: dict[str, float], result: dict) -> float:
    """EI = weighted_score / (avg_completion_sec * sqrt(avg_token_cost))。"""
    weighted = compute_weighted_score(scores)
    times, tokens = [], []
    for t in result.get("tasks", []):
        if t.get("execution_time"):
            times.append(t["execution_time"])
        tok = t.get("usage", {}).get("total_tokens", 0)
        if tok:
            tokens.append(tok)
    if not times or not tokens:
        return 0.0
    avg_time = sum(times) / len(times)
    avg_tok  = sum(tokens) / len(tokens)
    denom = avg_time * math.sqrt(avg_tok)
    return round(weighted / denom, 8) if denom > 0 else 0.0


# ── 报告生成 ──────────────────────────────────────────────────────────────────

def print_table(rows: list[dict], model_id: str):
    """打印对比表格。"""
    header = f"\n{'='*90}"
    print(header)
    print(f"  EXP-1 结果 — 模型: {model_id}")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print('='*90)
    print(f"  {'治理模型':<14} {'中文名':<10} {'朝代':<8} {'加权总分':>8}  "
          f"{'T23':>6} {'T24':>6} {'T25':>6} {'T26':>6} {'T27':>6}  {'EI':>10}")
    print(f"  {'-'*14} {'-'*10} {'-'*8} {'-'*8}  "
          f"{'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6}  {'-'*10}")

    for r in sorted(rows, key=lambda x: x["weighted_score"], reverse=True):
        meta = MODEL_META.get(r["governance"], {})
        t = r["task_scores"]
        print(
            f"  {r['governance']:<14} {meta.get('name',''):<10} {meta.get('dynasty',''):<8} "
            f"{r['weighted_score']:>8.4f}  "
            f"{t.get('task_23_governance_routing', 0):>6.3f} "
            f"{t.get('task_24_governance_state_machine', 0):>6.3f} "
            f"{t.get('task_25_governance_tradeoff_analysis', 0):>6.3f} "
            f"{t.get('task_26_governance_mechanism_composition', 0):>6.3f} "
            f"{t.get('task_27_governance_historical_mapping', 0):>6.3f}  "
            f"{r['efficiency_index']:>10.6f}"
        )
    print('='*90)

    # 最优模型
    best = max(rows, key=lambda x: x["weighted_score"])
    best_ei = max(rows, key=lambda x: x["efficiency_index"])
    print(f"\n  最高总分:  {best['governance']} ({MODEL_META[best['governance']]['name']}) "
          f"= {best['weighted_score']:.4f}")
    print(f"  最高效率:  {best_ei['governance']} ({MODEL_META[best_ei['governance']]['name']}) "
          f"EI = {best_ei['efficiency_index']:.6f}")

    # 拓扑类型分组均值
    topo_scores: dict[str, list] = {}
    for r in rows:
        topo = MODEL_META.get(r["governance"], {}).get("topology", "unknown")
        topo_scores.setdefault(topo, []).append(r["weighted_score"])
    print(f"\n  拓扑类型均分:")
    for topo, scores in sorted(topo_scores.items(), key=lambda x: -sum(x[1])/len(x[1])):
        avg = sum(scores) / len(scores)
        print(f"    {topo:<30} {avg:.4f}")
    print()


def save_report(rows: list[dict], model_id: str, out_path: Path):
    report = {
        "experiment": "exp-1",
        "model": model_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task_weights": TASK_WEIGHTS,
        "results": rows,
        "ranking": [
            {
                "rank": i + 1,
                "governance": r["governance"],
                "name": MODEL_META[r["governance"]]["name"],
                "weighted_score": r["weighted_score"],
                "efficiency_index": r["efficiency_index"],
            }
            for i, r in enumerate(sorted(rows, key=lambda x: x["weighted_score"], reverse=True))
        ],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  报告已保存: {out_path}")


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="EXP-1: governance suite 对比实验")
    parser.add_argument("--model",      required=True,
                        help="模型 ID，如 anthropic/claude-sonnet-4-6")
    parser.add_argument("--governance", default="all",
                        help="逗号分隔的治理模型，或 'all'（默认）")
    parser.add_argument("--runs",       type=int, default=1,
                        help="每个治理模型的运行次数（取平均）")
    parser.add_argument("--timeout-multiplier", type=float, default=1.0)
    parser.add_argument("--dry-run",    action="store_true",
                        help="不实际调用 pinchbench，用随机分数验证流程")
    parser.add_argument("--out-dir",    default=str(RESULTS_DIR))
    args = parser.parse_args()

    gov_list = (ALL_GOVERNANCE_MODELS if args.governance == "all"
                else [g.strip() for g in args.governance.split(",")])

    # 验证模型名
    unknown = [g for g in gov_list if g not in MODEL_META]
    if unknown:
        print(f"[错误] 未知治理模型: {unknown}")
        print(f"可用: {ALL_GOVERNANCE_MODELS}")
        sys.exit(1)

    out_dir = Path(args.out_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\nEXP-1 启动")
    print(f"  模型:     {args.model}")
    print(f"  治理模型: {len(gov_list)} 种")
    print(f"  每模型runs: {args.runs}")
    print(f"  dry-run:  {args.dry_run}")
    print(f"  输出目录: {out_dir}\n")

    rows = []
    for i, governance in enumerate(gov_list, 1):
        meta = MODEL_META[governance]
        print(f"[{i:02d}/{len(gov_list):02d}] {governance} ({meta['name']}, {meta['dynasty']})")

        gov_out = out_dir / governance
        result = run_pinchbench(
            model=args.model,
            governance=governance,
            runs=args.runs,
            out_dir=gov_out,
            timeout_multiplier=args.timeout_multiplier,
            dry_run=args.dry_run,
        )

        if result is None:
            print(f"  [跳过] {governance} 运行失败")
            continue

        scores = extract_scores(result)
        weighted = compute_weighted_score(scores)
        ei = compute_efficiency_index(scores, result)

        rows.append({
            "governance":       governance,
            "weighted_score":   weighted,
            "efficiency_index": ei,
            "task_scores":      scores,
            "runs":             args.runs,
        })
        print(f"  加权总分: {weighted:.4f}  EI: {ei:.6f}")

    if not rows:
        print("\n[错误] 没有成功的运行结果")
        sys.exit(1)

    print_table(rows, args.model)

    report_path = out_dir / f"exp1_{timestamp}.json"
    save_report(rows, args.model, report_path)


if __name__ == "__main__":
    main()
