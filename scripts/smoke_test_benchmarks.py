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
        bench_dir / "MODEL_BENCHMARK_REPORT.md",
    ]

    for path in required:
        if not path.exists():
            raise FileNotFoundError(f"Missing benchmark artifact: {path}")

    fold_df = pd.read_csv(bench_dir / "model_benchmark_fold_metrics.csv")
    summary_df = pd.read_csv(bench_dir / "model_benchmark_summary.csv")
    summary_json = json.loads((bench_dir / "model_benchmark_summary.json").read_text(encoding="utf-8"))

    if fold_df.empty or summary_df.empty:
        raise AssertionError("Benchmark CSV outputs should not be empty")

    for col in ["average_precision", "roc_auc", "wss@95", "precision@20", "recall@20"]:
        if col not in fold_df.columns:
            raise AssertionError(f"Missing fold metric column: {col}")

    if not any(summary_df["cohort"] == "baseline"):
        raise AssertionError("Benchmark summary missing baseline cohort")

    if not any(summary_df["cohort"] == "improved"):
        raise AssertionError("Benchmark summary missing improved cohort")

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
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
