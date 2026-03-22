#!/usr/bin/env bash
set -euo pipefail

VCF_DIR="../03_gatk_call/outputs/artifacts"
CONFIG="../config/cohort_filter_config.json"
OUTDIR="outputs/artifacts"

python3 scripts/run_cohort_filter.py \
  --vcf-dir "$VCF_DIR" \
  --config "$CONFIG" \
  --outdir "$OUTDIR"
