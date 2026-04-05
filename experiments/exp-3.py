#!/usr/bin/env python3
"""
exp-3.py — 机制正交性实验：验证 ke_ju / yu_shi_tai / gong_guo_bu 叠加效果

假设验证：
  H4: 三种跨制度机制叠加效果可加，无显著交互项
  H5: 功过簿追踪下系统效率随任务数单调提升

实验设计：
  - 基准：san_sheng（无机制）
  - 单机制：+ke_ju / +yu_shi_tai / +gong_guo_bu
  - 双机制：+ke_ju+yu_shi_tai / +ke_ju+gong_guo_bu / +yu_shi_tai+gong_guo_bu
  - 三机制：+ke_ju+yu_shi_tai+gong_guo_bu
  共 8 种组合 × N 次运行

用法：
    python experiments/exp-3.py --model anthropic/claude-sonnet-4-6 --runs 5
    python experiments/exp-3.py --model anthropic/claude-sonnet-4-6 --dry-run
"""

import argparse
import json
import math
import subprocess
import sys
import random
import statistics
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

REPO_ROOT   = Path(__file__).parent.parent
PINCHBENCH  = REPO_ROOT / "pinchbench"
RESULTS_DIR = REPO_ROOT / "experiments" / "results" / "exp-3"

GOVERNANCE_SUITE = (
    "task_23_governance_routing,"
    "task_24_governance_state_machine,"
    "task_25_governance_tradeoff_analysis,"
    "task_26_governance_mechanism_composition,"
    "task_27_governance_historical_mapping"
)

TASK_WEIGHTS = {
    "task_23_governance_routing":               0.25,
    "task_24_governance_state_machine":         0.20,
    "task_25_governance_tradeoff_analysis":     0.25,
    "task_26_governance_mechanism_composition": 0.20,
    "task_27_governance_historical_mapping":    0.10,
}

MECHANISMS = ["ke_ju", "yu_shi_tai", "gong_guo_bu"]

# 8种机制组合
MECHANISM_COMBOS: list[tuple[str, ...]] = [()]  # 基准：无机制
for r in range(1, 4):
    for combo in combinations(MECHANISMS, r):
        MECHANISM_COMBOS.append(combo)


def combo_label(combo: tuple) -> str:
    return "+".join(combo) if combo else "baseline"


