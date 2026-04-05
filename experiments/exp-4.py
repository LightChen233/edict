#!/usr/bin/env python3
"""
exp-4.py — 全任务实验：跑 task_00-22（23个通用任务），等权重评估

用法：
    python experiments/exp-4.py --model anthropic/claude-sonnet-4-6
    python experiments/exp-4.py --model anthropic/claude-sonnet-4-6 --dry-run
"""

import argparse
import json
import subprocess
import sys
import random
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT    = Path(__file__).parent.parent
PINCHBENCH   = REPO_ROOT / "pinchbench"
RESULTS_DIR  = REPO_ROOT / "experiments" / "results" / "exp-4"

# task_00-22（23个任务）
ALL_TASKS = [f"task_{i:02d}" for i in range(23)]
TASK_SUITE = ",".join(ALL_TASKS)

ALL_GOVERNANCE = [
    "san_sheng", "cheng_xiang", "nei_ge", "jun_ji_chu", "feng_jian",
    "yi_hui", "wei_yuan_hui", "zong_tong", "lian_bang",
    "athenian", "roman", "venetian", "kurultai", "ritsuryo", "shura",
]

GOVERNANCE_NAMES = {
    "san_sheng": "三省六部", "cheng_xiang": "丞相制", "nei_ge": "内阁制",
    "jun_ji_chu": "军机处", "feng_jian": "分封制", "yi_hui": "议会制",
    "wei_yuan_hui": "委员会制", "zong_tong": "总统制", "lian_bang": "联邦制",
    "athenian": "雅典民主", "roman": "罗马元老院", "venetian": "威尼斯共和",
    "kurultai": "忽里勒台", "ritsuryo": "令制", "shura": "舒拉制",
}


def run_pinchbench(model: str, governance: str, out_dir: Path, dry_run: bool):
    out_dir.mkdir(parents=True, exist_ok=True)
    if dry_run:
        return _fake_result(governance)
    
    cmd = [
        "uv", "run", "scripts/benchmark.py",
        "--model", model,
        "--suite", TASK_SUITE,
        "--output-dir", str(out_dir),
        "--no-upload",
    ]
    
    print(f"  运行: {governance}")
    try:
        proc = subprocess.run(cmd, cwd=str(PINCHBENCH), capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        print(f"  [超时] {governance}")
        return None
    except FileNotFoundError:
        print("  [错误] uv 未找到")
        sys.exit(1)
    
    if proc.returncode != 0:
        print(f"  [失败] {governance}")
        return None
    
    result_files = sorted(out_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    if not result_files:
        return None
    
    with open(result_files[-1]) as f:
        return json.load(f)


def _fake_result(governance: str):
    random.seed(hash(governance) % 2**32)
    tasks = []
    for i in range(23):
        tasks.append({
            "task_id": f"task_{i:02d}",
            "status": "success",
            "grading": {"mean": round(random.uniform(0.3, 0.95), 4)},
        })
    return {"tasks": tasks}


def compute_score(result: dict) -> dict:
    """等权重计算所有任务的平均分。"""
    tasks = result.get("tasks", [])
    if not tasks:
        return {"mean": 0.0, "task_scores": {}}
    scores = {}
    for t in tasks:
        tid = t.get("task_id", "")
        scores[tid] = t.get("grading", {}).get("mean", 0.0)
    mean = sum(scores.values()) / len(scores)
    return {"mean": round(mean, 4), "task_scores": scores}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="anthropic/claude-sonnet-4-6")
    parser.add_argument("--governance", default="all")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    models_to_run = ALL_GOVERNANCE if args.governance == "all" else args.governance.split(",")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    print(f"exp-4: {len(models_to_run)} 个治理模型 × {len(ALL_TASKS)} 个任务")
    print(f"模型: {args.model}  dry-run: {args.dry_run}\n")

    results = []
    for gov in models_to_run:
        out_dir = RESULTS_DIR / gov
        raw = run_pinchbench(args.model, gov, out_dir, args.dry_run)
        if raw is None:
            print(f"  [跳过] {gov}")
            continue
        score = compute_score(raw)
        results.append({
            "governance": gov,
            "name": GOVERNANCE_NAMES.get(gov, gov),
            "mean_score": score["mean"],
            "task_scores": score["task_scores"],
        })
        print(f"  {GOVERNANCE_NAMES.get(gov, gov):10s}  {score['mean']:.4f}")

    # 排名
    results.sort(key=lambda x: x["mean_score"], reverse=True)
    ranking = [{"rank": i+1, **r} for i, r in enumerate(results)]

    out = {
        "experiment": "exp-4",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "tasks": ALL_TASKS,
        "note": "等权重，task_00-22 共23个通用任务",
        "ranking": ranking,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"exp4_{ts}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"\n结果写入: {out_path}")
    print("\n排名:")
    for r in ranking:
        print(f"  {r['rank']:2d}. {r['name']:10s}  {r['mean_score']:.4f}")


if __name__ == "__main__":
    main()
