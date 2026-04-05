#!/usr/bin/env python3
"""
exp-simple.py — 简化实验：直接用 nanobot 测试不同治理模型的 agent 表现

不需要完整 Edict 后端，直接调用 nanobot Python API。

用法：
    python experiments/exp-simple.py --sample 3 --governance san_sheng,roman
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
RESULTS_DIR = REPO_ROOT / "experiments" / "results" / "exp-simple"
AGENTS_DIR = REPO_ROOT / "agents"

# 治理模型到 agent 的映射（简化版：只用核心 agent）
GOVERNANCE_AGENTS = {
    "san_sheng": "zhongshu",
    "cheng_xiang": "chengxiang",
    "nei_ge": "shoufu",
    "jun_ji_chu": "junji_dachen",
    "roman": "tianzi",  # 用天子模拟
}

GOVERNANCE_NAMES = {
    "san_sheng": "三省六部",
    "cheng_xiang": "丞相制",
    "nei_ge": "内阁制",
    "jun_ji_chu": "军机处",
    "roman": "罗马元老院",
}


def load_agent_prompt(agent_name: str) -> str:
    """加载 agent 的 SOUL.md。"""
    soul_path = AGENTS_DIR / agent_name / "SOUL.md"
    if soul_path.exists():
        return soul_path.read_text(encoding="utf-8")
    return f"你是 {agent_name}，请完成任务。"


def run_task_with_nanobot(task_title: str, system_prompt: str, timeout: int = 60) -> dict:
    """用 nanobot CLI 运行单个任务。"""
    import subprocess
    import tempfile
    
    # 创建临时配置
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(system_prompt)
        prompt_file = f.name
    
    start = time.time()
    try:
        # 调用 nanobot（假设已安装）
        result = subprocess.run(
            ['nanobot', '--prompt-file', prompt_file, task_title],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        duration = time.time() - start
        success = result.returncode == 0
        return {
            'success': success,
            'duration': duration,
            'output': result.stdout[:500] if success else result.stderr[:500]
        }
    except subprocess.TimeoutExpired:
        return {'success': False, 'duration': timeout, 'output': 'timeout'}
    except FileNotFoundError:
        return {'success': False, 'duration': 0, 'output': 'nanobot not found'}
    finally:
        Path(prompt_file).unlink(missing_ok=True)


def evaluate_result(result: dict) -> float:
    """评分：成功=1.0，失败=0.0，根据时间调整。"""
    if not result['success']:
        return 0.0
    duration = result['duration']
    # 30秒内完成得满分，超过60秒得0.5分
    if duration <= 30:
        return 1.0
    elif duration <= 60:
        return 0.5 + 0.5 * (60 - duration) / 30
    else:
        return 0.5


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", default="experiments/tasks.json")
    parser.add_argument("--governance", default="san_sheng,roman")
    parser.add_argument("--sample", type=int, default=3)
    args = parser.parse_args()
    
    # 加载任务
    with open(args.tasks) as f:
        all_tasks = json.load(f)
    
    import random
    random.seed(42)
    tasks = random.sample(all_tasks, min(args.sample, len(all_tasks)))
    
    gov_list = args.governance.split(",")
    
    print(f"简化实验（直接调用 nanobot）")
    print(f"  任务数: {len(tasks)}")
    print(f"  治理模型: {len(gov_list)}")
    
    results = []
    for gov in gov_list:
        if gov not in GOVERNANCE_AGENTS:
            print(f"\n跳过未映射的治理模型: {gov}")
            continue
        
        agent = GOVERNANCE_AGENTS[gov]
        prompt = load_agent_prompt(agent)
        
        print(f"\n{'='*50}")
        print(f"{GOVERNANCE_NAMES.get(gov, gov)} (agent: {agent})")
        print(f"{'='*50}")
        
        scores = []
        for i, task in enumerate(tasks, 1):
            print(f"  [{i}/{len(tasks)}] {task['title'][:35]}...", end=" ")
            result = run_task_with_nanobot(task['title'], prompt)
            score = evaluate_result(result)
            scores.append(score)
            status = "✓" if result['success'] else "✗"
            print(f"{status} {score:.2f} ({result['duration']:.1f}s)")
        
        mean = sum(scores) / len(scores) if scores else 0
        results.append({
            "governance": gov,
            "name": GOVERNANCE_NAMES.get(gov, gov),
            "mean_score": round(mean, 4),
        })
    
    # 保存结果
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = RESULTS_DIR / f"exp_simple_{ts}.json"
    
    with open(out, "w") as f:
        json.dump({
            "experiment": "exp-simple",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": results
        }, f, indent=2)
    
    print(f"\n{'='*50}")
    print("结果:")
    for r in sorted(results, key=lambda x: x['mean_score'], reverse=True):
        print(f"  {r['name']:12s}  {r['mean_score']:.4f}")
    print(f"\n保存到: {out}")


if __name__ == "__main__":
    main()
