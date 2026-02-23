#!/usr/bin/env python3
"""Smoke checks for NLP benchmark artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate benchmark output artifacts")
    parser.add_argument("--bench-dir", type=Path, default=Path("analysis/outputs/benchmarks"))
    args = parser.parse_args()

    bench_dir = args.bench_dir
    required = [
        bench_dir / "model_benchmark_fold_metrics.csv",
        bench_dir / "model_benchmark_summary.csv",
        bench_dir / "model_benchmark_summary.json",
        bench_dir / "environment_model_availability.json",
        bench_dir / "model_combo_attempt_matrix.csv",
        bench_dir / "model_combo_attempt_matrix.json",
        bench_dir / "MODEL_BENCHMARK_REPORT.md",
    ]

    for path in required:
        if not path.exists():
            raise FileNotFoundError(f"Missing benchmark artifact: {path}")

    fold_df = pd.read_csv(bench_dir / "model_benchmark_fold_metrics.csv")
    summary_df = pd.read_csv(bench_dir / "model_benchmark_summary.csv")
    summary_json = json.loads((bench_dir / "model_benchmark_summary.json").read_text(encoding="utf-8"))
    env_json = json.loads((bench_dir / "environment_model_availability.json").read_text(encoding="utf-8"))
    combo_df = pd.read_csv(bench_dir / "model_combo_attempt_matrix.csv")

    if fold_df.empty or summary_df.empty:
        raise AssertionError("Benchmark CSV outputs should not be empty")

    if combo_df.empty:
        raise AssertionError("Combo attempt matrix should not be empty")

    for col in ["average_precision", "roc_auc", "wss@95", "precision@20", "recall@20"]:
        if col not in fold_df.columns:
            raise AssertionError(f"Missing fold metric column: {col}")

    if not any(summary_df["cohort"] == "baseline"):
        raise AssertionError("Benchmark summary missing baseline cohort")

    if not any(summary_df["cohort"] == "improved"):
        raise AssertionError("Benchmark summary missing improved cohort")

    expected_lightweight_models = {
        "candidate_calibrated_sgd_word_char",
        "candidate_lr_elasticnet_word_char",
        "candidate_linear_svc_isotonic_word_char",
    }
    missing_expected = sorted(expected_lightweight_models - set(summary_df["model_id"].astype(str)))
    if missing_expected:
        raise AssertionError(f"Benchmark summary missing expected advanced models: {missing_expected}")

    succeeded = combo_df[combo_df["status"] == "succeeded"]
    if succeeded.empty:
        raise AssertionError("Combo matrix has no succeeded models")

    combo_counts = summary_json.get("combo_matrix_counts", {})
    if not combo_counts:
        raise AssertionError("Benchmark summary JSON missing combo_matrix_counts")

    attempted_expected = int((combo_df["status"].isin(["succeeded", "failed"])).sum())
    if int(combo_counts.get("attempted", -1)) != attempted_expected:
        raise AssertionError(
            "combo_matrix_counts.attempted mismatch with combo matrix status rows"
        )

    if "nemo" not in (env_json.get("environment") or {}):
        raise AssertionError("Environment availability JSON missing nemo diagnostics")

    dory_status = (((env_json.get("environment") or {}).get("dory") or {}).get("status"))
    if dory_status == "available":
        has_dory = any(summary_df["cohort"] == "dory")
        if not has_dory:
            raise AssertionError("ASReview Dory is available but no Dory cohort model was benchmarked")

    winner = summary_json.get("summary_rows", [{}])[0]
    if "model_id" not in winner:
        raise AssertionError("Benchmark summary JSON has no winner model")

    print(
        json.dumps(
            {
                "status": "ok",
                "bench_dir": str(bench_dir),
                "n_fold_rows": int(len(fold_df)),
                "n_models": int(summary_df["model_id"].nunique()),
                "winner": winner.get("model_id"),
                "combo_matrix_counts": combo_counts,
                "dory_models_benchmarked": summary_json.get("dory_models_benchmarked", []),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
