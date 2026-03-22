#!/usr/bin/env bash
set -euo pipefail

python3 scripts/run_gatk.py \
  --bam-dir ../02_starsolo/outputs/artifacts \
  --config ../config/gatk_config.json \
  --outdir outputs/artifacts
