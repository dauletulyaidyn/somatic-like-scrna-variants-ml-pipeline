# 03_gatk_call: GATK RNA Variant Calling

Purpose
- Call expressed variants from CB/UB-tagged BAM files with the GATK RNA workflow.

Inputs
- CB/UB BAM + BAI from `02_starsolo/outputs/artifacts/`.
- Reference genome FASTA (e.g., `config/ref/genome.fa`).
- `config/gatk_config.json`.

Outputs
- PASS-only filtered VCF per sample.
- Stage metrics, imported logs, and run manifests.
- Stage outputs saved under `outputs/`.

How to run (manual)
1) Ensure GATK, samtools, and tabix are installed.
2) Set paths in `config/gatk_config.json`.
3) Run:
   - `bash scripts/run_03_gatk_call_stage.sh`

Pre-run checks (manual)
- Verify OS and environment.
  - Windows: use WSL2 (per root TECH_SPEC) and run commands inside WSL.
  - macOS/Linux: run natively.
- Confirm reference FASTA and BAM/BAI inputs exist.
- If `mode=import_existing`, confirm the external GATK workspace paths resolve.
- You are responsible for errors/logs when running manually.

Success criteria
- Filtered VCFs exist and are non-empty for each sample.

Next stage
- Proceed to `04_cohort_filter`.
