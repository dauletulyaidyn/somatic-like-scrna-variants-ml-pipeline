#!/usr/bin/env bash
set -euo pipefail

STAGE=\"08_cellsnp\"
STATUS=\"../scripts/status.py\"
CONFIG=\"../config/status_config.json\"

python3 \"\" init --config \"\"
python3 \"\" start --stage \"08_cellsnp\" --message \"start\"

if python3 scripts/run_cellsnp.py --config ../config/cellsnp_config.json; then
  python3 \"\" scan --stage \"08_cellsnp\" --paths outputs
  python3 \"\" finish --stage \"08_cellsnp\" --message \"success\"
else
  python3 \"\" error --stage \"08_cellsnp\" --message \"stage failed\"
  exit 1
fi
