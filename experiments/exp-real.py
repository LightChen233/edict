#!/usr/bin/env python3
"""
exp-real.py — 基于 Edict 真实系统的治理模型实验

通过 Edict API 提交任务，测试 15 个治理模型的实际表现。

前置条件：
    1. Edict 后端运行中（Postgres + Redis + FastAPI + dispatch_worker）
    2. nanobot 已配置好 API key

用法：
    # 生成测试任务
    python experiments/task_generator.py --out experiments/tasks.json --per-group 2

    # 运行实验（每个治理模型跑 10 个任务）
    python experiments/exp-real.py --tasks experiments/tasks.json --sample 10

    # 只测试指定治理模型
    python experiments/exp-real.py --governance san_sheng,nei_ge --sample 5
"""

import argparse
import json
import time
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).parent.parent
RESULTS_DIR = REPO_ROOT / "experiments" / "results" / "exp-real"
CHECKPOINT_FILE = RESULTS_DIR / "checkpoint.json"

# Edict API 地址
API_BASE = "http://localhost:8000"

# 15 个治理模型
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


def load_checkpoint() -> dict:
    """加载 checkpoint，返回 {gov:task_title -> {task_id, score}} 字典。"""
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_checkpoint(checkpoint: dict):
    """保存 checkpoint 到文件。"""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)


def checkpoint_key(governance: str, title: str) -> str:
    return f"{governance}::{title}"


def submit_task(title: str, governance: str, priority: str = "normal") -> Optional[str]:
    """提交任务到 Edict API，返回 task_id。"""
    try:
        resp = requests.post(f"{API_BASE}/api/tasks", json={
            "title": title,
            "governance_type": governance,
            "priority": priority,
        }, timeout=10)
        resp.raise_for_status()
        return resp.json()["task_id"]
    except Exception as e:
        print(f"  [提交失败] {e}")
        return None


def wait_task_done(task_id: str, timeout: int = 600) -> Optional[dict]:
    """轮询任务状态直到完成或超时，返回任务详情。"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(f"{API_BASE}/api/tasks/{task_id}", timeout=5)
            resp.raise_for_status()
            task = resp.json()
            state = task.get("state")
            if state in ["Done", "Cancelled", "Blocked"]:
                return task
        except Exception:
            pass
        time.sleep(2)
    return None


def evaluate_task(task: dict) -> float:
    """评分：Done=按时间打分，Cancelled=0.2，其他=0。"""
    state = task.get("state")
    if state == "Cancelled":
        return 0.2
    if state == "Blocked":
        return 0.1
    if state != "Done":
        return 0.0
    # 时间字段兼容驼峰和下划线
    created_str = task.get("createdAt") or task.get("created_at", "")
    updated_str = task.get("updatedAt") or task.get("updated_at", "")
    try:
        created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        updated = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
        duration = (updated - created).total_seconds()
        time_score = max(0.5, 1.0 - (duration - 60) / 240) if duration > 60 else 1.0
    except Exception:
        time_score = 0.5
    return round(time_score, 4)


def run_experiment(tasks: list[dict], governance_list: list[str], sample: int):
    """运行实验：每个治理模型处理 sample 个任务。支持断点续跑。"""
    import random
    random.seed(42)
    sampled = random.sample(tasks, min(sample, len(tasks)))

    checkpoint = load_checkpoint()
    results = []

    for gov in governance_list:
        print(f"\n{'='*60}")
        print(f"测试治理模型: {GOVERNANCE_NAMES.get(gov, gov)}")
        print(f"{'='*60}")

        scores = []
        for i, task in enumerate(sampled, 1):
            title = task["title"]
            ck = checkpoint_key(gov, title)
            print(f"  [{i}/{len(sampled)}] {title[:40]}...")

            # 已有结果直接复用
            if ck in checkpoint:
                entry = checkpoint[ck]
                if entry.get("score") is not None:
                    scores.append(entry["score"])
                    print(f"    ↩ 复用 checkpoint (得分: {entry['score']:.2f})")
                    continue
                # 有 task_id 但未完成，继续等待
                task_id = entry.get("task_id")
            else:
                task_id = submit_task(title, gov, task.get("priority", "normal"))
                if not task_id:
                    continue
                checkpoint[ck] = {"task_id": task_id, "score": None}
                save_checkpoint(checkpoint)

            completed = wait_task_done(task_id, timeout=300)
            if completed:
                score = evaluate_task(completed)
                scores.append(score)
                checkpoint[ck]["score"] = score
                save_checkpoint(checkpoint)
                print(f"    ✓ 完成 (得分: {score:.2f})")
            else:
                print(f"    ✗ 超时")

        mean_score = sum(scores) / len(scores) if scores else 0.0
        results.append({
            "governance": gov,
            "name": GOVERNANCE_NAMES.get(gov, gov),
            "mean_score": round(mean_score, 4),
            "completed": len(scores),
            "total": len(sampled),
        })
        print(f"\n  平均得分: {mean_score:.4f} ({len(scores)}/{len(sampled)} 完成)")

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", default="experiments/tasks.json")
    parser.add_argument("--governance", default="all")
    parser.add_argument("--sample", type=int, default=10)
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args()
    
    global API_BASE
    API_BASE = args.api
    
    # 加载任务
    with open(args.tasks, encoding="utf-8") as f:
        tasks = json.load(f)
    
    gov_list = ALL_GOVERNANCE if args.governance == "all" else args.governance.split(",")
    
    print(f"实验配置:")
    print(f"  任务池: {len(tasks)} 个")
    print(f"  每个治理模型测试: {args.sample} 个")
    print(f"  治理模型: {len(gov_list)} 个")
    print(f"  API: {API_BASE}")
    
    # 运行实验
    results = run_experiment(tasks, gov_list, args.sample)
    
    # 排名
    results.sort(key=lambda x: x["mean_score"], reverse=True)
    ranking = [{"rank": i+1, **r} for i, r in enumerate(results)]
    
    # 保存结果
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"exp_real_{ts}.json"
    
    output = {
        "experiment": "exp-real",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sample_size": args.sample,
        "ranking": ranking,
    }
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print("最终排名:")
    print(f"{'='*60}")
    for r in ranking:
        print(f"  {r['rank']:2d}. {r['name']:12s}  {r['mean_score']:.4f}  ({r['completed']}/{r['total']})")
    print(f"\n结果已保存: {out_path}")


if __name__ == "__main__":
    main()
