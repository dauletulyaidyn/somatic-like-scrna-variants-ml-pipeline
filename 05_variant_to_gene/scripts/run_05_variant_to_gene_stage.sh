#!/usr/bin/env bash
set -euo pipefail

STAGE=\"05_variant_to_gene\"
STATUS=\"../scripts/status.py\"
CONFIG=\"../config/status_config.json\"

python3 \"\" init --config \"\"
python3 \"\" start --stage \"05_variant_to_gene\" --message \"start\"

if python3 scripts/run_variant_to_gene.py --config ../config/variant_to_gene_config.json; then
  python3 \"\" scan --stage \"05_variant_to_gene\" --paths outputs
  python3 \"\" finish --stage \"05_variant_to_gene\" --message \"success\"
else
  python3 \"\" error --stage \"05_variant_to_gene\" --message \"stage failed\"
  exit 1
fi
