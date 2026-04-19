# Status Web UI

Run the status server on port `5556` for the legacy `01_...12_` pipeline.

Manual server start
- `python status/app.py --port 5556`

Recommended background start
- `python scripts/launch_pipeline_background.py --use-wsl --watchdog-interval 10`

The UI shows:
- stage statuses from `config/status_config.json`
- runner state
- watchdog state and sequence warnings
- events (`start` / `finish` / `error` / `scan`)
- file list with sizes and previews
