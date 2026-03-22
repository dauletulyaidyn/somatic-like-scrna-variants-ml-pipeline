#!/usr/bin/env bash
set -euo pipefail

BAM_DIR="../02_starsolo/outputs/artifacts"
CONFIG="../config/bcftools_config.json"
OUTDIR="outputs/artifacts"

python3 scripts/run_bcftools.py \
  --bam-dir "$BAM_DIR" \
  --config "$CONFIG" \
  --outdir "$OUTDIR"
