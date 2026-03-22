# Autonomous Agent Quickstart

Start the full pipeline with one command:

- `python scripts/run_autonomous_pipeline.py --auto-install --start-status --use-wsl` (recommended on Windows)
- `./zapusti_analiz.ps1`

Suggested agent prompt:

- `zapusti analiz`

The autonomous runner will:

- initialize the status DB
- reset stale stage states before a new run
- start the Flask status page on port `5556`
- infer and prepare a barcode whitelist when possible
- attempt best-effort dependency installation
- execute stages `01` through `12` in order
