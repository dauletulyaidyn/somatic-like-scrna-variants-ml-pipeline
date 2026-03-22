#!/usr/bin/env bash
set -euo pipefail

STAGE="10_mutational_analysis"
STATUS="../scripts/status.py"
CONFIG="../config/status_config.json"

python3 "$STATUS" init --config "$CONFIG"
python3 "$STATUS" start --stage "$STAGE" --message "start"

if python3 scripts/run_mutational_analysis.py --config ../config/mutational_analysis_config.json; then
  python3 "$STATUS" scan --stage "$STAGE" --paths outputs
  python3 "$STATUS" finish --stage "$STAGE" --message "success"
else
  python3 "$STATUS" error --stage "$STAGE" --message "stage failed"
  exit 1
fi
