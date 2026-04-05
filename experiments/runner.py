"""
runner.py — 实验运行器

对每个任务×每种治理模型运行一次，共 450×15 = 6750 次（含6个新模型）。
通过 Edict HTTP API 提交任务，轮询结果，写入 experiment_runs 表。

用法：
    python runner.py --tasks results/tasks.json --governance all --workers 4
    python runner.py --tasks results/tasks.json --governance san_sheng,jun_ji_chu
    python runner.py --tasks results/tasks.json --dry-run
"""

import argparse
import json
import time
import uuid
import asyncio
import httpx
import psycopg2
from datetime import datetime
from pathlib import Path

# 所有15种治理模型
ALL_GOVERNANCE = [
    "san_sheng", "cheng_xiang", "nei_ge", "yi_hui", "jun_ji_chu",
    "feng_jian", "wei_yuan_hui", "zong_tong", "lian_bang",
    "athenian", "roman", "venetian", "kurultai", "ritsuryo", "shura",
]

POLL_INTERVAL = 5   # 秒
TASK_TIMEOUT  = 300 # 秒，超时标记为 fault


def get_db(dsn: str):
    return psycopg2.connect(dsn)


def insert_run(conn, run: dict):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO experiment_runs
              (id, task_id, task_tier, task_domain, governance_type, mechanisms,
               quality_score, completion_sec, token_cost,
               rejection_count, autonomy_score, fault_recovered, agent_model, run_at, context_snapshot)
            VALUES
              (%(id)s, %(task_id)s, %(task_tier)s, %(task_domain)s, %(governance_type)s, %(mechanisms)s,
               %(quality_score)s, %(completion_sec)s, %(token_cost)s,
               %(rejection_count)s, %(autonomy_score)s, %(fault_recovered)s, %(agent_model)s, %(run_at)s, %(context_snapshot)s)
        """, {**run, "mechanisms": json.dumps(run.get("mechanisms", [])),
              "context_snapshot": json.dumps(run.get("context_snapshot", {}))})
    conn.commit()


async def submit_task(client: httpx.AsyncClient, base_url: str, task: dict, governance: str) -> str:
    """提交任务到 Edict API，返回 task_id。"""
    payload = {
        "title": task["title"],
        "governance_type": governance,
        "priority": task.get("priority", "normal"),
        "metadata": {
            "experiment": True,
            "tier": task["tier"],
            "domain": task["domain"],
            "multi_domain": task.get("multi_domain", False),
        }
    }
    # 军机处只接受 urgent
    if governance == "jun_ji_chu":
        payload["priority"] = "urgent"

    resp = await client.post(f"{base_url}/api/tasks", json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()["id"]


async def poll_task(client: httpx.AsyncClient, base_url: str, task_id: str) -> dict:
    """轮询任务直到终态，返回结果 dict。"""
    start = time.time()
    while True:
        elapsed = time.time() - start
        if elapsed > TASK_TIMEOUT:
            return {"status": "timeout", "elapsed": elapsed}
        resp = await client.get(f"{base_url}/api/tasks/{task_id}", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            state = data.get("state", "")
            if state in ("Done", "Cancelled"):
                return {"status": state, "elapsed": elapsed, "data": data}
        await asyncio.sleep(POLL_INTERVAL)


async def run_one(client: httpx.AsyncClient, base_url: str,
                  task: dict, governance: str, dry_run: bool) -> dict:
    """运行单次实验，返回 run record。"""
    run_id = str(uuid.uuid4())
    start_ts = datetime.utcnow()

    if dry_run:
        # 模拟结果
        import random
        return {
            "id": run_id,
            "task_id": task["id"],
            "task_tier": task["tier"],
            "task_domain": task["domain"],
            "governance_type": governance,
            "mechanisms": [],
            "quality_score": round(random.uniform(4, 10), 2),
            "completion_sec": random.randint(10, 120),
            "token_cost": random.randint(500, 5000),
            "rejection_count": random.randint(0, 3),
            "autonomy_score": round(random.uniform(0.5, 1.0), 2),
            "fault_recovered": random.random() < 0.1,
            "agent_model": "claude-sonnet-4-6",
            "run_at": start_ts.isoformat(),
            "context_snapshot": {},
        }

    try:
        edict_task_id = await submit_task(client, base_url, task, governance)
        result = await poll_task(client, base_url, edict_task_id)
        data = result.get("data", {})
        return {
            "id": run_id,
            "task_id": task["id"],
            "task_tier": task["tier"],
            "task_domain": task["domain"],
            "governance_type": governance,
            "mechanisms": data.get("mechanisms", []),
            "quality_score": data.get("quality_score"),       # 由 evaluator 填充
            "completion_sec": int(result.get("elapsed", 0)),
            "token_cost": data.get("token_cost", 0),
            "rejection_count": data.get("rejection_count", 0),
            "autonomy_score": data.get("autonomy_score"),
            "fault_recovered": result["status"] == "Done" and data.get("had_fault", False),
            "agent_model": data.get("agent_model", ""),
            "run_at": start_ts.isoformat(),
            "context_snapshot": data.get("context", {}),
        }
    except Exception as e:
        return {
            "id": run_id, "task_id": task["id"], "task_tier": task["tier"],
            "task_domain": task["domain"], "governance_type": governance,
            "mechanisms": [], "quality_score": None, "completion_sec": None,
            "token_cost": None, "rejection_count": 0, "autonomy_score": None,
            "fault_recovered": False, "agent_model": "", "run_at": start_ts.isoformat(),
            "context_snapshot": {"error": str(e)},
        }


async def run_experiment(tasks: list[dict], governance_list: list[str],
                         base_url: str, dsn: str | None,
                         workers: int, dry_run: bool, out_file: str):
    total = len(tasks) * len(governance_list)
    print(f"计划运行 {len(tasks)} 任务 × {len(governance_list)} 模型 = {total} 次")

    conn = get_db(dsn) if dsn and not dry_run else None
    results = []
    done = 0

    # 生成所有 (task, governance) 对
    pairs = [(t, g) for t in tasks for g in governance_list]

    sem = asyncio.Semaphore(workers)

    async def bounded_run(client, task, gov):
        async with sem:
            return await run_one(client, base_url, task, gov, dry_run)

    async with httpx.AsyncClient() as client:
        coros = [bounded_run(client, t, g) for t, g in pairs]
        for coro in asyncio.as_completed(coros):
            run = await coro
            results.append(run)
            done += 1
            if conn:
                try:
                    insert_run(conn, run)
                except Exception as e:
                    print(f"  DB写入失败: {e}")
            if done % 50 == 0 or done == total:
                print(f"  进度: {done}/{total}")

    if conn:
        conn.close()

    # 写 JSON 备份
    Path(out_file).parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"结果写入 {out_file}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks",      default="results/tasks.json")
    parser.add_argument("--governance", default="all",
                        help="逗号分隔的模型名，或 'all'")
    parser.add_argument("--base-url",   default="http://localhost:8000")
    parser.add_argument("--dsn",        default=None, help="PostgreSQL DSN")
    parser.add_argument("--workers",    type=int, default=4)
    parser.add_argument("--dry-run",    action="store_true")
    parser.add_argument("--out",        default="results/runs.json")
    args = parser.parse_args()

    with open(args.tasks, encoding="utf-8") as f:
        tasks = json.load(f)

    gov_list = ALL_GOVERNANCE if args.governance == "all" \
               else [g.strip() for g in args.governance.split(",")]

    asyncio.run(run_experiment(
        tasks, gov_list, args.base_url, args.dsn,
        args.workers, args.dry_run, args.out
    ))


if __name__ == "__main__":
    main()
