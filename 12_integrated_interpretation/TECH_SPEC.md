# AI Tech Spec: 12_integrated_interpretation

Objective
- Collect key tables/figures from each stage into `for_report/`.

Entry
- Working directory: `12_integrated_interpretation`
- Required inputs:
  - All stage `outputs/metrics/` and `outputs/plots/` folders (where present)

Prerequisites
- Python 3.10+

OS check
- Windows: require WSL2; execute all commands inside WSL.
- macOS/Linux: run natively.

Actions
1) Verify stage outputs exist.
2) Run collection script to copy files into `for_report/`.
3) Write summary manifest.

Outputs
- `for_report/` bundle with normalized filenames.
- `12_integrated_interpretation/outputs/metrics/for_report_manifest.tsv`

Exit criteria
- `for_report/` contains metrics/plots for stages that produced them.

Next stage
- End.
