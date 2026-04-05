"""
analysis.py — 统计分析：ANOVA + 交互效应 + 治理选择分类器

依赖：pip install pandas scipy scikit-learn matplotlib seaborn

用法：
    python analysis.py --runs results/runs_scored.json --out results/analysis/
"""

import argparse
import json
import os
from pathlib import Path

import pandas as pd
import numpy as np
from scipy import stats
from scipy.stats import f_oneway, kruskal
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.family'] = ['Arial Unicode MS', 'DejaVu Sans']

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report


# ── 数据加载 ──────────────────────────────────────────────────────────────────

def load_runs(path: str) -> pd.DataFrame:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    df = df[df["quality_score"].notna()].copy()
    df["efficiency_index"] = df.apply(
        lambda r: r["quality_score"] / (r["completion_sec"] * np.sqrt(max(r["token_cost"], 1)))
        if r["completion_sec"] and r["completion_sec"] > 0 else np.nan,
        axis=1
    )
    return df


# ── H1: 治理主导性 ────────────────────────────────────────────────────────────

def test_h1_governance_dominance(df: pd.DataFrame) -> dict:
    """H1: 治理模型解释 >40% 的质量方差。"""
    groups = [g["quality_score"].values for _, g in df.groupby("governance_type")]
    f_stat, p_val = f_oneway(*groups)

    # eta² = SS_between / SS_total
    grand_mean = df["quality_score"].mean()
    ss_between = sum(len(g) * (g["quality_score"].mean() - grand_mean) ** 2
                     for _, g in df.groupby("governance_type"))
    ss_total = ((df["quality_score"] - grand_mean) ** 2).sum()
    eta_sq = ss_between / ss_total

    return {
        "hypothesis": "H1",
        "f_statistic": round(f_stat, 4),
        "p_value": round(p_val, 6),
        "eta_squared": round(eta_sq, 4),
        "supported": eta_sq > 0.40 and p_val < 0.001,
        "note": f"治理模型解释 {eta_sq*100:.1f}% 质量方差",
    }


# ── H2: 速度-质量-自治三难 ────────────────────────────────────────────────────

def test_h2_trilemma(df: pd.DataFrame) -> dict:
    """H2: 无单一模型在质量/速度/自治三维同时最优。"""
    summary = df.groupby("governance_type").agg(
        quality=("quality_score", "mean"),
        speed=("completion_sec", lambda x: 1 / x.mean() if x.mean() > 0 else 0),
        autonomy=("autonomy_score", "mean"),
    ).dropna()

    # 归一化到 [0,1]
    for col in ["quality", "speed", "autonomy"]:
        mn, mx = summary[col].min(), summary[col].max()
        summary[f"{col}_norm"] = (summary[col] - mn) / (mx - mn + 1e-9)

    summary["composite"] = summary[["quality_norm", "speed_norm", "autonomy_norm"]].mean(axis=1)
    best = summary["composite"].idxmax()

    # 检验最优模型是否在三维上均显著领先
    best_row = summary.loc[best]
    dominated = all(best_row[f"{d}_norm"] > 0.8 for d in ["quality", "speed", "autonomy"])

    return {
        "hypothesis": "H2",
        "best_composite_model": best,
        "composite_score": round(summary.loc[best, "composite"], 4),
        "dominated_all_dims": dominated,
        "supported": not dominated,  # H2 成立 = 没有模型全面碾压
        "top5": summary.nlargest(5, "composite")[["quality", "speed", "autonomy", "composite"]].round(4).to_dict(),
    }


# ── H3: 任务-治理交互效应 ─────────────────────────────────────────────────────

def test_h3_interaction(df: pd.DataFrame) -> dict:
    """H3: 任务层级 × 治理模型存在显著交互效应。"""
    # 双因素 ANOVA（用 OLS 近似）
    try:
        import statsmodels.formula.api as smf
        model = smf.ols("quality_score ~ C(task_tier) * C(governance_type)", data=df).fit()
        from statsmodels.stats.anova import anova_lm
        anova_table = anova_lm(model, typ=2)
        interaction_p = float(anova_table.loc["C(task_tier):C(governance_type)", "PR(>F)"])
        interaction_f = float(anova_table.loc["C(task_tier):C(governance_type)", "F"])
        supported = interaction_p < 0.001
    except ImportError:
        # fallback：Kruskal-Wallis per tier
        results_per_tier = {}
        for tier in sorted(df["task_tier"].unique()):
            sub = df[df["task_tier"] == tier]
            groups = [g["quality_score"].values for _, g in sub.groupby("governance_type")]
            h, p = kruskal(*groups)
            results_per_tier[f"T{tier}"] = {"H": round(h, 3), "p": round(p, 6)}
        interaction_p = min(v["p"] for v in results_per_tier.values())
        interaction_f = None
        supported = interaction_p < 0.001

    return {
        "hypothesis": "H3",
        "interaction_F": round(interaction_f, 4) if interaction_f else None,
        "interaction_p": round(interaction_p, 6),
        "supported": supported,
        "note": "任务层级×治理模型交互效应" + (" 显著" if supported else " 不显著"),
    }


