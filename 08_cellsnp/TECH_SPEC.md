# AI Tech Spec: 08_cellsnp

Objective
- Run cellsnp-lite to generate per-cell allele counts.

Entry
- Working directory: `08_cellsnp`
- Required inputs:
  - BAM/BAI from `02_starsolo/outputs/artifacts/`
  - Cohort VCF from `04_cohort_filter/outputs/artifacts/`
  - Barcode whitelist

Prerequisites
- cellsnp-lite
- samtools
- tabix

OS check
- Windows: require WSL2; execute all commands inside WSL.
- macOS/Linux: run natively.

Actions
1) Verify BAM/BAI and cohort VCF exist.
2) Ensure `config/cellsnp_config.json` is filled.
3) Run cellsnp-lite per sample.
4) Save outputs under `outputs/`.

Outputs
- AD/DP matrices + variants.tsv per sample.

Exit criteria
- cellsnp outputs exist and are non-empty for each sample.

Next stage
- Proceed to `09_cluster_aggregation`.
