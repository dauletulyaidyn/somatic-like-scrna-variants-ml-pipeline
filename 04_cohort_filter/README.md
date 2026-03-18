# 04_cohort_filter: Cohort-Common Filter

Purpose
- Build a cohort-common VCF to keep candidate somatic-like loci based on multi-sample recurrence and per-sample VAF support.

Inputs
- Filtered VCFs from `03_gatk_call/outputs/artifacts/`.
- Optional: minimum cohort recurrence and VAF thresholds.

Outputs
- Cohort VCF (combined/common sites).
- Summary tables.
- Stage outputs saved under `outputs/`.

How to run (manual)
1) Ensure Python 3.10+ is installed. `tabix` is optional for indexing.
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
