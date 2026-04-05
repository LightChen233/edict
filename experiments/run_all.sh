#!/usr/bin/env bash
# run_all.sh — 统一实验入口
#
# 用法：
#   ./experiments/run_all.sh --model anthropic/claude-sonnet-4-6
#   ./experiments/run_all.sh --model anthropic/claude-sonnet-4-6 --dry-run
#   ./experiments/run_all.sh --model anthropic/claude-sonnet-4-6 --exp 1,2   # 只跑指定实验
#   ./experiments/run_all.sh --model anthropic/claude-sonnet-4-6 --runs 3    # 每组跑3次

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXPERIMENTS="$REPO_ROOT/experiments"
RESULTS="$EXPERIMENTS/results"

# ── 默认参数 ──────────────────────────────────────────────────────────────────
MODEL=""
DRY_RUN=""
RUNS=1
EXPS="1,2,3"
MODELS_EXP2=""   # exp-2 额外模型（逗号分隔）
TIMEOUT_MULT=1.0

# ── 参数解析 ──────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --model)           MODEL="$2";        shift 2 ;;
    --dry-run)         DRY_RUN="--dry-run"; shift ;;
    --runs)            RUNS="$2";         shift 2 ;;
    --exp)             EXPS="$2";         shift 2 ;;
    --models-exp2)     MODELS_EXP2="$2";  shift 2 ;;
    --timeout-multiplier) TIMEOUT_MULT="$2"; shift 2 ;;
    *) echo "未知参数: $1"; exit 1 ;;
  esac
done

if [[ -z "$MODEL" ]]; then
  echo "用法: $0 --model <model_id> [--dry-run] [--runs N] [--exp 1,2,3]"
  echo "示例: $0 --model anthropic/claude-sonnet-4-6 --dry-run"
  exit 1
fi

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$RESULTS/run_all_${TIMESTAMP}.log"
mkdir -p "$RESULTS"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

log "======================================================"
log "  Governance as Algorithm — 实验套件"
log "  模型:    $MODEL"
log "  实验:    $EXPS"
log "  runs:    $RUNS"
log "  dry-run: ${DRY_RUN:-否}"
log "  时间:    $TIMESTAMP"
log "======================================================"

run_exp() {
  local exp_num="$1"
  local script="$EXPERIMENTS/exp-${exp_num}.py"

  if [[ ! -f "$script" ]]; then
    log "[跳过] exp-${exp_num}.py 不存在"
    return
  fi

  log ""
  log "── EXP-${exp_num} 开始 ──────────────────────────────────"

  case "$exp_num" in
    1)
      python3 "$script" \
        --model "$MODEL" \
        --runs "$RUNS" \
        --timeout-multiplier "$TIMEOUT_MULT" \
        --out-dir "$RESULTS/exp-1" \
        $DRY_RUN \
        2>&1 | tee -a "$LOG_FILE"
      ;;
    2)
      # exp-2 需要多个模型；若未指定则只用主模型
      local all_models="$MODEL"
      if [[ -n "$MODELS_EXP2" ]]; then
        all_models="${MODEL},${MODELS_EXP2}"
      fi
      python3 "$script" \
        --models "$all_models" \
        --timeout-multiplier "$TIMEOUT_MULT" \
        --out-dir "$RESULTS/exp-2" \
        $DRY_RUN \
        2>&1 | tee -a "$LOG_FILE"
      ;;
    3)
      python3 "$script" \
        --model "$MODEL" \
        --runs "$RUNS" \
        --timeout-multiplier "$TIMEOUT_MULT" \
        --out-dir "$RESULTS/exp-3" \
        $DRY_RUN \
        2>&1 | tee -a "$LOG_FILE"
      ;;
  esac

  local exit_code=$?
  if [[ $exit_code -eq 0 ]]; then
    log "── EXP-${exp_num} 完成 ✓"
  else
    log "── EXP-${exp_num} 失败 ✗ (exit=$exit_code)"
  fi
}

# ── 执行指定实验 ──────────────────────────────────────────────────────────────
IFS=',' read -ra EXP_LIST <<< "$EXPS"
for exp in "${EXP_LIST[@]}"; do
  run_exp "$exp"
done

log ""
log "======================================================"
log "  全部实验完成"
log "  结果目录: $RESULTS"
log "  日志:     $LOG_FILE"
log "======================================================"

# ── 汇总报告 ──────────────────────────────────────────────────────────────────
SUMMARY="$RESULTS/summary_${TIMESTAMP}.json"
python3 - <<PYEOF
import json, glob, os
from pathlib import Path

results_dir = Path("$RESULTS")
summary = {"timestamp": "$TIMESTAMP", "model": "$MODEL", "experiments": {}}

for exp_num in [1, 2, 3]:
    pattern = str(results_dir / f"exp-{exp_num}" / f"exp{exp_num}_*.json")
    files = sorted(glob.glob(pattern))
    if files:
        with open(files[-1], encoding="utf-8") as f:
            data = json.load(f)
        summary["experiments"][f"exp-{exp_num}"] = {
            "result_file": files[-1],
            "timestamp": data.get("timestamp", ""),
        }
        if exp_num == 1 and "ranking" in data:
            top3 = data["ranking"][:3]
            summary["experiments"]["exp-1"]["top3"] = [
                {"rank": r["rank"], "governance": r["governance"],
                 "name": r["name"], "score": r["weighted_score"]}
                for r in top3
            ]
        if exp_num == 2 and "variance_decomposition" in data:
            summary["experiments"]["exp-2"]["variance_decomposition"] = data["variance_decomposition"]
        if exp_num == 3:
            if "h4_orthogonality" in data:
                summary["experiments"]["exp-3"]["h4_supported"] = data["h4_orthogonality"].get("supported")
            if "h5_learning_curve" in data:
                summary["experiments"]["exp-3"]["h5_supported"] = data["h5_learning_curve"].get("supported")

with open("$SUMMARY", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print(f"汇总报告: $SUMMARY")
PYEOF
