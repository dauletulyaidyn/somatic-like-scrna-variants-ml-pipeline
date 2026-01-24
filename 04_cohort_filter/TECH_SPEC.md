# AI Tech Spec: 04_cohort_filter

Objective
- Build cohort-common VCF from per-sample filtered VCFs.

Entry
- Working directory: `04_cohort_filter`
- Required inputs:
  - VCFs from `03_bcftools_call/outputs/artifacts/`

Prerequisites
- bcftools
- tabix

OS check
- Windows: require WSL2; execute all commands inside WSL.
- macOS/Linux: run natively.

Actions
1) Verify input VCFs exist and are non-empty.
2) Ensure `config/cohort_filter_config.json` is filled.
3) Run cohort-common filter script.
4) Save outputs under `outputs/`.

Outputs
- Cohort VCF.
- Summary tables.

Exit criteria
- Cohort VCF exists and is non-empty.

Next stage
- Proceed to `05_variant_to_gene`.
