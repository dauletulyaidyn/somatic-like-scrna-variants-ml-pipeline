#!/usr/bin/env bash
set -euo pipefail

CONFIG="../config/cellsnp_config.json"

python3 scripts/run_cellsnp.py --config "$CONFIG"
