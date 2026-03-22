#!/usr/bin/env bash
set -euo pipefail

STAGE="01_input_data"
STATUS="../scripts/status.py"
CONFIG="../config/status_config.json"

python3 "$STATUS" init --config "$CONFIG"
python3 "$STATUS" start --stage "$STAGE" --message "start"

if python3 scripts/validate_inputs.py --fastq-dir ../data/fastq --metadata ../data/metadata/metadata.tsv --out ../data/metadata/metadata.cleaned.tsv; then
  python3 "$STATUS" scan --stage "$STAGE" --paths outputs ../data/metadata/metadata.cleaned.tsv
  python3 "$STATUS" finish --stage "$STAGE" --message "success"
else
  python3 "$STATUS" error --stage "$STAGE" --message "validate_inputs failed"
  exit 1
fi
