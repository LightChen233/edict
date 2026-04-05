"""
evaluator.py — 自动评分 + 人工评分接口

自动评分：调用 Claude API 对任务输出打分（1–10）
人工评分：生成待评分 CSV，读取填写后的 CSV 写回 DB

用法：
    # 自动评分（T1–T3）
    python evaluator.py --runs results/runs.json --auto --tiers 1,2,3

    # 生成人工评分表（T4–T5）
    python evaluator.py --runs results/runs.json --export-csv results/manual_scoring.csv --tiers 4,5

    # 导入人工评分结果
    python evaluator.py --import-csv results/manual_scoring_filled.csv --dsn postgresql://...
"""

import argparse
import csv
import json
import os
from pathlib import Path

import anthropic


SCORING_PROMPT = """你是一位严格的任务质量评审员。请对以下 AI 任务输出打分（1–10 整数）。

评分标准：
- 10: 完美，超出预期，无任何问题
- 8–9: 优秀，完成目标，有小瑕疵
- 6–7: 良好，基本完成，有明显改进空间
- 4–5: 一般，部分完成，有重要遗漏
- 2–3: 较差，大部分未完成或有严重错误
- 1: 完全失败

任务描述：{title}
任务层级：T{tier}（{tier_name}）
任务领域：{domain}
治理模型：{governance_type}

任务输出：
{output}

请只输出一个 1–10 的整数，不要任何解释。"""

TIER_NAMES = {1: "Atomic", 2: "Sequential", 3: "Parallel", 4: "Deliberative", 5: "Complex"}


def auto_score(run: dict, client: anthropic.Anthropic) -> float | None:
    output = run.get("context_snapshot", {}).get("final_output", "")
    if not output:
        return None
    prompt = SCORING_PROMPT.format(
        title=run.get("task_title", run.get("task_id", "")),
        tier=run["task_tier"],
        tier_name=TIER_NAMES.get(run["task_tier"], ""),
        domain=run["task_domain"],
        governance_type=run["governance_type"],
        output=output[:2000],  # 截断防止超长
    )
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        score_str = msg.content[0].text.strip()
        score = float(score_str)
        return max(1.0, min(10.0, score))
    except Exception:
        return None


def export_csv(runs: list[dict], out_path: str, tiers: list[int]):
    """导出待人工评分的 CSV。"""
    rows = [r for r in runs if r["task_tier"] in tiers and r.get("quality_score") is None]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "task_tier", "task_domain", "governance_type",
            "task_title", "completion_sec", "rejection_count",
            "output_preview", "quality_score", "notes"
        ])
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "id": r["id"],
                "task_tier": r["task_tier"],
                "task_domain": r["task_domain"],
                "governance_type": r["governance_type"],
                "task_title": r.get("task_title", r.get("task_id", "")),
                "completion_sec": r.get("completion_sec", ""),
                "rejection_count": r.get("rejection_count", 0),
                "output_preview": str(r.get("context_snapshot", {}).get("final_output", ""))[:200],
                "quality_score": "",   # 人工填写
                "notes": "",
            })
    print(f"导出 {len(rows)} 条待评分记录 → {out_path}")


def import_csv(csv_path: str, dsn: str):
    """读取填写后的 CSV，更新 DB 中的 quality_score。"""
    import psycopg2
    conn = psycopg2.connect(dsn)
    updated = 0
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            score_str = row.get("quality_score", "").strip()
            if not score_str:
                continue
            try:
                score = float(score_str)
            except ValueError:
                continue
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE experiment_runs SET quality_score = %s WHERE id = %s",
                    (score, row["id"])
                )
            updated += 1
    conn.commit()
    conn.close()
    print(f"更新 {updated} 条评分记录")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs",       default="results/runs.json")
    parser.add_argument("--auto",       action="store_true", help="自动评分")
    parser.add_argument("--tiers",      default="1,2,3", help="逗号分隔的层级")
    parser.add_argument("--export-csv", default=None)
    parser.add_argument("--import-csv", default=None)
    parser.add_argument("--dsn",        default=None)
    parser.add_argument("--out",        default="results/runs_scored.json")
    args = parser.parse_args()

    tiers = [int(t) for t in args.tiers.split(",")]

    if args.import_csv:
        import_csv(args.import_csv, args.dsn)
        return

    with open(args.runs, encoding="utf-8") as f:
        runs = json.load(f)

    if args.export_csv:
        export_csv(runs, args.export_csv, tiers)
        return

    if args.auto:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        scored = 0
        for run in runs:
            if run["task_tier"] not in tiers:
                continue
            if run.get("quality_score") is not None:
                continue
            score = auto_score(run, client)
            if score is not None:
                run["quality_score"] = score
                scored += 1
        print(f"自动评分完成：{scored} 条")
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(runs, f, ensure_ascii=False, indent=2)
        print(f"写入 {args.out}")


if __name__ == "__main__":
    main()