# ── H4: 机制正交性 ────────────────────────────────────────────────────────────

def test_h4_mechanism_orthogonality(df: pd.DataFrame) -> dict:
    """H4: 三种跨制度机制叠加效果可加，无显著交互项。"""
    df2 = df.copy()
    df2["has_keju"]   = df2["mechanisms"].apply(lambda m: "ke_ju"     in (m or []))
    df2["has_yushi"]  = df2["mechanisms"].apply(lambda m: "yu_shi_tai" in (m or []))
    df2["has_gonguo"] = df2["mechanisms"].apply(lambda m: "gong_guo_bu" in (m or []))

    if df2["has_keju"].sum() < 10:
        return {"hypothesis": "H4", "supported": None, "note": "机制数据不足，跳过"}

    try:
        import statsmodels.formula.api as smf
        model = smf.ols(
            "quality_score ~ has_keju + has_yushi + has_gonguo"
            " + has_keju:has_yushi + has_keju:has_gonguo + has_yushi:has_gonguo",
            data=df2
        ).fit()
        interaction_pvals = {
            "keju×yushi":  model.pvalues.get("has_keju:has_yushi[T.True]", 1.0),
            "keju×gonguo": model.pvalues.get("has_keju:has_gonguo[T.True]", 1.0),
            "yushi×gonguo":model.pvalues.get("has_yushi:has_gonguo[T.True]", 1.0),
        }
        supported = all(p > 0.05 for p in interaction_pvals.values())
        return {
            "hypothesis": "H4",
            "interaction_pvalues": {k: round(v, 4) for k, v in interaction_pvals.items()},
            "supported": supported,
            "note": "机制交互项均不显著" if supported else "存在显著机制交互项",
        }
    except ImportError:
        return {"hypothesis": "H4", "supported": None, "note": "需要 statsmodels"}


# ── H5: 功过簿学习曲线 ────────────────────────────────────────────────────────

def test_h5_learning_curve(df: pd.DataFrame) -> dict:
    """H5: 功过簿追踪下系统效率随任务数单调提升。"""
    df_gonguo = df[df["mechanisms"].apply(lambda m: "gong_guo_bu" in (m or []))].copy()
    if len(df_gonguo) < 20:
        return {"hypothesis": "H5", "supported": None, "note": "功过簿数据不足"}

    df_gonguo = df_gonguo.sort_values("run_at")
    df_gonguo["task_seq"] = range(len(df_gonguo))

    # Spearman 相关：任务序号 vs 效率指数
    corr, p = stats.spearmanr(df_gonguo["task_seq"], df_gonguo["efficiency_index"].fillna(0))
    return {
        "hypothesis": "H5",
        "spearman_r": round(corr, 4),
        "p_value": round(p, 6),
        "supported": corr > 0 and p < 0.05,
        "note": f"效率随任务数{'单调提升' if corr > 0 else '未提升'}（r={corr:.3f}）",
    }


# ── H6: 治理选择可学习 ────────────────────────────────────────────────────────

def test_h6_selector(df: pd.DataFrame) -> dict:
    """H6: 基于任务元数据的分类器可达 oracle 效率的 >85%。"""
    # Oracle：每个任务选最优治理模型
    oracle = df.groupby(["task_id", "governance_type"])["efficiency_index"].mean().reset_index()
    best_gov = oracle.loc[oracle.groupby("task_id")["efficiency_index"].idxmax()]
    best_gov = best_gov.set_index("task_id")["governance_type"]

    # 特征：tier, domain
    df2 = df.drop_duplicates("task_id").copy()
    df2["best_governance"] = df2["task_id"].map(best_gov)
    df2 = df2.dropna(subset=["best_governance"])

    if len(df2) < 30:
        return {"hypothesis": "H6", "supported": None, "note": "任务数不足"}

    le_domain = LabelEncoder()
    X = np.column_stack([
        df2["task_tier"].values,
        le_domain.fit_transform(df2["task_domain"].values),
    ])
    le_gov = LabelEncoder()
    y = le_gov.fit_transform(df2["best_governance"].values)

    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(clf, X, y, cv=cv, scoring="accuracy")

    # Oracle 效率基准
    oracle_ei = df.merge(best_gov.rename("best_gov"), left_on="task_id", right_index=True)
    oracle_ei = oracle_ei[oracle_ei["governance_type"] == oracle_ei["best_gov"]]["efficiency_index"].mean()
    mean_ei = df["efficiency_index"].mean()
    oracle_ratio = mean_ei / oracle_ei if oracle_ei > 0 else 0

    return {
        "hypothesis": "H6",
        "classifier_accuracy": round(scores.mean(), 4),
        "classifier_std": round(scores.std(), 4),
        "oracle_efficiency_ratio": round(oracle_ratio, 4),
        "supported": scores.mean() > 0.6 and oracle_ratio > 0.85,
        "note": f"分类器准确率 {scores.mean()*100:.1f}%，达 oracle 效率 {oracle_ratio*100:.1f}%",
    }


