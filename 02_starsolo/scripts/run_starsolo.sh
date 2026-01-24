#!/usr/bin/env bash
set -euo pipefail

METADATA="../data/metadata/metadata.cleaned.tsv"
FASTQ_DIR="../data/fastq"
CONFIG="../config/starsolo_config.json"
OUTDIR="outputs/artifacts"

python3 scripts/run_starsolo.py \
  --metadata "$METADATA" \
  --fastq-dir "$FASTQ_DIR" \
  --config "$CONFIG" \
  --outdir "$OUTDIR"
