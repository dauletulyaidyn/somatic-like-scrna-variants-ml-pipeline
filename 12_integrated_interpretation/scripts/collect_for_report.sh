#!/usr/bin/env bash
set -euo pipefail

python3 scripts/collect_for_report.py --repo-root .. --out for_report
