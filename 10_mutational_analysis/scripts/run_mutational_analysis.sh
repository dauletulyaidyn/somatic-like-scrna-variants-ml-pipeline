#!/usr/bin/env bash
set -euo pipefail

CONFIG="../config/mutational_analysis_config.json"

python3 scripts/run_mutational_analysis.py --config "$CONFIG"
