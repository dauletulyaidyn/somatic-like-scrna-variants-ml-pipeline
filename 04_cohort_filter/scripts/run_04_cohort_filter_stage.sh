#!/usr/bin/env bash
set -euo pipefail

STAGE=\"04_cohort_filter\"
STATUS=\"../scripts/status.py\"
CONFIG=\"../config/status_config.json\"

python3 \"\" init --config \"\"
python3 \"\" start --stage \"04_cohort_filter\" --message \"start\"

if python3 scripts/run_cohort_filter.py --vcf-dir ../03_bcftools_call/outputs/artifacts --config ../config/cohort_filter_config.json --outdir outputs/artifacts; then
  python3 \"\" scan --stage \"04_cohort_filter\" --paths outputs
  python3 \"\" finish --stage \"04_cohort_filter\" --message \"success\"
else
  python3 \"\" error --stage \"04_cohort_filter\" --message \"stage failed\"
  exit 1
fi
