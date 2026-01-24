#!/usr/bin/env bash
set -euo pipefail

CONFIG="../config/correlation_config.json"

python3 scripts/run_correlation.py --config "$CONFIG"
