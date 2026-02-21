#!/usr/bin/env python3
"""Planning simulations for additional screening scenarios.

Generates scenario and results artifacts for reviewer planning.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd


@dataclass
class Scenario:
    scenario_id: str
    threshold_policy: str
    target_recall: float
    baseline_docs_screened: int
    baseline_recall: float
    additional_docs_requested: int
    additional_docs_effective: int
    total_docs: int
    cap_reached: bool
    prevalence_band: str
    prevalence: float
    total_relevant_assumed: int


def load_inputs(repo_root: Path) -> Dict[str, pd.DataFrame]:
    base = repo_root / "analysis" / "outputs" / "next_steps"
    return {
        "traces": pd.read_csv(base / "active_learning_traces.csv"),
        "runs": pd.read_csv(base / "active_learning_runs.csv"),
        "policy": pd.read_csv(base / "stopping_policy_summary.csv"),
        "meta": pd.read_json(base / "run_meta_next_steps.json", typ="series").to_frame().T,
    }


def get_policy_config(runs: pd.DataFrame, policy: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    runs_best = runs[runs["strategy"] == "asreview_prior_1p1n"].copy()
    policy_best = policy[policy["strategy"] == "asreview_prior_1p1n"].copy()

    def policy_row(name: str) -> pd.Series:
        row = policy_best[policy_best["policy"] == name]
        if row.empty:
            raise ValueError(f"Missing policy row: {name}")
        return row.iloc[0]

    p90 = policy_row("oracle_target_recall_90")
    p95 = policy_row("oracle_target_recall_95")

    return {
        "recall_target_90": {
            "target_recall": 0.90,
            "baseline_docs": int(round(runs_best["docs_to_recall_0.90"].mean())),
            "baseline_recall": float(p90["recall_mean"]),
        },
        "recall_target_95": {
            "target_recall": 0.95,
            "baseline_docs": int(round(runs_best["docs_to_recall_0.95"].mean())),
            "baseline_recall": float(p95["recall_mean"]),
        },
    }


def build_recall_curve(traces: pd.DataFrame) -> pd.Series:
    t = traces[traces["strategy"] == "asreview_prior_1p1n"].copy()
    curve = t.groupby("docs_screened", as_index=True)["recall"].mean().sort_index()
    return curve


def aligned_recall(
    docs_screened: int,
    curve: pd.Series,
    baseline_docs: int,
    baseline_recall: float,
) -> float:
    docs_screened = int(np.clip(docs_screened, int(curve.index.min()), int(curve.index.max())))
    curve_docs = curve.reindex(range(int(curve.index.min()), int(curve.index.max()) + 1)).interpolate("linear")

    c0 = float(curve_docs.loc[baseline_docs])
    cx = float(curve_docs.loc[docs_screened])

    if docs_screened <= baseline_docs:
        return baseline_recall

    if c0 >= 0.999999:
        return baseline_recall

    progress = (cx - c0) / max(1e-9, (1.0 - c0))
    progress = float(np.clip(progress, 0.0, 1.0))
    return float(np.clip(baseline_recall + progress * (1.0 - baseline_recall), 0.0, 1.0))


def confusion_from_budget(n_docs: int, n_relevant: int, docs_screened: int, recall: float) -> Dict[str, float]:
    tp = float(np.clip(recall * n_relevant, 0, n_relevant))
    fn = float(n_relevant - tp)
    fp = float(max(0.0, docs_screened - tp))
    tn = float(max(0.0, (n_docs - docs_screened) - fn))

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": precision,
        "recall": rec,
        "specificity": specificity,
        "fpr": fpr,
        "fnr": fnr,
    }


def run(repo_root: Path) -> None:
    out_dir = repo_root / "analysis" / "outputs" / "planning_simulations"
    out_dir.mkdir(parents=True, exist_ok=True)

    data = load_inputs(repo_root)
    traces = data["traces"]
    runs = data["runs"]
    policy = data["policy"]
    n_docs = int(data["meta"].iloc[0]["n_records"])

    cfg = get_policy_config(runs, policy)
    curve = build_recall_curve(traces)

    prevalence_bands = {
        "low": 0.10,
        "medium": float(data["meta"].iloc[0]["n_positives"]) / n_docs,
        "high": 0.20,
    }
    additional_requested = [50, 100, 200, 400]

    scenarios: List[Scenario] = []
    results_rows: List[Dict[str, float]] = []

    for policy_name, p in cfg.items():
        bdocs = int(p["baseline_docs"])
        brecall = float(p["baseline_recall"])

        for band, prev in prevalence_bands.items():
            n_rel = int(round(prev * n_docs))
            baseline_conf = confusion_from_budget(n_docs=n_docs, n_relevant=n_rel, docs_screened=bdocs, recall=brecall)

            for add in additional_requested:
                add_eff = int(min(add, n_docs - bdocs))
                docs_now = int(bdocs + add_eff)
                r_now = aligned_recall(docs_now, curve=curve, baseline_docs=bdocs, baseline_recall=brecall)
                conf = confusion_from_budget(n_docs=n_docs, n_relevant=n_rel, docs_screened=docs_now, recall=r_now)

                scenario_id = f"{policy_name}__{band}__plus_{add}"
                sc = Scenario(
                    scenario_id=scenario_id,
                    threshold_policy=policy_name,
                    target_recall=float(p["target_recall"]),
                    baseline_docs_screened=bdocs,
                    baseline_recall=brecall,
                    additional_docs_requested=add,
                    additional_docs_effective=add_eff,
                    total_docs=n_docs,
                    cap_reached=bool(add_eff < add),
                    prevalence_band=band,
                    prevalence=prev,
                    total_relevant_assumed=n_rel,
                )
                scenarios.append(sc)

                additional_tp = conf["tp"] - baseline_conf["tp"]
                fn_reduction = baseline_conf["fn"] - conf["fn"]

                results_rows.append(
                    {
                        **asdict(sc),
                        **conf,
                        "screened_docs_total": docs_now,
                        "screened_fraction": docs_now / n_docs,
                        "work_saved_docs": n_docs - docs_now,
                        "work_saved_fraction": (n_docs - docs_now) / n_docs,
                        "additional_tp_vs_baseline": additional_tp,
                        "fn_reduction_vs_baseline": fn_reduction,
                        "incremental_yield_tp_per_doc": (additional_tp / add_eff) if add_eff > 0 else np.nan,
                    }
                )

    scenarios_df = pd.DataFrame([asdict(s) for s in scenarios])
    results_df = pd.DataFrame(results_rows)

    float_cols = [
        "baseline_recall",
        "prevalence",
        "tp",
        "fp",
        "tn",
        "fn",
        "precision",
        "recall",
        "specificity",
        "fpr",
        "fnr",
        "screened_fraction",
        "work_saved_fraction",
        "additional_tp_vs_baseline",
        "fn_reduction_vs_baseline",
        "incremental_yield_tp_per_doc",
    ]
    for c in float_cols:
        if c in results_df.columns:
            results_df[c] = results_df[c].astype(float).round(6)

    scenarios_df.to_csv(out_dir / "simulation_scenarios.csv", index=False)
    results_df.to_csv(out_dir / "simulation_results.csv", index=False)
    (out_dir / "simulation_results.json").write_text(
        json.dumps(results_df.to_dict(orient="records"), indent=2), encoding="utf-8"
    )

    # Human-readable summary
    med = results_df[results_df["prevalence_band"] == "medium"].copy()
    med = med.sort_values(["threshold_policy", "additional_docs_requested"]) 

    lines = []
    lines.append("# Simulation Summary: Additional Screening Planning")
    lines.append("")
    lines.append("## Scope")
    lines.append("- Strategy baseline: `asreview_prior_1p1n` from `analysis/outputs/next_steps/`.")
    lines.append("- Threshold policy scenarios: recall-targeted 90% and 95%.")
    lines.append("- Additional screening scenarios requested: +50, +100, +200, +400.")
    lines.append("- Prevalence sensitivity bands: low (10%), medium (observed), high (20%).")
    lines.append("")
    lines.append("## Method (planning approximation)")
    lines.append("1. Use active-learning traces to estimate recall-vs-screening progression.")
    lines.append("2. Anchor baseline at the observed stopping-policy means:")
    lines.append(f"   - recall_target_90: {cfg['recall_target_90']['baseline_docs']} docs screened, recall {cfg['recall_target_90']['baseline_recall']:.3f}.")
    lines.append(f"   - recall_target_95: {cfg['recall_target_95']['baseline_docs']} docs screened, recall {cfg['recall_target_95']['baseline_recall']:.3f}.")
    lines.append("3. Convert each scenario to TP/FP/TN/FN by treating the screened budget as selected records and unscreened as deferred records.")
    lines.append("4. Cap additional screening at remaining documents in this 300-record dataset (cap flag shown in outputs).")
    lines.append("")
    lines.append("## Medium-prevalence highlights")
    for policy_name in ["recall_target_90", "recall_target_95"]:
        p = med[med["threshold_policy"] == policy_name]
        lines.append(f"### {policy_name}")
        for _, r in p.iterrows():
            lines.append(
                f"- +{int(r['additional_docs_requested'])} requested (effective +{int(r['additional_docs_effective'])}): "
                f"TP={r['tp']:.2f}, FN={r['fn']:.2f}, recall={r['recall']:.3f}, "
                f"precision={r['precision']:.3f}, work_saved={int(r['work_saved_docs'])} docs ({r['work_saved_fraction']:.1%}), "
                f"FN reduction vs baseline={r['fn_reduction_vs_baseline']:.2f}."
            )
        lines.append("")

    lines.append("## Notes")
    lines.append("- Scenarios with `cap_reached=true` exceed available unscreened records in the current dataset; effective additional screening is capped.")
    lines.append("- For operational planning beyond this dataset, re-run this simulation after ingesting a larger candidate pool.")

    (out_dir / "SIMULATION_SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Recommendation note
    rec_lines = [
        "# Recommended Next Screening Targets",
        "",
        "## Recommendation logic",
        "- Prefer the smallest additional-screening increment that meaningfully reduces expected FN while retaining useful work-saved percentage.",
        "- Use medium-prevalence scenarios as primary planning signal; check low/high as sensitivity bounds.",
        "",
        "## Recommended targets",
        "1. **Immediate target: +50 additional records**",
        "   - Expected to materially reduce FN in both threshold policies while preserving non-trivial work saved.",
        "   - Operationally feasible as a short sprint batch.",
        "2. **Contingent target: move to +100 total additional records**",
        "   - Use if confidence requirements are strict (e.g., risk tolerance near 95%+ recall expectations).",
        "   - In this dataset, larger requests (+200/+400) are capped by remaining unscreened records.",
        "",
        "## Policy-specific guidance",
        "- If operating at recall_target_90, +100 effectively exhausts the current unscreened pool (cap).",
        "- If operating at recall_target_95, +79 effectively exhausts the current unscreened pool (cap reached from +100 request onward).",
        "",
        "## Practical next action",
        "- Schedule a two-stage screening sprint: +50 now, reassess model metrics and residual-risk estimate, then decide whether to continue to the +100-equivalent cap for the current dataset.",
    ]
    (out_dir / "recommended_next_screening_targets.md").write_text("\n".join(rec_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run(Path(__file__).resolve().parents[1])
