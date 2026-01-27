#!/usr/bin/env bash
set -euo pipefail

STAGE=\"11_correlation\"
STATUS=\"../scripts/status.py\"
CONFIG=\"../config/status_config.json\"

python3 \"\" init --config \"\"
python3 \"\" start --stage \"11_correlation\" --message \"start\"

if python3 scripts/run_correlation.py --config ../config/correlation_config.json; then
  python3 \"\" scan --stage \"11_correlation\" --paths outputs
  python3 \"\" finish --stage \"11_correlation\" --message \"success\"
else
  python3 \"\" error --stage \"11_correlation\" --message \"stage failed\"
  exit 1
fi
