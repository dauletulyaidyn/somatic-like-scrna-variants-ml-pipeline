# 04_cohort_filter: Cohort-common filter

Purpose
- Build a cohort-common filter VCF to keep candidate somatic-like variants.

Inputs
- Filtered VCFs from `03_bcftools_call/outputs/artifacts/`.
- Optional: min cohort frequency threshold.

Outputs
- Cohort VCF (combined/common sites).
- Summary tables (counts per sample).
- Stage outputs saved under `outputs/`.

How to run (manual)
1) Ensure bcftools + tabix are installed.
2) Set parameters in `config/cohort_filter_config.json`.
3) Run:
   - `bash scripts/run_04_cohort_filter_stage.sh`

Pre-run checks (manual)
- Verify OS and environment.
  - Windows: use WSL2 (per root TECH_SPEC) and run commands inside WSL.
  - macOS/Linux: run natively.
- Confirm input VCFs exist.
- You are responsible for errors/logs when running manually.

Success criteria
- Cohort VCF exists and is non-empty.

Next stage
- Proceed to `05_variant_to_gene`.
