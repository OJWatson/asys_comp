#!/usr/bin/env python3
"""Build app-ready JSON artifacts from analysis outputs.

This script is intentionally file-based and local-only so it can run without
external credentials.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

DEFAULT_CONFIG = {
    "analysis_outputs_dir": "analysis/outputs",
    "app_artifacts_dir": "app/data/artifacts",
    "preferred_strategy": "asreview_prior_1p1n",
    "primary_prevalence_band": "medium",
    "policy_aliases": {
        "oracle_target_recall_90": "recall_target_90",
        "oracle_target_recall_95": "recall_target_95",
    },
}


@dataclass(frozen=True)
class SourceFile:
    name: str
    path: Path


def load_config(config_path: Path) -> Dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if config_path.exists():
        user_cfg = json.loads(config_path.read_text(encoding="utf-8"))
        cfg.update(user_cfg)

    if not isinstance(cfg.get("policy_aliases"), dict) or not cfg["policy_aliases"]:
        raise ValueError("config.policy_aliases must be a non-empty object")
    return cfg


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit_or_unknown(repo_root: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return out
    except Exception:
        return "unknown"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_targets_from_markdown(md: str) -> Dict[str, int]:
    immediate = re.search(r"Immediate target:\s*\+(\d+)", md)
    contingent = re.search(r"Contingent target:\s*move to\s*\+(\d+)", md)
    return {
        "immediate_additional_docs": int(immediate.group(1)) if immediate else 50,
        "contingent_additional_docs": int(contingent.group(1)) if contingent else 100,
    }


def confusion(n_docs: int, n_relevant: int, docs_screened: int, recall: float) -> Dict[str, float]:
    tp = max(0.0, min(float(n_relevant), float(n_relevant) * float(recall)))
    fn = max(0.0, float(n_relevant) - tp)
    fp = max(0.0, float(docs_screened) - tp)
    tn = max(0.0, float(n_docs - docs_screened) - fn)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0

    return {
        "tp": round(tp, 6),
        "fp": round(fp, 6),
        "tn": round(tn, 6),
        "fn": round(fn, 6),
        "precision": round(precision, 6),
        "recall": round(rec, 6),
        "fpr": round(fpr, 6),
        "fnr": round(fnr, 6),
    }


def build_fn_fp_story(
    policy_summary: pd.DataFrame,
    simulations: pd.DataFrame,
    *,
    preferred_strategy: str,
    prevalence_band: str,
    n_docs: int,
    n_relevant: int,
    policy_aliases: Dict[str, str],
) -> Dict[str, Any]:
    policy_rows = policy_summary[policy_summary["strategy"] == preferred_strategy].copy()
    policy_rows = policy_rows[policy_rows["policy"].isin(policy_aliases.keys())]

    scenarios: List[Dict[str, Any]] = []
    for raw_policy, threshold_policy in policy_aliases.items():
        row = policy_rows[policy_rows["policy"] == raw_policy]
        if row.empty:
            continue
        row0 = row.iloc[0]

        base_docs = int(round(float(row0["docs_screened_mean"])))
        base_recall = float(row0["recall_mean"])
        base_conf = confusion(n_docs=n_docs, n_relevant=n_relevant, docs_screened=base_docs, recall=base_recall)

        baseline = {
            "threshold_policy": threshold_policy,
            "display_name": raw_policy,
            "additional_docs_requested": 0,
            "additional_docs_effective": 0,
            "screened_docs_total": base_docs,
            "screened_fraction": round(base_docs / n_docs, 6),
            "work_saved_docs": n_docs - base_docs,
            "work_saved_fraction": round((n_docs - base_docs) / n_docs, 6),
            "fn_reduction_vs_baseline": 0.0,
            "additional_tp_vs_baseline": 0.0,
            **base_conf,
        }

        sim_subset = simulations[
            (simulations["threshold_policy"] == threshold_policy)
            & (simulations["prevalence_band"] == prevalence_band)
        ].copy()
        sim_subset = sim_subset.sort_values("additional_docs_requested")

        rows = [baseline]
        for _, r in sim_subset.iterrows():
            rows.append(
                {
                    "threshold_policy": threshold_policy,
                    "display_name": raw_policy,
                    "additional_docs_requested": int(r["additional_docs_requested"]),
                    "additional_docs_effective": int(r["additional_docs_effective"]),
                    "screened_docs_total": int(r["screened_docs_total"]),
                    "screened_fraction": float(r["screened_fraction"]),
                    "work_saved_docs": int(r["work_saved_docs"]),
                    "work_saved_fraction": float(r["work_saved_fraction"]),
                    "fn_reduction_vs_baseline": float(r["fn_reduction_vs_baseline"]),
                    "additional_tp_vs_baseline": float(r["additional_tp_vs_baseline"]),
                    "tp": float(r["tp"]),
                    "fp": float(r["fp"]),
                    "tn": float(r["tn"]),
                    "fn": float(r["fn"]),
                    "precision": float(r["precision"]),
                    "recall": float(r["recall"]),
                    "fpr": float(r["fpr"]),
                    "fnr": float(r["fnr"]),
                    "cap_reached": bool(r["cap_reached"]),
                }
            )

        scenarios.append(
            {
                "threshold_policy": threshold_policy,
                "display_name": raw_policy,
                "target_recall": 0.9 if "90" in raw_policy else 0.95,
                "rows": rows,
                "baseline": baseline,
            }
        )

    return {
        "strategy": preferred_strategy,
        "prevalence_band": prevalence_band,
        "n_docs": n_docs,
        "n_relevant_assumed": n_relevant,
        "policies": scenarios,
    }


def build_artifacts(repo_root: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    outputs = repo_root / config["analysis_outputs_dir"]
    app_artifacts_dir = repo_root / config["app_artifacts_dir"]
    app_artifacts_dir.mkdir(parents=True, exist_ok=True)

    source_files = [
        SourceFile("metrics_best", outputs / "improved" / "metrics_best.json"),
        SourceFile("model_summary", outputs / "improved" / "model_summary.csv"),
        SourceFile("comparison", outputs / "improved" / "comparison_baseline_vs_improved.csv"),
        SourceFile("next_meta", outputs / "next_steps" / "run_meta_next_steps.json"),
        SourceFile("stopping_policy", outputs / "next_steps" / "stopping_policy_summary.csv"),
        SourceFile("nested_cv_summary", outputs / "next_steps" / "nested_cv_seed_sweep_summary.csv"),
        SourceFile("benchmark_summary", outputs / "benchmarks" / "model_benchmark_summary.csv"),
        SourceFile("benchmark_summary_json", outputs / "benchmarks" / "model_benchmark_summary.json"),
        SourceFile("benchmark_env", outputs / "benchmarks" / "environment_model_availability.json"),
        SourceFile("benchmark_report", outputs / "benchmarks" / "MODEL_BENCHMARK_REPORT.md"),
        SourceFile("lab_manifest", outputs / "next_steps" / "production_ranking_manifest.json"),
        SourceFile("sim_results", outputs / "planning_simulations" / "simulation_results.csv"),
        SourceFile(
            "recommended_targets",
            outputs / "planning_simulations" / "recommended_next_screening_targets.md",
        ),
        SourceFile("sim_summary", outputs / "planning_simulations" / "SIMULATION_SUMMARY.md"),
    ]

    missing = [str(s.path) for s in source_files if not s.path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required source files: {missing}")

    metrics_best = json.loads((outputs / "improved" / "metrics_best.json").read_text(encoding="utf-8"))
    meta = json.loads((outputs / "next_steps" / "run_meta_next_steps.json").read_text(encoding="utf-8"))
    lab_manifest = json.loads((outputs / "next_steps" / "production_ranking_manifest.json").read_text(encoding="utf-8"))

    model_summary = pd.read_csv(outputs / "improved" / "model_summary.csv")
    comparison = pd.read_csv(outputs / "improved" / "comparison_baseline_vs_improved.csv")
    stopping_policy = pd.read_csv(outputs / "next_steps" / "stopping_policy_summary.csv")
    nested_cv_summary = pd.read_csv(outputs / "next_steps" / "nested_cv_seed_sweep_summary.csv")
    benchmark_summary = pd.read_csv(outputs / "benchmarks" / "model_benchmark_summary.csv")
    benchmark_summary_json = json.loads(
        (outputs / "benchmarks" / "model_benchmark_summary.json").read_text(encoding="utf-8")
    )
    benchmark_env = json.loads((outputs / "benchmarks" / "environment_model_availability.json").read_text(encoding="utf-8"))
    sim_results = pd.read_csv(outputs / "planning_simulations" / "simulation_results.csv")
    recommended_md = (outputs / "planning_simulations" / "recommended_next_screening_targets.md").read_text(
        encoding="utf-8"
    )
    sim_summary_md = (outputs / "planning_simulations" / "SIMULATION_SUMMARY.md").read_text(encoding="utf-8")

    target_cfg = parse_targets_from_markdown(recommended_md)

    benchmark_rows_df = benchmark_summary.sort_values("rank").copy()
    benchmark_rows = benchmark_rows_df.to_dict(orient="records")

    benchmark_winner = benchmark_rows[0] if benchmark_rows else None
    benchmark_runner_up = benchmark_rows[1] if len(benchmark_rows) > 1 else None

    benchmark_insights: List[str] = list(benchmark_summary_json.get("key_findings", []))
    if benchmark_winner and benchmark_runner_up:
        ap_gap = float(benchmark_winner["average_precision_mean"] - benchmark_runner_up["average_precision_mean"])
        benchmark_insights.append(
            (
                f"Winner vs runner-up AP gap is {ap_gap:.4f}; treat as near-tie and prioritize operational stability "
                f"if both perform similarly in future refreshes."
            )
        )

    fastest_row = benchmark_rows_df.sort_values("fit_seconds_mean", ascending=True).iloc[0].to_dict()
    benchmark_insights.append(
        (
            f"Runtime trade-off: {fastest_row['display_name']} trains fastest "
            f"({float(fastest_row['fit_seconds_mean']):.3f}s/fold mean)."
        )
    )

    blocked_models = benchmark_summary_json.get("blocked_models", [])
    env_blocked = benchmark_env.get("blocked_models", [])
    if env_blocked:
        existing_ids = {str(x.get("model_id")) for x in blocked_models}
        for row in env_blocked:
            if str(row.get("model_id")) not in existing_ids:
                blocked_models.append(row)

    n_docs = int(meta["n_records"])
    n_positives = int(meta["n_positives"])
    prevalence = n_positives / n_docs if n_docs else 0.0

    fn_fp_story = build_fn_fp_story(
        stopping_policy,
        sim_results,
        preferred_strategy=config["preferred_strategy"],
        prevalence_band=config["primary_prevalence_band"],
        n_docs=n_docs,
        n_relevant=n_positives,
        policy_aliases=config["policy_aliases"],
    )

    baseline_cards = []
    for p in fn_fp_story["policies"]:
        b = p["baseline"]
        baseline_cards.append(
            {
                "threshold_policy": p["threshold_policy"],
                "target_recall": p["target_recall"],
                "docs_screened_mean": b["screened_docs_total"],
                "work_saved_docs": b["work_saved_docs"],
                "expected_fn": round(b["fn"], 2),
                "expected_fp": round(b["fp"], 2),
                "estimated_recall": b["recall"],
                "estimated_precision": b["precision"],
            }
        )

    selected_policy = fn_fp_story["policies"][0] if fn_fp_story["policies"] else None
    selected_row = None
    if selected_policy:
        for row in selected_policy["rows"]:
            if int(row["additional_docs_requested"]) == target_cfg["immediate_additional_docs"]:
                selected_row = row
                break

    overview = {
        "generated_at": now_utc_iso(),
        "project": {
            "name": "ASReview Screening Model",
            "dataset_records": n_docs,
            "known_relevant": n_positives,
            "estimated_prevalence": round(prevalence, 6),
            "preferred_strategy": config["preferred_strategy"],
            "prevalence_band": config["primary_prevalence_band"],
        },
        "model_snapshot": {
            "best_model": metrics_best.get("best_model"),
            "average_precision": metrics_best.get("average_precision"),
            "roc_auc": metrics_best.get("roc_auc"),
            "recall_at_20": metrics_best.get("recall@20"),
            "recall_at_50": metrics_best.get("recall@50"),
            "screen_fraction_recall_90": metrics_best.get("screening_fraction_at_recall_0.90"),
            "screen_fraction_recall_95": metrics_best.get("screening_fraction_at_recall_0.95"),
            "benchmark_winner_model": benchmark_winner.get("model_id") if benchmark_winner else None,
            "benchmark_winner_ap": benchmark_winner.get("average_precision_mean") if benchmark_winner else None,
            "benchmark_winner_wss95": benchmark_winner.get("wss@95_mean") if benchmark_winner else None,
        },
        "lab_queue_snapshot": {
            "n_records": lab_manifest.get("n_records"),
            "priority_bucket_counts": lab_manifest.get("priority_bucket_counts"),
            "score_range": lab_manifest.get("score_range"),
        },
        "risk_baselines": baseline_cards,
        "recommendation": {
            "immediate_additional_docs": target_cfg["immediate_additional_docs"],
            "contingent_additional_docs": target_cfg["contingent_additional_docs"],
            "expected_fn_after_immediate": round(selected_row["fn"], 2) if selected_row else None,
            "expected_fn_reduction_after_immediate": round(selected_row["fn_reduction_vs_baseline"], 2)
            if selected_row
            else None,
        },
    }

    methods_results = {
        "generated_at": now_utc_iso(),
        "methods": [
            "Text preprocessing with title+abstract concatenation and decision normalization.",
            "Model comparison across imbalance-aware baselines including calibrated SVM with word+char TF-IDF.",
            "Expanded NLP benchmark with repeated stratified CV across baseline, improved, and additional lightweight candidates.",
            "Evaluation emphasizes ranking and high-recall screening behavior, not threshold-0.5 accuracy only.",
            "Active-learning simulations with policy-based stopping diagnostics and seed-strategy sweeps.",
            "Leakage-safe queue export for reviewer operations with sensitive decision fields removed.",
        ],
        "model_leaderboard": model_summary.to_dict(orient="records"),
        "baseline_vs_improved": comparison.to_dict(orient="records"),
        "nested_cv_summary": nested_cv_summary.to_dict(orient="records"),
        "benchmarking": {
            "protocol": benchmark_summary_json.get("split_protocol", {}),
            "metrics_reported": benchmark_summary_json.get("metrics_reported", []),
            "model_results": benchmark_rows,
            "winner": benchmark_winner,
            "runner_up": benchmark_runner_up,
            "interpretation": benchmark_insights,
            "blocked_models": blocked_models,
            "nemo_status": benchmark_env.get("environment", {}).get("nemo", {}),
            "environment_notes": benchmark_env.get("environment", {}).get("stronger_heavy_model_candidates", []),
        },
    }

    fn_fp_risk = {
        "generated_at": now_utc_iso(),
        "framing": {
            "why_more_review": [
                "Stopping at fixed recall targets still leaves residual false negatives in medium prevalence scenarios.",
                "Additional screening reduces expected false negatives but increases screened workload and false positives.",
                "A staged +50 then reassess approach balances risk reduction and reviewer effort.",
            ],
            "source_note": "Values are planning approximations derived from active-learning traces and stopping summaries.",
        },
        "story": fn_fp_story,
    }

    sim_results_norm = sim_results.copy()
    bool_cols = ["cap_reached"]
    for c in bool_cols:
        if c in sim_results_norm.columns:
            sim_results_norm[c] = sim_results_norm[c].astype(bool)

    simulation_planner = {
        "generated_at": now_utc_iso(),
        "prevalence_bands": sorted(sim_results_norm["prevalence_band"].unique().tolist()),
        "threshold_policies": sorted(sim_results_norm["threshold_policy"].unique().tolist()),
        "rows": sim_results_norm.to_dict(orient="records"),
        "recommended_targets": target_cfg,
        "notes_markdown": sim_summary_md,
    }

    artifacts: Dict[str, Dict[str, Any]] = {
        "overview.json": overview,
        "methods_results.json": methods_results,
        "fn_fp_risk.json": fn_fp_risk,
        "simulation_planner.json": simulation_planner,
    }

    artifact_checksums: Dict[str, Dict[str, Any]] = {}
    for filename, payload in artifacts.items():
        out_path = app_artifacts_dir / filename
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        artifact_checksums[filename] = {
            "path": str(out_path.relative_to(repo_root)),
            "sha256": file_sha256(out_path),
            "size_bytes": out_path.stat().st_size,
        }

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    manifest = {
        "run_id": run_id,
        "generated_at": now_utc_iso(),
        "code_sha": git_commit_or_unknown(repo_root),
        "config": config,
        "sources": [
            {
                "name": s.name,
                "path": str(s.path.relative_to(repo_root)),
                "sha256": file_sha256(s.path),
                "modified_at": datetime.fromtimestamp(s.path.stat().st_mtime, tz=timezone.utc)
                .replace(microsecond=0)
                .isoformat(),
            }
            for s in source_files
        ],
        "artifacts": artifact_checksums,
    }

    manifest_path = app_artifacts_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "run_id": run_id,
        "artifact_dir": str(app_artifacts_dir.relative_to(repo_root)),
        "artifacts_written": sorted(list(artifacts.keys()) + ["run_manifest.json"]),
        "manifest_path": str(manifest_path.relative_to(repo_root)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh app-ready JSON artifacts from analysis outputs.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/app_refresh_config.json"),
        help="Path to refresh config JSON.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    cfg_path = args.config if args.config.is_absolute() else (repo_root / args.config)
    config = load_config(cfg_path)

    result = build_artifacts(repo_root=repo_root, config=config)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
