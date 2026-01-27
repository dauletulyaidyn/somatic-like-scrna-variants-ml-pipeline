# 08_cellsnp: cellsnp-lite per-cell allele counts

Purpose
- Compute per-cell allelic counts (AD/DP) at candidate sites.

Inputs
- CB/UB BAM + BAI from `02_starsolo/outputs/artifacts/`.
- Candidate VCF from `04_cohort_filter/outputs/artifacts/cohort.common.vcf.gz`.
- Barcode whitelist (platform-specific) in `config/ref/whitelist.txt`.

Outputs
- cellsnp-lite outputs: AD/DP matrices + variants TSV.
- Stage outputs saved under `outputs/`.

How to run (manual)
1) Ensure cellsnp-lite, samtools, tabix are installed.
2) Set paths in `config/cellsnp_config.json`.
3) Run:
   - `bash scripts/run_08_cellsnp_stage.sh`

Pre-run checks (manual)
- Verify OS and environment.
  - Windows: use WSL2 (per root TECH_SPEC) and run commands inside WSL.
  - macOS/Linux: run natively.
- Confirm BAM/BAI and cohort VCF exist.
- You are responsible for errors/logs when running manually.

Success criteria
- cellsnp output matrices exist for each sample.

Next stage
- Proceed to `09_cluster_aggregation`.
