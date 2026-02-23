# Integration Hooks

`integration/asreview_lab_hooks.py` provides local-file hooks for:

- exporting a leakage-safe queue to ASReview LAB CSV,
- emitting queue export manifest (checksum + distribution),
- normalizing ASReview LAB label exports into JSON snapshots,
- reconciling queue-vs-label roundtrip integrity/completion.

`integration/asreview_dory_hooks.py` provides local-file hooks for:

- preparing Dory-compatible ASReview datasets (`record_id,title,abstract,included`),
- running Dory-backed ASReview simulation flows,
- exporting Dory simulation outputs back into repo artifacts.

## Commands

```bash
python3 integration/asreview_lab_hooks.py export-queue --help
python3 integration/asreview_lab_hooks.py sync-labels --help
python3 integration/asreview_lab_hooks.py reconcile-roundtrip --help

python3 integration/asreview_dory_hooks.py prepare-dataset --help
python3 integration/asreview_dory_hooks.py run-simulate --help
python3 integration/asreview_dory_hooks.py export-results --help
python3 integration/asreview_dory_hooks.py run-workflow --help
```

## One-shot roundtrip checks

```bash
scripts/run_lab_roundtrip_checks.sh
```

## One-shot Dory workflow

```bash
scripts/setup_asreview_dory_env.sh
scripts/run_asreview_dory_workflow.sh
scripts/run_dory_smoke_test.sh
```

## Output location

Generated integration outputs are written to `integration/outputs/` (including `integration/outputs/dory/`) and are intentionally untracked.
A `.gitkeep` file keeps the directory in the repository.
