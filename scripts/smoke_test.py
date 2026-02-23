#!/usr/bin/env python3
"""Basic smoke tests for the reviewer-facing MVP app and data artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def assert_json(path: Path, required_keys: list[str]) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    for k in required_keys:
        if k not in payload:
            raise AssertionError(f"Missing key '{k}' in {path}")


def wait_http(url: str, timeout_s: float = 10.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                if resp.status == 200:
                    return
        except Exception:
            time.sleep(0.2)
    raise TimeoutError(f"Server did not become ready at {url}")


def fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=3) as resp:
        if resp.status != 200:
            raise AssertionError(f"Non-200 status for {url}: {resp.status}")
        return resp.read().decode("utf-8", errors="replace")


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=3) as resp:
        if resp.status != 200:
            raise AssertionError(f"Non-200 status for {url}: {resp.status}")
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local smoke tests.")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    artifacts_dir = repo_root / "app" / "data" / "artifacts"

    required_files = {
        "overview.json": ["generated_at", "project", "model_snapshot", "risk_baselines", "recommendation"],
        "methods_results.json": ["generated_at", "methods", "model_leaderboard", "baseline_vs_improved"],
        "fn_fp_risk.json": ["generated_at", "framing", "story"],
        "simulation_planner.json": ["generated_at", "rows", "recommended_targets"],
        "run_manifest.json": ["run_id", "generated_at", "sources", "artifacts"],
    }

    for filename, keys in required_files.items():
        path = artifacts_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing artifact: {path}")
        assert_json(path, keys)

    catalog_path = repo_root / "app" / "data" / "compendium_catalog.json"
    if not catalog_path.exists():
        raise FileNotFoundError(f"Missing catalog: {catalog_path}")
    assert_json(catalog_path, ["generated_at", "shared_lab", "projects"])

    server_cmd = [sys.executable, str(repo_root / "app" / "server.py"), "--host", "127.0.0.1", "--port", str(args.port)]
    proc = subprocess.Popen(server_cmd, cwd=repo_root)

    try:
        wait_http(f"http://127.0.0.1:{args.port}/")

        checks = {
            "/": "ASYS Compendium",
            "/projects/e5cr7": "Project Deep Dive · e5cr7",
            "/asreview-explainer": "Project Deep Dive · e5cr7",
            "/methods-results": "Project Deep Dive · e5cr7",
            "/why-more-review": "Project Deep Dive · e5cr7",
            "/how-many-more": "Project Deep Dive · e5cr7",
            "/lab": "Shared ASReview LAB Access",
            "/lab/e5cr7": "Project Deep Dive · e5cr7",
            "/asreview-explainer.html": "ASReview Reviewer Portal · e5cr7 (Moved)",
            "/methods-results.html": "Methods & Results · e5cr7 (Moved)",
            "/why-more-review.html": "Why More Review Is Needed · e5cr7 (Moved)",
            "/how-many-more.html": "How Many More To Screen · e5cr7 (Moved)",
            "/lab-e5cr7.html": "LAB Endpoint · e5cr7 (Moved)",
        }
        for path, marker in checks.items():
            content = fetch_text(f"http://127.0.0.1:{args.port}{path}")
            if marker not in content:
                raise AssertionError(f"Expected marker '{marker}' not found in {path}")

        api_checks = [
            "/data/artifacts/overview.json",
            "/data/artifacts/methods_results.json",
            "/data/artifacts/fn_fp_risk.json",
            "/data/artifacts/simulation_planner.json",
            "/data/compendium_catalog.json",
        ]
        for path in api_checks:
            payload = fetch_json(f"http://127.0.0.1:{args.port}{path}")
            if not isinstance(payload, dict):
                raise AssertionError(f"Expected JSON object from {path}")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=4)
        except subprocess.TimeoutExpired:
            proc.kill()

    print("Smoke test passed: compendium routes, legacy redirects/stubs, and data endpoints are reachable.")


if __name__ == "__main__":
    main()
