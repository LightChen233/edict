#!/usr/bin/env python3                                               
"""                                                                  
exp-1.py — 标准实验：把 pinchbench task prompt 提交给                
Edict，走完治理流程，用 pinchbench grading 评分
                                                                    
用法：                                                               
    # 跑全部15种治理模型
    python experiments/exp-1.py --edict-url http://localhost:8000

    # 只跑指定模型
    python experiments/exp-1.py --edict-url http://localhost:8000
--governance san_sheng,jun_ji_chu

    # dry-run（不实际调用 Edict，用随机分数验证流程）
    python experiments/exp-1.py --edict-url http://localhost:8000
--dry-run
"""

import argparse
import json
import math
import random
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# ── 路径 

REPO_ROOT   = Path(__file__).parent.parent
PINCHBENCH  = REPO_ROOT / "pinchbench"
RESULTS_DIR = REPO_ROOT / "experiments" / "results" / "exp-1"

sys.path.insert(0, str(PINCHBENCH / "scripts"))

from lib_tasks import TaskLoader
from lib_grading import grade_task, GradeResult

# ── 常量 

GOVERNANCE_TASK_IDS = [
    "task_23_governance_routing",
    "task_24_governance_state_machine",
    "task_25_governance_tradeoff_analysis",
    "task_26_governance_mechanism_composition",
    "task_27_governance_historical_mapping",
]

ALL_GOVERNANCE_MODELS = [
    "san_sheng", "cheng_xiang", "nei_ge", "jun_ji_chu", "feng_jian",
    "yi_hui", "wei_yuan_hui", "zong_tong", "lian_bang",
    "athenian", "roman", "venetian", "kurultai", "ritsuryo", "shura",
]

MODEL_META = {
    "san_sheng":    {"name": "三省六部",   "dynasty": "唐",
"topology": "pipeline+fork"},
    "cheng_xiang":  {"name": "丞相制",     "dynasty": "秦汉",
"topology": "hub-and-spoke"},
    "nei_ge":       {"name": "内阁制",     "dynasty": "明",
"topology": "parallel-converge"},
    "jun_ji_chu":   {"name": "军机处",     "dynasty": "清",
"topology": "direct"},
    "feng_jian":    {"name": "分封制",     "dynasty": "周",
"topology": "parallel-autonomous"},
    "yi_hui":       {"name": "议会制",     "dynasty": "现代",
"topology": "debate-vote"},
    "wei_yuan_hui": {"name": "委员会制",   "dynasty": "现代",
"topology": "flat-consensus"},
    "zong_tong":    {"name": "总统制",     "dynasty": "现代",
"topology": "hub-advisors"},
    "lian_bang":    {"name": "联邦制",     "dynasty": "现代",
"topology": "multi-level-parallel"},
    "athenian":     {"name": "雅典民主",   "dynasty": "古希腊",
"topology": "direct-democracy"},
    "roman":        {"name": "罗马元老院", "dynasty": "古罗马",
"topology": "dual-veto"},
    "venetian":     {"name": "威尼斯共和", "dynasty": "中世纪",
"topology": "nested-committees"},
    "kurultai":     {"name": "忽里勒台",   "dynasty": "蒙古",
"topology": "coercive-consensus"},
    "ritsuryo":     {"name": "令制",       "dynasty": "日本奈良",
"topology": "modified-pipeline"},
    "shura":        {"name": "舒拉制",     "dynasty": "伊斯兰",
"topology": "advisory-hard-constraint"},
}

TASK_WEIGHTS = {
    "task_23_governance_routing":               0.25,
    "task_24_governance_state_machine":         0.20,
    "task_25_governance_tradeoff_analysis":     0.25,
    "task_26_governance_mechanism_composition": 0.20,
    "task_27_governance_historical_mapping":    0.10,
}

TERMINAL_STATES = {"Done", "Cancelled"}
POLL_INTERVAL   = 5   # seconds
POLL_TIMEOUT    = 300 # seconds per task

# ── Edict HTTP 客户端

