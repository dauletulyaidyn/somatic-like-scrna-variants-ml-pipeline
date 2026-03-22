#!/usr/bin/env bash
set -euo pipefail

CONFIG="../config/variant_to_gene_config.json"

python3 scripts/run_variant_to_gene.py --config "$CONFIG"
