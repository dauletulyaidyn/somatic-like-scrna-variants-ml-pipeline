#!/usr/bin/env bash
set -euo pipefail

STAGE=\"09_cluster_aggregation\"
STATUS=\"../scripts/status.py\"
CONFIG=\"../config/status_config.json\"

python3 \"\" init --config \"\"
python3 \"\" start --stage \"09_cluster_aggregation\" --message \"start\"

if python3 scripts/run_cluster_aggregation.py --config ../config/cluster_aggregation_config.json; then
  python3 \"\" scan --stage \"09_cluster_aggregation\" --paths outputs
  python3 \"\" finish --stage \"09_cluster_aggregation\" --message \"success\"
else
  python3 \"\" error --stage \"09_cluster_aggregation\" --message \"stage failed\"
  exit 1
fi
