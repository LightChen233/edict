#!/usr/bin/env python3
"""
exp-2.py — 多模型对比实验：同一治理模型下，不同 LLM 的表现差异

假设验证：
  H1: 治理模型解释 >40% 的质量方差，超过模型能力(~25%)
  H2: 速度-质量-自治三难，无单一模型全面最优

用法：
    # 用3个模型跑全部15种治理模型
    python experiments/exp-2.py \
        --models anthropic/claude-sonnet-4-6,anthropic/claude-haiku-4-5,openai/gpt-4o \
        --governance all

    # dry-run 验证流程
    python experiments/exp-2.py \
        --models anthropic/claude-sonnet-4-6,anthropic/claude-haiku-4-5 \
        --dry-run
"""

import argparse
import json
import math
import subprocess
import sys
import random
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT   = Path(__file__).parent.parent
PINCHBENCH  = REPO_ROOT / "pinchbench"
RESULTS_DIR = REPO_ROOT / "experiments" / "results" / "exp-2"

GOVERNANCE_SUITE = (
    "task_23_governance_routing,"
    "task_24_governance_state_machine,"
    "task_25_governance_tradeoff_analysis,"
    "task_26_governance_mechanism_composition,"
    "task_27_governance_historical_mapping"
)

ALL_GOVERNANCE = [
    "san_sheng", "cheng_xiang", "nei_ge", "jun_ji_chu", "feng_jian",
    "yi_hui", "wei_yuan_hui", "zong_tong", "lian_bang",
    "athenian", "roman", "venetian", "kurultai", "ritsuryo", "shura",
]

TASK_WEIGHTS = {
    "task_23_governance_routing":               0.25,
    "task_24_governance_state_machine":         0.20,
    "task_25_governance_tradeoff_analysis":     0.25,
    "task_26_governance_mechanism_composition": 0.20,
    "task_27_governance_historical_mapping":    0.10,
}


def run_pinchbench(model: str, governance: str, out_dir: Path,
                   timeout_multiplier: float, dry_run: bool) -> dict | None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if dry_run:
        random.seed(hash((model, governance)) % 2**32)
        tasks = []
        for task_id in TASK_WEIGHTS:
            base = random.uniform(0.3, 0.95)
            tasks.append({
                "task_id": task_id,
                "execution_time": random.uniform(20, 200),
                "usage": {"total_tokens": random.randint(1000, 20000), "cost_usd": random.uniform(0.005, 0.2)},
                "grading": {"mean": round(base, 4), "std": round(random.uniform(0, 0.08), 4)},
            })
        return {"model": model, "governance_type": governance, "tasks": tasks}

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
                              text=True, timeout=600 * timeout_multiplier)
    except subprocess.TimeoutExpired:
        print(f"  [超时] model={model} governance={governance}")
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
    times = [t["execution_time"] for t in result.get("tasks", []) if t.get("execution_time")]
    tokens = [t.get("usage", {}).get("total_tokens", 0) for t in result.get("tasks", []) if t.get("usage", {}).get("total_tokens")]
    if not times or not tokens:
        return 0.0
    denom = (sum(times) / len(times)) * math.sqrt(sum(tokens) / len(tokens))
    return round(score / denom, 8) if denom > 0 else 0.0


def variance_decomposition(data: list[dict]) -> dict:
    """简单方差分解：估算治理模型 vs 模型能力各自解释的方差比例。"""
    import statistics
    scores = [d["score"] for d in data]
    if len(scores) < 2:
        return {}
    total_var = statistics.variance(scores)
    if total_var == 0:
        return {"governance_eta2": 0.0, "model_eta2": 0.0}

    # 按 governance 分组
    gov_groups: dict[str, list] = {}
    for d in data:
        gov_groups.setdefault(d["governance"], []).append(d["score"])
    grand_mean = sum(scores) / len(scores)
    ss_gov = sum(len(v) * (sum(v)/len(v) - grand_mean)**2 for v in gov_groups.values())

    # 按 model 分组
    model_groups: dict[str, list] = {}
    for d in data:
        model_groups.setdefault(d["model"], []).append(d["score"])
    ss_model = sum(len(v) * (sum(v)/len(v) - grand_mean)**2 for v in model_groups.values())

    ss_total = total_var * (len(scores) - 1)
    return {
        "governance_eta2": round(ss_gov / ss_total, 4),
        "model_eta2":      round(ss_model / ss_total, 4),
        "total_variance":  round(total_var, 6),
        "n":               len(scores),
    }


