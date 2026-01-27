#!/usr/bin/env bash
set -euo pipefail

STAGE=\"03_bcftools_call\"
STATUS=\"../scripts/status.py\"
CONFIG=\"../config/status_config.json\"

python3 \"\" init --config \"\"
python3 \"\" start --stage \"03_bcftools_call\" --message \"start\"

if python3 scripts/run_bcftools.py --bam-dir ../02_starsolo/outputs/artifacts --config ../config/bcftools_config.json --outdir outputs/artifacts; then
  python3 \"\" scan --stage \"03_bcftools_call\" --paths outputs
  python3 \"\" finish --stage \"03_bcftools_call\" --message \"success\"
else
  python3 \"\" error --stage \"03_bcftools_call\" --message \"stage failed\"
  exit 1
fi
