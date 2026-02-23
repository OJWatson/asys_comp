#!/usr/bin/env python3
"""ASReview Dory integration hooks for ASYS Compendium.

This module provides a practical bridge for:
1) Preparing Dory-compatible datasets from existing ASYS files.
2) Running ASReview simulation with Dory-backed components.
3) Exporting simulation outputs into repository artifacts.

The workflow is intentionally file-based and credential-free.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sqlite3
import subprocess
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Sequence

import pandas as pd

INCLUDE_TOKENS = {"1", "i", "include", "included", "relevant", "yes", "true", "y"}
EXCLUDE_TOKENS = {"0", "e", "exclude", "excluded", "irrelevant", "no", "false", "n"}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_col_name(name: object) -> str:
    s = str(name).strip().lower()
    s = s.replace("_", " ").replace("-", " ")
    s = " ".join(s.split())
    return s


def find_column(columns: Sequence[str], candidates: Sequence[str], *, required: bool = True) -> Optional[str]:
    norm_to_orig: Dict[str, str] = {}
    for col in columns:
        norm_to_orig.setdefault(normalize_col_name(col), col)

    norm_candidates = [normalize_col_name(c) for c in candidates]

    for cand in norm_candidates:
        if cand in norm_to_orig:
            return norm_to_orig[cand]

    for cand in norm_candidates:
        cand_alt = cand[:-1] if cand.endswith("s") else f"{cand}s"
        if cand_alt in norm_to_orig:
            return norm_to_orig[cand_alt]

    scored = []
    for norm, orig in norm_to_orig.items():
        for cand in norm_candidates:
            if cand in norm or norm in cand:
                scored.append((abs(len(norm) - len(cand)), len(norm), orig))
                break
    if scored:
        scored.sort()
        return scored[0][2]

    if required:
        raise ValueError(
            f"Could not find required column. Candidates={list(candidates)}; available={list(columns)}"
        )
    return None


def normalize_decision(value: object) -> float:
    if pd.isna(value):
        return float("nan")

    if isinstance(value, (int, bool)):
        iv = int(value)
        return float(iv) if iv in (0, 1) else float("nan")

    if isinstance(value, float):
        if math.isnan(value):
            return float("nan")
        if value in (0.0, 1.0):
            return float(int(value))

    s = str(value).strip().lower()
    if s in INCLUDE_TOKENS:
        return 1.0
    if s in EXCLUDE_TOKENS:
        return 0.0

    compact = "".join(ch for ch in s if ch.isalnum())
    if compact in INCLUDE_TOKENS:
        return 1.0
    if compact in EXCLUDE_TOKENS:
        return 0.0

    return float("nan")


def read_tabular(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if suffix in {".csv", ".tsv", ".tab"}:
        sep = "\t" if suffix in {".tsv", ".tab"} else ","
        return pd.read_csv(path, sep=sep)
    raise ValueError(f"Unsupported tabular format for {path}. Use CSV/TSV/XLSX.")


def prepare_dataset(
    records_path: Path,
    dataset_output: Path,
    *,
    labels_path: Path | None,
    labels_output: Path | None,
    manifest_output: Path | None,
    require_complete_labels: bool,
) -> Dict[str, object]:
    records_df = read_tabular(records_path)

    record_col = find_column(records_df.columns, ["record_id", "rec_number", "id", "record", "foreign_keys"])
    title_col = find_column(records_df.columns, ["title", "titles", "primary_title"])
    abstract_col = find_column(records_df.columns, ["abstract", "abstracts", "notes_abstract", "abstract note"])
    decision_col_records = find_column(
        records_df.columns,
        ["included", "label", "asreview_label", "final_decision", "final decision", "decision", "include"],
        required=False,
    )

    prepared = pd.DataFrame(
        {
            "record_id": records_df[record_col].astype(str),
            "title": records_df[title_col].fillna("").astype(str),
            "abstract": records_df[abstract_col].fillna("").astype(str),
        }
    )

    if prepared["record_id"].duplicated().any():
        n_dupes = int(prepared["record_id"].duplicated().sum())
        raise ValueError(f"Input records contain duplicate record_id values: {n_dupes}")

    prepared["included"] = float("nan")

    label_source = "none"
    labels_unique = 0

    if labels_path is not None:
        labels_df = read_tabular(labels_path)
        labels_record_col = find_column(labels_df.columns, ["record_id", "id", "record", "rec_number"])
        labels_decision_col = find_column(
            labels_df.columns,
            ["decision", "label", "included", "include", "relevant", "final_decision", "final decision"],
        )

        labels_norm = pd.DataFrame(
            {
                "record_id": labels_df[labels_record_col].astype(str),
                "included": labels_df[labels_decision_col].map(normalize_decision),
            }
        )

        labels_norm = labels_norm.dropna(subset=["included"]).drop_duplicates(subset=["record_id"], keep="last")
        labels_unique = int(len(labels_norm))
        prepared = prepared.merge(labels_norm, on="record_id", how="left", suffixes=("", "_from_labels"))
        prepared["included"] = prepared["included_from_labels"]
        prepared.drop(columns=["included_from_labels"], inplace=True)
        label_source = "external_labels"
    elif decision_col_records is not None:
        prepared["included"] = records_df[decision_col_records].map(normalize_decision)
        label_source = f"records:{decision_col_records}"

    if require_complete_labels and prepared["included"].isna().any():
        missing = int(prepared["included"].isna().sum())
        raise ValueError(
            f"Prepared dataset has {missing} records without labels, but --require-complete-labels was set."
        )

    prepared["included"] = prepared["included"].map(lambda x: "" if pd.isna(x) else int(x))

    dataset_output.parent.mkdir(parents=True, exist_ok=True)
    prepared.to_csv(dataset_output, index=False)

    if labels_output is not None:
        labels_out_df = prepared.loc[prepared["included"] != "", ["record_id", "included"]].copy()
        labels_output.parent.mkdir(parents=True, exist_ok=True)
        labels_out_df.to_csv(labels_output, index=False)

    n_labeled = int((prepared["included"] != "").sum())
    n_included = int((prepared["included"] == 1).sum())
    n_excluded = int((prepared["included"] == 0).sum())

    payload: Dict[str, object] = {
        "generated_at": now_utc_iso(),
        "records_input": str(records_path),
        "labels_input": str(labels_path) if labels_path is not None else None,
        "dataset_output": str(dataset_output),
        "rows": int(len(prepared)),
        "label_source": label_source,
        "labels_unique_rows_used": labels_unique,
        "labeled_rows": n_labeled,
        "included_rows": n_included,
        "excluded_rows": n_excluded,
        "unlabeled_rows": int(len(prepared) - n_labeled),
        "columns_detected": {
            "record_id": record_col,
            "title": title_col,
            "abstract": abstract_col,
            "decision_records": decision_col_records,
        },
    }

    if manifest_output is not None:
        manifest_output.parent.mkdir(parents=True, exist_ok=True)
        manifest_output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        payload["manifest_output"] = str(manifest_output)

    return payload


def _run_command(cmd: list[str]) -> tuple[int, str, str, float]:
    started = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - started
    return proc.returncode, proc.stdout, proc.stderr, elapsed


def run_simulation(
    dataset_path: Path,
    project_output: Path,
    *,
    asreview_bin: str,
    classifier: str,
    feature_extractor: str,
    querier: str,
    balancer: str,
    n_prior_included: int,
    n_prior_excluded: int,
    seed: int,
    n_stop: int,
    verbose: int,
    run_meta_output: Path | None,
) -> Dict[str, object]:
    if not dataset_path.exists():
        raise FileNotFoundError(f"Missing dataset for simulation: {dataset_path}")

    project_output.parent.mkdir(parents=True, exist_ok=True)

    tmp_candidate = Path(str(project_output) + ".tmp")
    for path in (project_output, tmp_candidate):
        if path.exists():
            if path.is_file():
                path.unlink()
            else:
                shutil.rmtree(path)

    cmd = [
        asreview_bin,
        "simulate",
        str(dataset_path),
        "--classifier",
        classifier,
        "--feature-extractor",
        feature_extractor,
        "--querier",
        querier,
        "--balancer",
        balancer,
        "--n-prior-included",
        str(n_prior_included),
        "--n-prior-excluded",
        str(n_prior_excluded),
        "--seed",
        str(seed),
        "--n-stop",
        str(n_stop),
        "--output",
        str(project_output),
        "--verbose",
        str(verbose),
    ]

    rc, stdout, stderr, elapsed = _run_command(cmd)
    if rc != 0:
        raise RuntimeError(
            "ASReview simulation failed.\n"
            f"Command: {' '.join(cmd)}\n"
            f"Exit code: {rc}\n"
            f"STDOUT:\n{stdout}\n"
            f"STDERR:\n{stderr}"
        )

    payload: Dict[str, object] = {
        "generated_at": now_utc_iso(),
        "dataset": str(dataset_path),
        "project_output": str(project_output),
        "command": cmd,
        "elapsed_seconds": round(elapsed, 3),
        "stdout": stdout,
        "stderr": stderr,
        "parameters": {
            "classifier": classifier,
            "feature_extractor": feature_extractor,
            "querier": querier,
            "balancer": balancer,
            "n_prior_included": n_prior_included,
            "n_prior_excluded": n_prior_excluded,
            "seed": seed,
            "n_stop": n_stop,
            "verbose": verbose,
        },
    }

    if run_meta_output is not None:
        run_meta_output.parent.mkdir(parents=True, exist_ok=True)
        run_meta_output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        payload["run_meta_output"] = str(run_meta_output)

    return payload


def _read_sql_table(conn: sqlite3.Connection, table_name: str) -> pd.DataFrame:
    return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)


def export_simulation_outputs(
    project_path: Path,
    *,
    sequence_output: Path,
    summary_output: Path,
) -> Dict[str, object]:
    if not project_path.exists():
        raise FileNotFoundError(f"Missing project file: {project_path}")

    sequence_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="asreview_dory_extract_") as tmpdir:
        tmp_root = Path(tmpdir)
        with zipfile.ZipFile(project_path) as zf:
            zf.extractall(tmp_root)

        data_store_path = tmp_root / "data_store.db"
        if not data_store_path.exists():
            raise FileNotFoundError(f"Invalid ASReview project (missing data_store.db): {project_path}")

        reviews_dir = tmp_root / "reviews"
        review_dirs = sorted(p for p in reviews_dir.glob("*") if p.is_dir())
        if not review_dirs:
            raise FileNotFoundError(f"Invalid ASReview project (missing review db): {project_path}")

        review_dir = review_dirs[0]
        results_db_path = review_dir / "results.db"

        with sqlite3.connect(data_store_path) as conn_data:
            records_df = _read_sql_table(conn_data, "record")

        with sqlite3.connect(results_db_path) as conn_results:
            results_df = _read_sql_table(conn_results, "results")

    results_df = results_df.sort_values(by=["time", "record_id"], kind="mergesort").reset_index(drop=True)

    merged = results_df.merge(
        records_df[["record_id", "title", "abstract", "included"]],
        on="record_id",
        how="left",
        suffixes=("", "_gold"),
    )

    merged = merged.rename(columns={"included": "gold_label", "label": "decision"})
    merged["step"] = range(1, len(merged) + 1)
    merged["decision"] = merged["decision"].astype(int)
    merged["gold_label"] = merged["gold_label"].astype("Int64")

    total_relevant = int((records_df["included"] == 1).sum())
    merged["cumulative_relevant_found"] = (merged["decision"] == 1).cumsum()
    merged["recall_at_step"] = (
        merged["cumulative_relevant_found"] / total_relevant if total_relevant > 0 else 0.0
    )

    ordered_cols = [
        "step",
        "time",
        "record_id",
        "decision",
        "gold_label",
        "classifier",
        "feature_extractor",
        "querier",
        "balancer",
        "training_set",
        "cumulative_relevant_found",
        "recall_at_step",
        "title",
        "abstract",
    ]
    sequence_df = merged[ordered_cols].copy()
    sequence_df.to_csv(sequence_output, index=False)

    if len(sequence_df) > 0:
        last_recall = float(sequence_df.iloc[-1]["recall_at_step"])
        found_relevant = int(sequence_df.iloc[-1]["cumulative_relevant_found"])
    else:
        last_recall = 0.0
        found_relevant = 0

    first_relevant_step = None
    rel_hits = sequence_df.loc[sequence_df["decision"] == 1, "step"]
    if len(rel_hits) > 0:
        first_relevant_step = int(rel_hits.iloc[0])

    summary = {
        "generated_at": now_utc_iso(),
        "project": str(project_path),
        "review_id": review_dir.name,
        "sequence_output": str(sequence_output),
        "n_records_total": int(len(records_df)),
        "n_labels_generated": int(len(sequence_df)),
        "total_relevant_gold": total_relevant,
        "relevant_found": found_relevant,
        "recall_final": round(last_recall, 6),
        "first_relevant_step": first_relevant_step,
        "components": {
            "classifier": sorted(sequence_df["classifier"].dropna().astype(str).unique().tolist()),
            "feature_extractor": sorted(sequence_df["feature_extractor"].dropna().astype(str).unique().tolist()),
            "querier": sorted(sequence_df["querier"].dropna().astype(str).unique().tolist()),
            "balancer": sorted(sequence_df["balancer"].dropna().astype(str).unique().tolist()),
        },
    }

    summary_output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary["summary_output"] = str(summary_output)
    return summary


def run_workflow(args: argparse.Namespace) -> Dict[str, object]:
    prep = prepare_dataset(
        records_path=args.records,
        dataset_output=args.dataset_output,
        labels_path=args.labels,
        labels_output=args.labels_output,
        manifest_output=args.prepare_manifest_output,
        require_complete_labels=args.require_complete_labels,
    )

    sim = run_simulation(
        dataset_path=args.dataset_output,
        project_output=args.project_output,
        asreview_bin=args.asreview_bin,
        classifier=args.classifier,
        feature_extractor=args.feature_extractor,
        querier=args.querier,
        balancer=args.balancer,
        n_prior_included=args.n_prior_included,
        n_prior_excluded=args.n_prior_excluded,
        seed=args.seed,
        n_stop=args.n_stop,
        verbose=args.verbose,
        run_meta_output=args.simulation_meta_output,
    )

    exported = export_simulation_outputs(
        project_path=args.project_output,
        sequence_output=args.sequence_output,
        summary_output=args.summary_output,
    )

    return {
        "generated_at": now_utc_iso(),
        "prepare": prep,
        "simulate": {
            "project_output": sim["project_output"],
            "elapsed_seconds": sim["elapsed_seconds"],
            "run_meta_output": sim.get("run_meta_output"),
        },
        "export": exported,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="ASReview Dory integration hooks")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_prepare = sub.add_parser("prepare-dataset", help="Prepare Dory-compatible dataset CSV")
    p_prepare.add_argument("--records", type=Path, default=Path("data/screening_input.xlsx"))
    p_prepare.add_argument("--labels", type=Path, default=None)
    p_prepare.add_argument(
        "--dataset-output",
        type=Path,
        default=Path("integration/outputs/dory/dory_simulation_dataset.csv"),
    )
    p_prepare.add_argument(
        "--labels-output",
        type=Path,
        default=Path("integration/outputs/dory/dory_labels_export.csv"),
    )
    p_prepare.add_argument(
        "--manifest-output",
        type=Path,
        default=Path("integration/outputs/dory/dory_prepare_manifest.json"),
    )
    p_prepare.add_argument("--require-complete-labels", action="store_true")

    p_sim = sub.add_parser("run-simulate", help="Run ASReview simulate with Dory components")
    p_sim.add_argument(
        "--dataset",
        type=Path,
        default=Path("integration/outputs/dory/dory_simulation_dataset.csv"),
    )
    p_sim.add_argument(
        "--project-output",
        type=Path,
        default=Path("integration/outputs/dory/dory_simulation.asreview"),
    )
    p_sim.add_argument("--asreview-bin", type=str, default="asreview")
    p_sim.add_argument("--classifier", type=str, default="xgboost")
    p_sim.add_argument("--feature-extractor", type=str, default="tfidf")
    p_sim.add_argument("--querier", type=str, default="max")
    p_sim.add_argument("--balancer", type=str, default="balanced")
    p_sim.add_argument("--n-prior-included", type=int, default=1)
    p_sim.add_argument("--n-prior-excluded", type=int, default=1)
    p_sim.add_argument("--seed", type=int, default=42)
    p_sim.add_argument("--n-stop", type=int, default=60)
    p_sim.add_argument("--verbose", type=int, default=1)
    p_sim.add_argument(
        "--run-meta-output",
        type=Path,
        default=Path("integration/outputs/dory/dory_simulation_run_meta.json"),
    )

    p_export = sub.add_parser("export-results", help="Export ASReview project outputs to CSV/JSON artifacts")
    p_export.add_argument(
        "--project",
        type=Path,
        default=Path("integration/outputs/dory/dory_simulation.asreview"),
    )
    p_export.add_argument(
        "--sequence-output",
        type=Path,
        default=Path("integration/outputs/dory/dory_simulation_sequence.csv"),
    )
    p_export.add_argument(
        "--summary-output",
        type=Path,
        default=Path("integration/outputs/dory/dory_simulation_summary.json"),
    )

    p_workflow = sub.add_parser("run-workflow", help="Run prepare -> simulate -> export in one command")
    p_workflow.add_argument("--records", type=Path, default=Path("data/screening_input.xlsx"))
    p_workflow.add_argument("--labels", type=Path, default=None)
    p_workflow.add_argument(
        "--dataset-output",
        type=Path,
        default=Path("integration/outputs/dory/dory_simulation_dataset.csv"),
    )
    p_workflow.add_argument(
        "--labels-output",
        type=Path,
        default=Path("integration/outputs/dory/dory_labels_export.csv"),
    )
    p_workflow.add_argument(
        "--prepare-manifest-output",
        type=Path,
        default=Path("integration/outputs/dory/dory_prepare_manifest.json"),
    )
    p_workflow.add_argument(
        "--project-output",
        type=Path,
        default=Path("integration/outputs/dory/dory_simulation.asreview"),
    )
    p_workflow.add_argument(
        "--sequence-output",
        type=Path,
        default=Path("integration/outputs/dory/dory_simulation_sequence.csv"),
    )
    p_workflow.add_argument(
        "--summary-output",
        type=Path,
        default=Path("integration/outputs/dory/dory_simulation_summary.json"),
    )
    p_workflow.add_argument(
        "--simulation-meta-output",
        type=Path,
        default=Path("integration/outputs/dory/dory_simulation_run_meta.json"),
    )
    p_workflow.add_argument("--asreview-bin", type=str, default="asreview")
    p_workflow.add_argument("--classifier", type=str, default="xgboost")
    p_workflow.add_argument("--feature-extractor", type=str, default="tfidf")
    p_workflow.add_argument("--querier", type=str, default="max")
    p_workflow.add_argument("--balancer", type=str, default="balanced")
    p_workflow.add_argument("--n-prior-included", type=int, default=1)
    p_workflow.add_argument("--n-prior-excluded", type=int, default=1)
    p_workflow.add_argument("--seed", type=int, default=42)
    p_workflow.add_argument("--n-stop", type=int, default=60)
    p_workflow.add_argument("--verbose", type=int, default=1)
    p_workflow.add_argument("--require-complete-labels", action="store_true")

    args = parser.parse_args()

    if args.cmd == "prepare-dataset":
        payload = prepare_dataset(
            records_path=args.records,
            dataset_output=args.dataset_output,
            labels_path=args.labels,
            labels_output=args.labels_output,
            manifest_output=args.manifest_output,
            require_complete_labels=args.require_complete_labels,
        )
    elif args.cmd == "run-simulate":
        payload = run_simulation(
            dataset_path=args.dataset,
            project_output=args.project_output,
            asreview_bin=args.asreview_bin,
            classifier=args.classifier,
            feature_extractor=args.feature_extractor,
            querier=args.querier,
            balancer=args.balancer,
            n_prior_included=args.n_prior_included,
            n_prior_excluded=args.n_prior_excluded,
            seed=args.seed,
            n_stop=args.n_stop,
            verbose=args.verbose,
            run_meta_output=args.run_meta_output,
        )
    elif args.cmd == "export-results":
        payload = export_simulation_outputs(
            project_path=args.project,
            sequence_output=args.sequence_output,
            summary_output=args.summary_output,
        )
    else:
        payload = run_workflow(args)

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
