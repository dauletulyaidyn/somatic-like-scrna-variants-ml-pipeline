#!/usr/bin/env bash
set -euo pipefail

STAGE=\"02_starsolo\"
STATUS=\"../scripts/status.py\"
CONFIG=\"../config/status_config.json\"

python3 \"\" init --config \"\"
python3 \"\" start --stage \"02_starsolo\" --message \"start\"

if python3 scripts/run_starsolo.py --metadata ../data/metadata/metadata.cleaned.tsv --fastq-dir ../data/fastq --config ../config/starsolo_config.json --outdir outputs/artifacts; then
  python3 \"\" scan --stage \"02_starsolo\" --paths outputs
  python3 \"\" finish --stage \"02_starsolo\" --message \"success\"
else
  python3 \"\" error --stage \"02_starsolo\" --message \"stage failed\"
  exit 1
fi
