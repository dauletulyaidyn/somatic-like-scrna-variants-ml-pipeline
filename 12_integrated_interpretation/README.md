# 12_integrated_interpretation: Integrated interpretation

Purpose
- Collect stage outputs into `for_report/` and summarize final conclusions.

Inputs
- Stage outputs (tables/plots) from each `*/outputs/` folder.

Outputs
- Curated report bundle in `for_report/`.
- Summary table with references to included files.

How to run (manual)
1) Ensure all prior stages completed.
2) Run:
   - `bash scripts/collect_for_report.sh`

Pre-run checks (manual)
- Verify OS and environment.
  - Windows: use WSL2 (per root TECH_SPEC) and run commands inside WSL.
  - macOS/Linux: run natively.
- You are responsible for errors/logs when running manually.

Success criteria
- Files copied to `for_report/` with required naming convention.

Next stage
- End.
