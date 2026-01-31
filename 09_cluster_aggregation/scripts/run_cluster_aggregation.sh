#!/usr/bin/env bash
set -euo pipefail

CONFIG="../config/cluster_aggregation_config.json"

python3 scripts/run_cluster_aggregation.py --config "$CONFIG"
