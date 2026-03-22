#!/usr/bin/env bash
set -euo pipefail

CONFIG="../config/gene_burden_config.json"

python3 scripts/run_gene_burden.py --config "$CONFIG"
