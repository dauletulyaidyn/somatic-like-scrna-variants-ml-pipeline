#!/usr/bin/env bash
set -euo pipefail

STAGE=\"06_gene_burden\"
STATUS=\"../scripts/status.py\"
CONFIG=\"../config/status_config.json\"

python3 \"\" init --config \"\"
python3 \"\" start --stage \"06_gene_burden\" --message \"start\"

if python3 scripts/run_gene_burden.py --config ../config/gene_burden_config.json; then
  python3 \"\" scan --stage \"06_gene_burden\" --paths outputs
  python3 \"\" finish --stage \"06_gene_burden\" --message \"success\"
else
  python3 \"\" error --stage \"06_gene_burden\" --message \"stage failed\"
  exit 1
fi
