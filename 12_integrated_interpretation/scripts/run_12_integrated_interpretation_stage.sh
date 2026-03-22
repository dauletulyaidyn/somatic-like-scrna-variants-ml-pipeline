#!/usr/bin/env bash
set -euo pipefail

STAGE="12_integrated_interpretation"
STATUS="../scripts/status.py"
CONFIG="../config/status_config.json"

python3 "$STATUS" init --config "$CONFIG"
python3 "$STATUS" start --stage "$STAGE" --message "start"

if python3 scripts/collect_for_report.py --repo-root .. --out for_report; then
  python3 "$STATUS" scan --stage "$STAGE" --paths outputs --paths for_report
  python3 "$STATUS" finish --stage "$STAGE" --message "success"
else
  python3 "$STATUS" error --stage "$STAGE" --message "stage failed"
  exit 1
fi