def print_report(all_data: list[dict], models: list[str], gov_list: list[str]):
    print(f"\n{'='*100}")
    print(f"  EXP-2 多模型对比报告  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  模型数: {len(models)}  治理模型数: {len(gov_list)}")
    print('='*100)

    # 按 governance 展示各模型得分
    print(f"\n  {'治理模型':<16}", end="")
    for m in models:
        short = m.split("/")[-1][:18]
        print(f"  {short:>18}", end="")
    print(f"  {'模型间方差':>10}")
    print(f"  {'-'*16}", end="")
    for _ in models:
        print(f"  {'-'*18}", end="")
    print(f"  {'-'*10}")

    import statistics
    for gov in gov_list:
        gov_scores = {d["model"]: d["score"] for d in all_data if d["governance"] == gov}
        print(f"  {gov:<16}", end="")
        row_scores = []
        for m in models:
            s = gov_scores.get(m, None)
            if s is not None:
                print(f"  {s:>18.4f}", end="")
                row_scores.append(s)
            else:
                print(f"  {'N/A':>18}", end="")
        var = round(statistics.variance(row_scores), 4) if len(row_scores) > 1 else 0.0
        print(f"  {var:>10.4f}")

    # 方差分解
    vd = variance_decomposition(all_data)
    print(f"\n  方差分解（H1验证）:")
    print(f"    治理模型解释方差 (η²): {vd.get('governance_eta2', 'N/A')}")
    print(f"    模型能力解释方差 (η²): {vd.get('model_eta2', 'N/A')}")
    h1 = vd.get('governance_eta2', 0) > 0.40
    print(f"    H1 {'✓ 支持' if h1 else '✗ 不支持'}: 治理模型{'>' if h1 else '≤'}40% 方差")

    # 每个模型的最优治理模型
    print(f"\n  各模型最优治理制度:")
    for m in models:
        model_data = [d for d in all_data if d["model"] == m]
        if model_data:
            best = max(model_data, key=lambda x: x["score"])
            print(f"    {m.split('/')[-1]:<20} → {best['governance']:<16} ({best['score']:.4f})")

    print('='*100)


def main():
    parser = argparse.ArgumentParser(description="EXP-2: 多模型 × 多治理模型对比")
    parser.add_argument("--models",     required=True, help="逗号分隔的模型ID列表")
    parser.add_argument("--governance", default="all")
    parser.add_argument("--timeout-multiplier", type=float, default=1.0)
    parser.add_argument("--dry-run",    action="store_true")
    parser.add_argument("--out-dir",    default=str(RESULTS_DIR))
    args = parser.parse_args()

    models   = [m.strip() for m in args.models.split(",")]
    gov_list = ALL_GOVERNANCE if args.governance == "all" \
               else [g.strip() for g in args.governance.split(",")]
    out_dir  = Path(args.out_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    total = len(models) * len(gov_list)
    print(f"\nEXP-2 启动: {len(models)} 模型 × {len(gov_list)} 治理模型 = {total} 次运行")

    all_data = []
    done = 0
    for model in models:
        for gov in gov_list:
            done += 1
            print(f"[{done:03d}/{total:03d}] {model.split('/')[-1]} × {gov}")
            result = run_pinchbench(
                model=model, governance=gov,
                out_dir=out_dir / model.replace("/", "_") / gov,
                timeout_multiplier=args.timeout_multiplier,
                dry_run=args.dry_run,
            )
            if result is None:
                continue
            score = weighted_score(result)
            ei    = efficiency_index(result, score)
            all_data.append({"model": model, "governance": gov, "score": score, "ei": ei})
            print(f"  得分: {score:.4f}  EI: {ei:.6f}")

    if not all_data:
        print("[错误] 无有效结果")
        sys.exit(1)

    print_report(all_data, models, gov_list)

    report = {
        "experiment": "exp-2",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "models": models,
        "governance_models": gov_list,
        "results": all_data,
        "variance_decomposition": variance_decomposition(all_data),
    }
    out_path = out_dir / f"exp2_{timestamp}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存: {out_path}")


if __name__ == "__main__":
    main()
