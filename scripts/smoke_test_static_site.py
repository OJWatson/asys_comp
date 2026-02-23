#!/usr/bin/env python3
"""Smoke test for built GitHub Pages static site output."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


REQUIRED_HTML = {
    "index.html": "ASYS Compendium",
    "projects-e5cr7.html": "Project Deep Dive · e5cr7",
    "asreview-explainer.html": "ASReview Reviewer Portal · e5cr7 (Moved)",
    "methods-results.html": "Methods & Results · e5cr7 (Moved)",
    "why-more-review.html": "Why More Review Is Needed · e5cr7 (Moved)",
    "how-many-more.html": "How Many More To Screen · e5cr7 (Moved)",
    "lab.html": "Shared ASReview LAB Access",
    "lab-e5cr7.html": "LAB Endpoint · e5cr7 (Moved)",
}

REQUIRED_JSON = [
    "overview.json",
    "methods_results.json",
    "fn_fp_risk.json",
    "simulation_planner.json",
    "run_manifest.json",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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
    parser = argparse.ArgumentParser(description="Smoke test built static site")
    parser.add_argument("--site-dir", type=Path, default=Path("site"))
    parser.add_argument("--port", type=int, default=8775)
    args = parser.parse_args()

    site_dir = args.site_dir.resolve()
    if not site_dir.exists():
        raise FileNotFoundError(f"Missing site directory: {site_dir}")

    for page in REQUIRED_HTML:
        if not (site_dir / page).exists():
            raise FileNotFoundError(f"Missing static page: {site_dir / page}")

    artifacts_dir = site_dir / "data" / "artifacts"
    for name in REQUIRED_JSON:
        if not (artifacts_dir / name).exists():
            raise FileNotFoundError(f"Missing static artifact JSON: {artifacts_dir / name}")

    catalog_path = site_dir / "data" / "compendium_catalog.json"
    if not catalog_path.exists():
        raise FileNotFoundError(f"Missing static compendium catalog: {catalog_path}")

    manifest = json.loads((artifacts_dir / "run_manifest.json").read_text(encoding="utf-8"))
    for name, meta in manifest.get("artifacts", {}).items():
        path = artifacts_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Manifest artifact missing in static bundle: {path}")
        expected = meta.get("sha256")
        observed = sha256_file(path)
        if expected != observed:
            raise AssertionError(f"Static bundle checksum mismatch for {name}: {expected} != {observed}")

    server_cmd = [sys.executable, "-m", "http.server", str(args.port)]
    proc = subprocess.Popen(server_cmd, cwd=site_dir)

    try:
        wait_http(f"http://127.0.0.1:{args.port}/index.html")

        for page, marker in REQUIRED_HTML.items():
            content = fetch_text(f"http://127.0.0.1:{args.port}/{page}")
            if marker not in content:
                raise AssertionError(f"Expected marker '{marker}' not found in /{page}")

        for name in REQUIRED_JSON:
            payload = fetch_json(f"http://127.0.0.1:{args.port}/data/artifacts/{name}")
            if not isinstance(payload, dict):
                raise AssertionError(f"Expected JSON object from /data/artifacts/{name}")

        catalog = fetch_json(f"http://127.0.0.1:{args.port}/data/compendium_catalog.json")
        if "projects" not in catalog:
            raise AssertionError("Compendium catalog missing 'projects' key")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=4)
        except subprocess.TimeoutExpired:
            proc.kill()

    print("Static smoke test passed: compendium bundle is reachable and complete.")


if __name__ == "__main__":
    main()