def run_pinchbench(model: str, mechanisms: tuple, run_idx: int,
                   out_dir: Path, timeout_multiplier: float, dry_run: bool) -> dict | None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if dry_run:
        # 模拟：机制叠加有小幅正向效果，无显著交互
        random.seed(hash((model, combo_label(mechanisms), run_idx)) % 2**32)
        base = 0.65
        for m in mechanisms:
            base += random.uniform(0.02, 0.06)   # 每个机制独立贡献
        base = min(base, 0.98)
        tasks = []
        for task_id in TASK_WEIGHTS:
            score = base + random.uniform(-0.05, 0.05)
            tasks.append({
                "task_id": task_id,
                "execution_time": random.uniform(30, 150),
                "usage": {"total_tokens": random.randint(2000, 12000), "cost_usd": random.uniform(0.01, 0.1)},
                "grading": {"mean": round(max(0, min(1, score)), 4)},
            })
        return {"model": model, "mechanisms": list(mechanisms), "tasks": tasks}

    # 将机制列表通过环境变量传给 pinchbench
    import os
    env = os.environ.copy()
    env["EDICT_MECHANISMS"] = json.dumps(list(mechanisms))

    cmd = [
        "uv", "run", "scripts/benchmark.py",
        "--model", model,
        "--suite", GOVERNANCE_SUITE,
        "--timeout-multiplier", str(timeout_multiplier),
        "--output-dir", str(out_dir),
        "--no-upload",
    ]
    try:
        proc = subprocess.run(cmd, cwd=str(PINCHBENCH), capture_output=True,
                              text=True, timeout=600 * timeout_multiplier, env=env)
    except subprocess.TimeoutExpired:
        print(f"  [超时] mechanisms={combo_label(mechanisms)}")
        return None
    except FileNotFoundError:
        print("  [错误] uv 未找到")
        sys.exit(1)

    if proc.returncode != 0:
        print(f"  [失败] {proc.stderr[-300:]}")
        return None

    result_files = sorted(out_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    if not result_files:
        return None
    with open(result_files[-1], encoding="utf-8") as f:
        return json.load(f)


def weighted_score(result: dict) -> float:
    total, wsum = 0.0, 0.0
    for t in result.get("tasks", []):
        w = TASK_WEIGHTS.get(t["task_id"], 0)
        total += t.get("grading", {}).get("mean", 0.0) * w
        wsum += w
    return round(total / wsum, 4) if wsum > 0 else 0.0


def efficiency_index(result: dict, score: float) -> float:
    times  = [t["execution_time"] for t in result.get("tasks", []) if t.get("execution_time")]
    tokens = [t.get("usage", {}).get("total_tokens", 0) for t in result.get("tasks", []) if t.get("usage", {}).get("total_tokens")]
    if not times or not tokens:
        return 0.0
    denom = (sum(times) / len(times)) * math.sqrt(sum(tokens) / len(tokens))
    return round(score / denom, 8) if denom > 0 else 0.0


def test_h4_orthogonality(combo_scores: dict[str, list[float]]) -> dict:
    """H4: 机制叠加效果可加，无显著交互项。

    用简单加性模型检验：
      predicted(A+B) ≈ baseline + effect(A) + effect(B)
    若实际值与预测值偏差 < 0.05，认为正交。
    """
    baseline = statistics.mean(combo_scores.get("baseline", [0.65]))
    effects = {}
    for m in MECHANISMS:
        single_scores = combo_scores.get(m, [])
        if single_scores:
            effects[m] = statistics.mean(single_scores) - baseline

    deviations = []
    for r in range(2, 4):
        for combo in combinations(MECHANISMS, r):
            label = combo_label(combo)
            actual_scores = combo_scores.get(label, [])
            if not actual_scores:
                continue
            actual = statistics.mean(actual_scores)
            predicted = baseline + sum(effects.get(m, 0) for m in combo)
            dev = abs(actual - predicted)
            deviations.append({"combo": label, "actual": round(actual, 4),
                                "predicted": round(predicted, 4), "deviation": round(dev, 4)})

    max_dev = max((d["deviation"] for d in deviations), default=0)
    supported = max_dev < 0.05

    return {
        "hypothesis": "H4",
        "baseline_score": round(baseline, 4),
        "mechanism_effects": {k: round(v, 4) for k, v in effects.items()},
        "interaction_deviations": deviations,
        "max_deviation": round(max_dev, 4),
        "supported": supported,
        "note": f"最大交互偏差 {max_dev:.4f}，{'< 0.05 正交' if supported else '>= 0.05 存在交互'}",
    }


def test_h5_learning_curve(run_sequence: list[dict]) -> dict:
    """H5: 功过簿追踪下效率随任务数单调提升。"""
    gonguo_runs = [r for r in run_sequence if "gong_guo_bu" in r.get("mechanisms", [])]
    if len(gonguo_runs) < 5:
        return {"hypothesis": "H5", "supported": None, "note": "功过簿运行数不足（<5）"}

    eis = [r["ei"] for r in gonguo_runs]
    # Spearman 相关（简单实现）
    n = len(eis)
    ranks_x = list(range(1, n + 1))
    sorted_eis = sorted(enumerate(eis), key=lambda x: x[1])
    ranks_y = [0] * n
    for rank, (orig_idx, _) in enumerate(sorted_eis, 1):
        ranks_y[orig_idx] = rank

    d2 = sum((rx - ry) ** 2 for rx, ry in zip(ranks_x, ranks_y))
    spearman_r = 1 - (6 * d2) / (n * (n**2 - 1))

    return {
        "hypothesis": "H5",
        "n_gonguo_runs": n,
        "spearman_r": round(spearman_r, 4),
        "supported": spearman_r > 0.3,
        "note": f"效率{'单调提升' if spearman_r > 0.3 else '未显著提升'} (r={spearman_r:.3f})",
    }


def print_report(combo_scores: dict, h4: dict, h5: dict):
    print(f"\n{'='*80}")
    print(f"  EXP-3 机制正交性实验报告  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print('='*80)
    print(f"\n  {'机制组合':<35} {'均分':>8}  {'标准差':>8}  {'样本数':>6}")
    print(f"  {'-'*35} {'-'*8}  {'-'*8}  {'-'*6}")
    for combo in MECHANISM_COMBOS:
        label = combo_label(combo)
        scores = combo_scores.get(label, [])
        if scores:
            mean = statistics.mean(scores)
            std  = statistics.stdev(scores) if len(scores) > 1 else 0.0
            print(f"  {label:<35} {mean:>8.4f}  {std:>8.4f}  {len(scores):>6}")

    print(f"\n  H4 机制正交性: {h4.get('note', '')}")
    print(f"    {'支持' if h4.get('supported') else '不支持'} — 最大交互偏差: {h4.get('max_deviation', 'N/A')}")
    if h4.get("interaction_deviations"):
        for d in h4["interaction_deviations"]:
            print(f"    {d['combo']:<30} 实际={d['actual']:.4f}  预测={d['predicted']:.4f}  偏差={d['deviation']:.4f}")

    print(f"\n  H5 学习曲线: {h5.get('note', '')}")
    print('='*80)


def main():
    parser = argparse.ArgumentParser(description="EXP-3: 机制正交性实验")
    parser.add_argument("--model",   required=True)
    parser.add_argument("--runs",    type=int, default=3, help="每种组合的运行次数")
    parser.add_argument("--timeout-multiplier", type=float, default=1.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out-dir", default=str(RESULTS_DIR))
    args = parser.parse_args()

    out_dir   = Path(args.out_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    total     = len(MECHANISM_COMBOS) * args.runs

    print(f"\nEXP-3 启动: {len(MECHANISM_COMBOS)} 机制组合 × {args.runs} 次 = {total} 次运行")

    combo_scores: dict[str, list[float]] = {}
    run_sequence: list[dict] = []
    done = 0

    for combo in MECHANISM_COMBOS:
        label = combo_label(combo)
        combo_scores[label] = []
        for run_idx in range(args.runs):
            done += 1
            print(f"[{done:03d}/{total:03d}] {label} (run {run_idx+1}/{args.runs})")
            result = run_pinchbench(
                model=args.model, mechanisms=combo, run_idx=run_idx,
                out_dir=out_dir / label / f"run_{run_idx+1:02d}",
                timeout_multiplier=args.timeout_multiplier,
                dry_run=args.dry_run,
            )
            if result is None:
                continue
            score = weighted_score(result)
            ei    = efficiency_index(result, score)
            combo_scores[label].append(score)
            run_sequence.append({"mechanisms": list(combo), "score": score, "ei": ei, "run_idx": done})
            print(f"  得分: {score:.4f}  EI: {ei:.6f}")

    h4 = test_h4_orthogonality(combo_scores)
    h5 = test_h5_learning_curve(run_sequence)

    print_report(combo_scores, h4, h5)

    report = {
        "experiment": "exp-3",
        "model": args.model,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "runs_per_combo": args.runs,
        "combo_scores": {k: {"mean": round(statistics.mean(v), 4) if v else None,
                              "std":  round(statistics.stdev(v), 4) if len(v) > 1 else 0.0,
                              "runs": v}
                         for k, v in combo_scores.items()},
        "h4_orthogonality": h4,
        "h5_learning_curve": h5,
        "run_sequence": run_sequence,
    }
    out_path = out_dir / f"exp3_{timestamp}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存: {out_path}")


if __name__ == "__main__":
    main()
