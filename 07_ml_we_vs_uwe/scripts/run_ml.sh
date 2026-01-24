#!/usr/bin/env bash
set -euo pipefail

CONFIG="../config/ml_config.json"

python3 scripts/run_ml.py --config "$CONFIG"