# ── 可视化 ────────────────────────────────────────────────────────────────────

def plot_quality_by_governance(df: pd.DataFrame, out_dir: str):
    fig, ax = plt.subplots(figsize=(14, 6))
    order = df.groupby("governance_type")["quality_score"].mean().sort_values(ascending=False).index
    data = [df[df["governance_type"] == g]["quality_score"].values for g in order]
    ax.boxplot(data, labels=order, vert=True)
    ax.set_title("Quality Score by Governance Model")
    ax.set_xlabel("Governance Type")
    ax.set_ylabel("Quality Score (1–10)")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(f"{out_dir}/quality_by_governance.png", dpi=150)
    plt.close()


def plot_tier_governance_heatmap(df: pd.DataFrame, out_dir: str):
    pivot = df.groupby(["task_tier", "governance_type"])["quality_score"].mean().unstack()
    fig, ax = plt.subplots(figsize=(16, 5))
    im = ax.imshow(pivot.values, aspect="auto", cmap="RdYlGn", vmin=1, vmax=10)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([f"T{t}" for t in pivot.index])
    plt.colorbar(im, ax=ax, label="Mean Quality Score")
    ax.set_title("Mean Quality Score: Task Tier × Governance Model")
    plt.tight_layout()
    plt.savefig(f"{out_dir}/tier_governance_heatmap.png", dpi=150)
    plt.close()


def plot_efficiency_index(df: pd.DataFrame, out_dir: str):
    ei = df.groupby("governance_type")["efficiency_index"].mean().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(12, 5))
    ei.plot(kind="bar", ax=ax, color="steelblue")
    ax.set_title("Efficiency Index (Q / T·√C) by Governance Model")
    ax.set_ylabel("Efficiency Index")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(f"{out_dir}/efficiency_index.png", dpi=150)
    plt.close()


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", default="results/runs_scored.json")
    parser.add_argument("--out",  default="results/analysis")
    args = parser.parse_args()

    Path(args.out).mkdir(parents=True, exist_ok=True)
    df = load_runs(args.runs)
    print(f"加载 {len(df)} 条有效运行记录，覆盖 {df['governance_type'].nunique()} 种治理模型")

    results = {}
    for test_fn in [
        test_h1_governance_dominance,
        test_h2_trilemma,
        test_h3_interaction,
        test_h4_mechanism_orthogonality,
        test_h5_learning_curve,
        test_h6_selector,
    ]:
        r = test_fn(df)
        results[r["hypothesis"]] = r
        status = "✓ 支持" if r.get("supported") else ("? 数据不足" if r.get("supported") is None else "✗ 不支持")
        print(f"  {r['hypothesis']}: {status} — {r.get('note', '')}")

    # 写 JSON 报告
    report_path = f"{args.out}/hypothesis_results.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n假设检验报告 → {report_path}")

    # 可视化
    try:
        plot_quality_by_governance(df, args.out)
        plot_tier_governance_heatmap(df, args.out)
        plot_efficiency_index(df, args.out)
        print(f"图表 → {args.out}/")
    except Exception as e:
        print(f"可视化失败（可能缺少 matplotlib）: {e}")

    # 描述性统计
    summary = df.groupby("governance_type").agg(
        n=("quality_score", "count"),
        quality_mean=("quality_score", "mean"),
        quality_std=("quality_score", "std"),
        completion_mean=("completion_sec", "mean"),
        token_mean=("token_cost", "mean"),
        rejection_mean=("rejection_count", "mean"),
        ei_mean=("efficiency_index", "mean"),
    ).round(3)
    summary.to_csv(f"{args.out}/summary_by_governance.csv")
    print(f"描述统计 → {args.out}/summary_by_governance.csv")


if __name__ == "__main__":
    main()