def edict_create_task(base_url: str, title: str, description: str,
                    governance_type: str) -> str:
    """提交任务到 Edict，返回 task_id。"""
    import urllib.request
    payload = json.dumps({
        "title": title,
        "description": description,
        "governance_type": governance_type,
        "priority": "normal",
    }).encode()
    req = urllib.request.Request(
        f"{base_url}/api/tasks",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["task_id"]


def edict_get_task(base_url: str, task_id: str) -> dict:
    """获取任务详情。"""
    import urllib.request
    url = f"{base_url}/api/tasks/{task_id}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read())


def edict_poll_until_done(base_url: str, task_id: str,
                        timeout: int = POLL_TIMEOUT) -> dict | None:
    """轮询直到任务进入终态，返回最终任务 dict，超时返回 None。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        task = edict_get_task(base_url, task_id)
        if task.get("state") in TERMINAL_STATES:
            return task
        time.sleep(POLL_INTERVAL)
    return None


# ── 把 Edict 任务结果转成 pinchbench execution_result 格式


def edict_task_to_execution_result(task: dict, workspace_path: str,
                                    pinch_task) -> dict:
    """
    把 Edict 的 task dict 转成 lib_grading.grade_task 期望的
execution_result。

    pinchbench grading 需要：
    - transcript: list of events（我们用 flow_log + progress_log
构造）
    - workspace:  workspace 目录路径（automated checks
会在这里找文件）
    - status:     "success" | "error"
    """
    # 把 output 写入 workspace，让 automated checks 能读到
    workspace = Path(workspace_path)
    workspace.mkdir(parents=True, exist_ok=True)

    # 把 workspace_files（任务初始文件）写入 workspace
    for wf in (pinch_task.workspace_files or []):
        fpath = workspace / wf["path"]
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(wf.get("content", ""), encoding="utf-8")

    # 把 Edict output 写成 agent 最终回复，供 LLM judge 读取
    output_text = task.get("output", "") or ""

    # 构造 transcript：把 progress_log 每条变成 assistant message
    transcript = []
    for entry in (task.get("progress_log") or []):
        transcript.append({
            "type": "message",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text":
entry.get("text", "")}],
            },
        })
    # 最终 output 作为最后一条 assistant message
    if output_text:
        transcript.append({
            "type": "message",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": output_text}],
            },
        })

    # 如果 output 看起来像 JSON 文件内容，尝试写入 workspace
    _try_write_output_files(output_text, workspace)

    state = task.get("state", "")
    return {
        "status":       "success" if state == "Done" else "error",
        "transcript":   transcript,
        "workspace":    str(workspace),
        "timed_out":    False,
        "execution_time": 0.0,
        "usage":        {},
    }


def _try_write_output_files(output_text: str, workspace: Path):
    """
    尝试从 output 文本中提取文件内容并写入 workspace。
    支持 markdown 代码块格式：
    ```filename.json
    {...}
    ```
    或者直接是 JSONL（governance_recommendations.json 等）。
    """
    import re
    # 匹配 ```filename\n...\n``` 格式
    pattern = re.compile(r"```(\S+)\n(.*?)```", re.DOTALL)
    for m in pattern.finditer(output_text):
        fname, content = m.group(1), m.group(2)
        if "/" not in fname and len(fname) < 80:
            fpath = workspace / fname
            fpath.write_text(content, encoding="utf-8")

    # 如果整个 output 是 JSONL（每行都是 JSON 对象），
    # 且 workspace 里还没有 governance_recommendations.json，就写入
    lines = [l.strip() for l in output_text.strip().splitlines() if
l.strip()]
    if lines and all(_is_json_obj(l) for l in lines):
        target = workspace / "governance_recommendations.json"
        if not target.exists():
            target.write_text("\n".join(lines), encoding="utf-8")


def _is_json_obj(s: str) -> bool:
    try:
        return isinstance(json.loads(s), dict)
    except Exception:
        return False


# ── dry-run 模拟

def _fake_execution_result(governance: str, task_id: str) -> dict:
    random.seed(hash(f"{governance}:{task_id}") % 2**32)
    return {
        "status":        "success",
        "transcript":    [],
        "workspace":     "",
        "timed_out":     False,
        "execution_time": random.uniform(30, 180),
        "usage":         {"total_tokens": random.randint(2000,
15000)},
    }


def _fake_grade(task_id: str, governance: str) -> GradeResult:
    random.seed(hash(f"{governance}:{task_id}") % 2**32)
    score = random.uniform(0.4, 0.95)
    return GradeResult(
        task_id=task_id,
        score=round(score, 4),
        max_score=1.0,
        grading_type="hybrid",
        breakdown={},
        notes="dry-run",
    )


# ── 评分聚合
def compute_weighted_score(scores: dict[str, float]) -> float:
    total, wsum = 0.0, 0.0
    for tid, w in TASK_WEIGHTS.items():
        if tid in scores:
            total += scores[tid] * w
            wsum  += w
    return round(total / wsum, 4) if wsum > 0 else 0.0


def compute_efficiency_index(scores: dict[str, float],
                            exec_results: list[dict]) -> float:
    weighted = compute_weighted_score(scores)
    times, tokens = [], []
    for r in exec_results:
        if r.get("execution_time"):
            times.append(r["execution_time"])
        tok = r.get("usage", {}).get("total_tokens", 0)
        if tok:
            tokens.append(tok)
    if not times or not tokens:
        return 0.0
    denom = (sum(times)/len(times)) * math.sqrt(sum(tokens)/len(tokens))
    return round(weighted / denom, 8) if denom > 0 else 0.0


# ── 报告 

def print_table(rows: list[dict]):
    print(f"\n{'='*95}")
    print(f"  EXP-1 结果 — {datetime.now().strftime('%Y-%m-%d%H:%M:%S')}")
    print('='*95)
    print(f"  {'治理模型':<14} {'中文名':<10} {'朝代':<8} {'加权总分':>8}  "
        f"{'T23':>6} {'T24':>6} {'T25':>6} {'T26':>6} {'T27':>6} {'EI':>10}")
    print(f"  {'-'*14} {'-'*10} {'-'*8} {'-'*8}  "
        f"{'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6}  {'-'*10}")
    for r in sorted(rows, key=lambda x: x["weighted_score"],
reverse=True):
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
    print('='*95)
    best    = max(rows, key=lambda x: x["weighted_score"])
    best_ei = max(rows, key=lambda x: x["efficiency_index"])
    print(f"\n  最高总分: {best['governance']} ({MODEL_META[best['governance']]['name']}) "
        f"= {best['weighted_score']:.4f}")
    print(f"  最高效率: {best_ei['governance']} ({MODEL_META[best_ei['governance']]['name']}) "
        f"EI = {best_ei['efficiency_index']:.6f}")
    topo_scores: dict[str, list] = {}
    for r in rows:
        topo = MODEL_META.get(r["governance"], {}).get("topology", "unknown")
        topo_scores.setdefault(topo, []).append(r["weighted_score"])
    print(f"\n  拓扑类型均分:")
    for topo, sc in sorted(topo_scores.items(), key=lambda x:
-sum(x[1])/len(x[1])):
        print(f"    {topo:<35} {sum(sc)/len(sc):.4f}")
    print()


def save_report(rows: list[dict], out_path: Path):
    report = {
        "experiment":   "exp-1",
        "timestamp":    datetime.now(timezone.utc).isoformat(),
        "task_weights": TASK_WEIGHTS,
        "results":      rows,
        "ranking": [
            {
                "rank":            i + 1,
                "governance":      r["governance"],
                "name":
MODEL_META[r["governance"]]["name"],
                "weighted_score":  r["weighted_score"],
                "efficiency_index": r["efficiency_index"],
            }
            for i, r in enumerate(
                sorted(rows, key=lambda x: x["weighted_score"],
reverse=True)
            )
        ],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False,
indent=2),
                        encoding="utf-8")
    print(f"  报告已保存: {out_path}")


# ── 主流程

def main():
    parser = argparse.ArgumentParser(
        description="EXP-1: Edict 治理模型 × pinchbench 评分")
    parser.add_argument("--edict-url",
                        default="http://localhost:8000",
                        help="Edict 后端地址")
    parser.add_argument("--governance", default="all",
                        help="逗号分隔的治理模型，或 'all'")
    parser.add_argument("--poll-timeout", type=int,
default=POLL_TIMEOUT,
                        help="每个任务最长等待秒数（默认300）")
    parser.add_argument("--dry-run",    action="store_true",
                        help="不实际调用 Edict，用随机分数验证流程")
    parser.add_argument("--out-dir",    default=str(RESULTS_DIR))
    args = parser.parse_args()

    gov_list = (ALL_GOVERNANCE_MODELS if args.governance == "all"
                else [g.strip() for g in args.governance.split(",")])

    unknown = [g for g in gov_list if g not in MODEL_META]
    if unknown:
        print(f"[错误] 未知治理模型: {unknown}")
        sys.exit(1)

    # 加载 pinchbench tasks
    loader = TaskLoader(PINCHBENCH / "tasks")
    all_tasks = loader.load_all_tasks()
    tasks_map = {t.task_id: t for t in all_tasks
                if t.task_id in GOVERNANCE_TASK_IDS}
    missing = [tid for tid in GOVERNANCE_TASK_IDS if tid not in
tasks_map]
    if missing:
        print(f"[错误] pinchbench 中找不到 tasks: {missing}")
        sys.exit(1)

    out_dir   = Path(args.out_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    skill_dir = PINCHBENCH  # lib_grading 需要

    print(f"\nEXP-1 启动")
    print(f"  Edict:    {args.edict_url}")
    print(f"  治理模型: {len(gov_list)} 种")
    print(f"  dry-run:  {args.dry_run}\n")

    rows = []

    for gi, governance in enumerate(gov_list, 1):
        meta = MODEL_META[governance]
        print(f"[{gi:02d}/{len(gov_list):02d}] {governance} ({meta['name']}, {meta['dynasty']})")

        task_scores  = {}
        exec_results = []

        for tid in GOVERNANCE_TASK_IDS:
            pinch_task = tasks_map[tid]
            print(f"  → {tid}", end="", flush=True)

            if args.dry_run:
                exec_result = _fake_execution_result(governance, tid)
                grade       = _fake_grade(tid, governance)
            else:
                # 1. 提交任务给 Edict
                try:
                    task_id = edict_create_task(
                        base_url        = args.edict_url,
                        title           = f"[EXP-1] {pinch_task.name} ({governance})",
                        description     = pinch_task.prompt,
                        governance_type = governance,
                    )
                except Exception as e:
                    print(f"  [提交失败] {e}")
                    continue

                # 2. 轮询直到终态
                edict_task = edict_poll_until_done(
                    args.edict_url, task_id,
timeout=args.poll_timeout
                )
                if edict_task is None:
                    print(f"  [超时] task_id={task_id}")
                    continue

                # 3. 构造 workspace + execution_result
                ws_dir = out_dir / governance / tid / "workspace"
                exec_result = edict_task_to_execution_result(
                    edict_task, str(ws_dir), pinch_task
                )

                # 4. pinchbench grading
                try:
                    grade = grade_task(
                        task             = pinch_task,
                        execution_result = exec_result,
                        skill_dir        = skill_dir,
                    )
                except Exception as e:
                    print(f"  [评分失败] {e}")
                    grade = GradeResult(
                        task_id      = tid,
                        score        = 0.0,
                        max_score    = 1.0,
                        grading_type = pinch_task.grading_type,
                        breakdown    = {},
                        notes        = str(e),
                    )

            task_scores[tid] = round(grade.score, 4)
            exec_results.append(exec_result)
            print(f"  {grade.score:.3f}")

        if not task_scores:
            print(f"  [跳过] 无有效结果")
            continue

        weighted = compute_weighted_score(task_scores)
        ei       = compute_efficiency_index(task_scores,
exec_results)
        rows.append({
            "governance":       governance,
            "weighted_score":   weighted,
            "efficiency_index": ei,
            "task_scores":      task_scores,
        })
        print(f"  加权总分: {weighted:.4f}  EI: {ei:.6f}")

    if not rows:
        print("\n[错误] 没有成功的运行结果")
        sys.exit(1)

    print_table(rows)
    save_report(rows, out_dir / f"exp1_{timestamp}.json")


if __name__ == "__main__":
    main()