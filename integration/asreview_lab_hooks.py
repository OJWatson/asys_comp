#!/usr/bin/env python3
"""Integration hooks for ASReview LAB queue export and label sync.

These hooks are local-file based by design for credential-free operation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import pandas as pd

INCLUDE_TOKENS = {"1", "i", "include", "included", "relevant", "yes", "true"}
EXCLUDE_TOKENS = {"0", "e", "exclude", "excluded", "irrelevant", "no", "false"}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_decision(value: object) -> int:
    if pd.isna(value):
        raise ValueError("Missing decision value")
    s = str(value).strip().lower()
    if s in INCLUDE_TOKENS:
        return 1
    if s in EXCLUDE_TOKENS:
        return 0
    raise ValueError(f"Unrecognized decision token: {value}")


def normalize_labels_frame(df: pd.DataFrame) -> pd.DataFrame:
    candidates = {
        "record_id": ["record_id", "id", "record"],
        "decision": ["decision", "label", "included", "relevant"],
        "timestamp": ["decision_time", "timestamp", "updated_at", "created_at"],
    }

    def pick(colnames: list[str]) -> str | None:
        for c in colnames:
            if c in df.columns:
                return c
        return None

    record_col = pick(candidates["record_id"])
    decision_col = pick(candidates["decision"])
    ts_col = pick(candidates["timestamp"])

    if not record_col or not decision_col:
        raise ValueError(
            "labels CSV must include record id and decision columns. "
            f"Available columns: {list(df.columns)}"
        )

    labels = df.copy()
    labels["record_id"] = labels[record_col].astype(str)
    labels["decision"] = labels[decision_col].map(normalize_decision)

    if ts_col:
        labels["decision_time"] = pd.to_datetime(labels[ts_col], errors="coerce", utc=True)
        labels = labels.sort_values("decision_time").drop_duplicates(subset=["record_id"], keep="last")
    else:
        labels["decision_time"] = pd.NaT
        labels = labels.drop_duplicates(subset=["record_id"], keep="last")

    return labels[["record_id", "decision", "decision_time"]].copy()


def export_queue(
    ranking_path: Path,
    output_path: Path,
    top_n: int | None,
    manifest_path: Path | None = None,
) -> Dict[str, object]:
    df = pd.read_csv(ranking_path)

    required = ["queue_rank", "score_include", "title", "abstract", "record_id", "priority_bucket"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in ranking CSV: {missing}")

    out = df[required].sort_values("queue_rank")
    if top_n is not None and top_n > 0:
        out = out.head(top_n)

    if out["record_id"].duplicated().any():
        dupes = int(out["record_id"].duplicated().sum())
        raise ValueError(f"Queue export contains duplicate record_id values: {dupes}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)

    payload: Dict[str, object] = {
        "generated_at": now_utc_iso(),
        "input": str(ranking_path),
        "output": str(output_path),
        "rows": int(len(out)),
        "top_n": top_n,
        "priority_bucket_counts": out["priority_bucket"].value_counts().to_dict(),
        "score_range": {
            "min": float(out["score_include"].min()) if len(out) else None,
            "max": float(out["score_include"].max()) if len(out) else None,
        },
        "queue_sha256": sha256_file(output_path),
    }

    if manifest_path is not None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        payload["manifest_output"] = str(manifest_path)

    return payload


def sync_labels(labels_path: Path, output_path: Path) -> Dict[str, object]:
    raw_df = pd.read_csv(labels_path)
    out = normalize_labels_frame(raw_df)

    payload = {
        "generated_at": now_utc_iso(),
        "input": str(labels_path),
        "n_labels": int(len(out)),
        "n_include": int((out["decision"] == 1).sum()),
        "n_exclude": int((out["decision"] == 0).sum()),
        "labels": [
            {
                "record_id": str(r["record_id"]),
                "decision": int(r["decision"]),
                "decision_time": None
                if pd.isna(r["decision_time"])
                else pd.Timestamp(r["decision_time"]).to_pydatetime().replace(microsecond=0).isoformat(),
            }
            for _, r in out.iterrows()
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def reconcile_roundtrip(queue_path: Path, labels_path: Path, output_path: Path) -> Dict[str, object]:
    queue_df = pd.read_csv(queue_path)
    if "record_id" not in queue_df.columns:
        raise ValueError(f"Queue CSV must include record_id column: {queue_path}")

    labels_raw = pd.read_csv(labels_path)
    labels_df = normalize_labels_frame(labels_raw)

    queue_ids = queue_df["record_id"].astype(str)
    label_ids = labels_df["record_id"].astype(str)

    queue_set = set(queue_ids.tolist())
    label_set = set(label_ids.tolist())

    labeled_in_queue = sorted(queue_set & label_set)
    labels_not_in_queue = sorted(label_set - queue_set)
    queue_unlabeled = sorted(queue_set - label_set)

    payload = {
        "generated_at": now_utc_iso(),
        "queue": str(queue_path),
        "labels": str(labels_path),
        "queue_rows": int(len(queue_df)),
        "queue_duplicate_record_ids": int(queue_ids.duplicated().sum()),
        "labels_raw_rows": int(len(labels_raw)),
        "labels_unique_rows": int(len(labels_df)),
        "labels_in_queue": int(len(labeled_in_queue)),
        "labels_not_in_queue": int(len(labels_not_in_queue)),
        "queue_unlabeled": int(len(queue_unlabeled)),
        "queue_completion_fraction": round(len(labeled_in_queue) / len(queue_set), 6) if queue_set else 0.0,
        "decision_counts": {
            "include": int((labels_df["decision"] == 1).sum()),
            "exclude": int((labels_df["decision"] == 0).sum()),
        },
        "labels_not_in_queue_record_ids": labels_not_in_queue,
        "queue_unlabeled_record_ids_sample": queue_unlabeled[:50],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="ASReview LAB integration hooks")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_export = sub.add_parser("export-queue", help="Export leakage-safe queue for ASReview LAB import")
    p_export.add_argument(
        "--ranking",
        type=Path,
        default=Path("analysis/outputs/next_steps/production_ranking_leakage_safe.csv"),
    )
    p_export.add_argument(
        "--output",
        type=Path,
        default=Path("infra/asreview-lab/data/queue_for_lab.csv"),
    )
    p_export.add_argument("--top-n", type=int, default=None)
    p_export.add_argument(
        "--manifest-output",
        type=Path,
        default=Path("integration/outputs/lab_queue_export_manifest.json"),
    )

    p_sync = sub.add_parser("sync-labels", help="Normalize exported LAB labels to local JSON snapshot")
    p_sync.add_argument(
        "--labels",
        type=Path,
        default=Path("infra/asreview-lab/data/lab_labels_export.csv"),
    )
    p_sync.add_argument(
        "--output",
        type=Path,
        default=Path("integration/outputs/lab_labels_snapshot.json"),
    )

    p_reconcile = sub.add_parser(
        "reconcile-roundtrip",
        help="Compare exported queue vs labels export and report completion/data-integrity stats",
    )
    p_reconcile.add_argument(
        "--queue",
        type=Path,
        default=Path("infra/asreview-lab/data/queue_for_lab.csv"),
    )
    p_reconcile.add_argument(
        "--labels",
        type=Path,
        default=Path("infra/asreview-lab/data/lab_labels_export.csv"),
    )
    p_reconcile.add_argument(
        "--output",
        type=Path,
        default=Path("integration/outputs/lab_roundtrip_report.json"),
    )

    args = parser.parse_args()

    if args.cmd == "export-queue":
        result = export_queue(args.ranking, args.output, args.top_n, args.manifest_output)
    elif args.cmd == "sync-labels":
        result = sync_labels(args.labels, args.output)
    else:
        result = reconcile_roundtrip(args.queue, args.labels, args.output)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
