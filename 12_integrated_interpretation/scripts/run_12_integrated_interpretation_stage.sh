#!/usr/bin/env bash
set -euo pipefail

STAGE=\"12_integrated_interpretation\"
STATUS=\"../scripts/status.py\"
CONFIG=\"../config/status_config.json\"

python3 \"\" init --config \"\"
python3 \"\" start --stage \"12_integrated_interpretation\" --message \"start\"

if python3 scripts/collect_for_report.py --repo-root .. --out for_report; then
  python3 \"\" scan --stage \"12_integrated_interpretation\" --paths outputs
  python3 \"\" finish --stage \"12_integrated_interpretation\" --message \"success\"
else
  python3 \"\" error --stage \"12_integrated_interpretation\" --message \"stage failed\"
  exit 1
fi
