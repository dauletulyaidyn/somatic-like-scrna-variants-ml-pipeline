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

GATK run monitor
- Start the same Flask server with a default GATK run folder:
  `python status/app.py --port 5556 --gatk-run-root "PATH_TO_GATK_RUN_FOLDER"`
- Or launch it as a detached background server:
  `python scripts/launch_gatk_status_server.py --run-root "PATH_TO_GATK_RUN_FOLDER" --port 5556`
- Open `http://127.0.0.1:5556/gatk`
- Or pass the run folder in the URL:
  `http://127.0.0.1:5556/gatk?run_root=PATH_TO_GATK_RUN_FOLDER`

The GATK page refreshes every 10 seconds and shows:
- active process and PID file state
- current sample and current GATK step
- per-sample pending/running/finished/stopped status
- output file sizes
- raw and PASS variant counts for completed VCFs
- tail of the latest run log

This page is read-only. It does not stop, delete, or restart GATK jobs.

GATK parallel supervisor
- To keep two samples running in parallel, launch:
  `python scripts/launch_gatk_parallel_supervisor.py --run-root "PATH_TO_GATK_RUN_FOLDER" --max-parallel 2`
- The supervisor writes state to:
  `PATH_TO_GATK_RUN_FOLDER/logs/gatk_parallel_supervisor_state.json`
- The GATK status page shows this state when it exists.
- The supervisor does not retry stopped or failed samples by default, to avoid silently overwriting partial outputs.
