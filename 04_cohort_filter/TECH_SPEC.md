# AI Tech Spec: 04_cohort_filter

Objective
- Build a cohort-common VCF from per-sample filtered VCFs.

Entry
- Working directory: `04_cohort_filter`
- Required inputs:
  - VCFs from `03_gatk_call/outputs/artifacts/`

Prerequisites
- Python 3.10+
- tabix (optional, for indexing)

OS check
- Windows: require WSL2; execute all commands inside WSL.
- macOS/Linux: run natively.

Actions
1) Verify input VCFs exist and are non-empty.
2) Ensure `config/cohort_filter_config.json` is filled.
3) Parse per-sample VCFs and compute sample recurrence plus max per-sample VAF per locus.
4) Emit the cohort-common VCF under `outputs/`.

Outputs
- Cohort VCF.
- Summary tables.

Exit criteria
- Cohort VCF exists and is non-empty.

Next stage
- Proceed to `05_variant_to_gene`.
