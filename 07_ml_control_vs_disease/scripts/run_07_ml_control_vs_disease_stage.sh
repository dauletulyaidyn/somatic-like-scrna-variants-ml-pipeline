#!/usr/bin/env bash
set -euo pipefail

STAGE=\"07_ml_control_vs_disease\"
STATUS=\"../scripts/status.py\"
CONFIG=\"../config/status_config.json\"

python3 \"\" init --config \"\"
python3 \"\" start --stage \"07_ml_control_vs_disease\" --message \"start\"

if python3 scripts/run_ml.py --config ../config/ml_config.json; then
  python3 \"\" scan --stage \"07_ml_control_vs_disease\" --paths outputs
  python3 \"\" finish --stage \"07_ml_control_vs_disease\" --message \"success\"
else
  python3 \"\" error --stage \"07_ml_control_vs_disease\" --message \"stage failed\"
  exit 1
fi
