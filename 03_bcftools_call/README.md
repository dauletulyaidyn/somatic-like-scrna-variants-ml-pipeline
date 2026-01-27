# 03_bcftools_call: bcftools mpileup/call

Purpose
- Call expressed variants from CB/UB-tagged BAM files.

Inputs
- CB/UB BAM + BAI from `02_starsolo/outputs/artifacts/`.
- Reference genome FASTA (e.g., `config/ref/genome.fa`).
- Optional: target regions BED (if limiting to expressed genes).

Outputs
- Filtered VCF per sample.
- bcftools logs per sample.
- Stage outputs saved under `outputs/`.

How to run (manual)
1) Ensure bcftools, samtools, and tabix are installed.
2) Set paths in `config/bcftools_config.json`.
3) Run:
   - `bash scripts/run_03_bcftools_call_stage.sh`

Pre-run checks (manual)
- Verify OS and environment.
  - Windows: use WSL2 (per root TECH_SPEC) and run commands inside WSL.
  - macOS/Linux: run natively.
- Confirm reference FASTA and BAM/BAI inputs exist.
- You are responsible for errors/logs when running manually.

Success criteria
- Filtered VCFs exist and are non-empty for each sample.

Next stage
- Proceed to `04_cohort_filter`.
