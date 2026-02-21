# Integration Hooks

`integration/asreview_lab_hooks.py` provides local-file hooks for:

- exporting a leakage-safe queue to ASReview LAB CSV,
- emitting queue export manifest (checksum + distribution),
- normalizing ASReview LAB label exports into JSON snapshots,
- reconciling queue-vs-label roundtrip integrity/completion.

## Commands

```bash
python3 integration/asreview_lab_hooks.py export-queue --help
python3 integration/asreview_lab_hooks.py sync-labels --help
python3 integration/asreview_lab_hooks.py reconcile-roundtrip --help
```

## One-shot roundtrip checks

```bash
scripts/run_lab_roundtrip_checks.sh
```

## Output location

Generated JSON outputs are written to `integration/outputs/` and are intentionally untracked.
A `.gitkeep` file keeps the directory in the repository.
