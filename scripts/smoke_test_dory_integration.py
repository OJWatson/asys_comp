#!/usr/bin/env python3
"""Smoke test for ASReview Dory integration hooks.

This test is optional and expects an ASReview Dory-enabled Python executable.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    return proc


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Dory integration smoke test")
    parser.add_argument(
        "--dory-python",
        type=Path,
        default=Path(".venv-dory/bin/python"),
        help="Python interpreter with asreview + asreview-dory installed.",
    )
    parser.add_argument(
        "--asreview-bin",
        type=Path,
        default=Path(".venv-dory/bin/asreview"),
        help="ASReview executable in Dory environment.",
    )
    parser.add_argument("--n-stop", type=int, default=30)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    dory_python = args.dory_python if args.dory_python.is_absolute() else (repo_root / args.dory_python)
    asreview_bin = args.asreview_bin if args.asreview_bin.is_absolute() else (repo_root / args.asreview_bin)

    if not dory_python.exists():
        raise FileNotFoundError(
            f"Missing Dory Python executable: {dory_python}. "
            "Run scripts/setup_asreview_dory_env.sh first."
        )
    if not asreview_bin.exists():
        raise FileNotFoundError(
            f"Missing ASReview executable: {asreview_bin}. "
            "Run scripts/setup_asreview_dory_env.sh first."
        )

    smoke_dir = repo_root / "integration" / "outputs" / "dory" / "smoke"
    if smoke_dir.exists():
        shutil.rmtree(smoke_dir)
    smoke_dir.mkdir(parents=True, exist_ok=True)

    base_cmd = [str(dory_python), "integration/asreview_dory_hooks.py"]

    run(
        base_cmd
        + [
            "prepare-dataset",
            "--records",
            "data/screening_input.xlsx",
            "--dataset-output",
            str(smoke_dir / "dataset.csv"),
            "--labels-output",
            str(smoke_dir / "labels.csv"),
            "--manifest-output",
            str(smoke_dir / "prepare_manifest.json"),
            "--require-complete-labels",
        ],
        cwd=repo_root,
    )

    run(
        base_cmd
        + [
            "run-simulate",
            "--dataset",
            str(smoke_dir / "dataset.csv"),
            "--project-output",
            str(smoke_dir / "simulation.asreview"),
            "--asreview-bin",
            str(asreview_bin),
            "--classifier",
            "xgboost",
            "--feature-extractor",
            "tfidf",
            "--n-prior-included",
            "1",
            "--n-prior-excluded",
            "1",
            "--seed",
            "42",
            "--n-stop",
            str(args.n_stop),
            "--run-meta-output",
            str(smoke_dir / "simulation_meta.json"),
        ],
        cwd=repo_root,
    )

    run(
        base_cmd
        + [
            "export-results",
            "--project",
            str(smoke_dir / "simulation.asreview"),
            "--sequence-output",
            str(smoke_dir / "sequence.csv"),
            "--summary-output",
            str(smoke_dir / "summary.json"),
        ],
        cwd=repo_root,
    )

    summary = json.loads((smoke_dir / "summary.json").read_text(encoding="utf-8"))
    if summary.get("n_labels_generated", 0) <= 0:
        raise AssertionError("Expected n_labels_generated > 0")

    feature_extractors = summary.get("components", {}).get("feature_extractor", [])
    classifiers = summary.get("components", {}).get("classifier", [])
    if "tfidf" not in feature_extractors:
        raise AssertionError(f"Expected tfidf feature extractor in summary, got: {feature_extractors}")
    if "xgboost" not in classifiers:
        raise AssertionError(f"Expected xgboost classifier in summary, got: {classifiers}")

    print("Dory integration smoke test passed.")
    print(f"Smoke output dir: {smoke_dir}")


if __name__ == "__main__":
    main()
