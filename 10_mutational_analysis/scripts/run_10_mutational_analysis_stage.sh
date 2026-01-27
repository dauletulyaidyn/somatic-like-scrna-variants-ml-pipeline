#!/usr/bin/env bash
set -euo pipefail

STAGE=\"10_mutational_analysis\"
STATUS=\"../scripts/status.py\"
CONFIG=\"../config/status_config.json\"

python3 \"\" init --config \"\"
python3 \"\" start --stage \"10_mutational_analysis\" --message \"start\"

if python3 scripts/run_mutational_analysis.py --config ../config/mutational_analysis_config.json; then
  python3 \"\" scan --stage \"10_mutational_analysis\" --paths outputs
  python3 \"\" finish --stage \"10_mutational_analysis\" --message \"success\"
else
  python3 \"\" error --stage \"10_mutational_analysis\" --message \"stage failed\"
  exit 1
fi
