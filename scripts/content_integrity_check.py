#!/usr/bin/env python3
"""Content integrity checks for reviewer-facing artifacts.

Checks:
1) run_manifest artifact checksums match files
2) recommendation targets are coherent
3) FN/FP policy tables include baseline rows
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate reviewer artifact integrity")
    parser.add_argument("--artifacts-dir", type=Path, default=Path("app/data/artifacts"))
    args = parser.parse_args()

    artifacts_dir = args.artifacts_dir
    manifest_path = artifacts_dir / "run_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing run manifest: {manifest_path}")

    manifest = load_json(manifest_path)
    manifest_artifacts = manifest.get("artifacts", {})
    if not manifest_artifacts:
        raise AssertionError("run_manifest.json has no artifacts section")

    for name, meta in manifest_artifacts.items():
        path = artifacts_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Manifest artifact missing on disk: {path}")
        expected = meta.get("sha256")
        observed = sha256_file(path)
        if expected != observed:
            raise AssertionError(f"Checksum mismatch for {name}: expected {expected}, got {observed}")

    overview = load_json(artifacts_dir / "overview.json")
    planner = load_json(artifacts_dir / "simulation_planner.json")
    fn_fp = load_json(artifacts_dir / "fn_fp_risk.json")

    rec = overview.get("recommendation", {})
    immediate = int(rec.get("immediate_additional_docs", 0))
    contingent = int(rec.get("contingent_additional_docs", 0))
    if immediate <= 0 or contingent <= 0:
        raise AssertionError("Recommendation targets must be positive integers")
    if immediate > contingent:
        raise AssertionError("Immediate target cannot exceed contingent target")

    planner_additional = {int(r["additional_docs_requested"]) for r in planner.get("rows", [])}
    if immediate not in planner_additional:
        raise AssertionError(f"Immediate target {immediate} is not represented in planner rows")

    for policy in fn_fp.get("story", {}).get("policies", []):
        rows = policy.get("rows", [])
        if not rows:
            raise AssertionError(f"FN/FP story policy has no rows: {policy}")
        has_baseline = any(int(r.get("additional_docs_requested", -1)) == 0 for r in rows)
        if not has_baseline:
            raise AssertionError(
                f"Policy {policy.get('threshold_policy')} does not contain baseline (+0) row"
            )

    print(
        json.dumps(
            {
                "status": "ok",
                "artifacts_dir": str(artifacts_dir),
                "checked_artifacts": sorted(list(manifest_artifacts.keys()) + ["run_manifest.json"]),
                "immediate_target": immediate,
                "contingent_target": contingent,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
