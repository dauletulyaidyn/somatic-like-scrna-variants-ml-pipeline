# AI Tech Spec: 03_gatk_call

Objective
- Call expressed variants from CB/UB-tagged BAM files using the GATK RNA-seq workflow.

Entry
- Working directory: `03_gatk_call`
- Required inputs:
  - BAM/BAI from `02_starsolo/outputs/artifacts/`
  - Reference genome FASTA

Prerequisites
- GATK 4
- samtools
- Java runtime

Actions
1) Verify BAM/BAI exist for all samples in `02_starsolo/outputs/artifacts/`.
2) Verify reference FASTA exists.
3) Ensure `config/gatk_config.json` is filled.
4) Run GATK preprocessing and HaplotypeCaller per sample.
5) Apply hard filters and export PASS-only VCF files.
6) Save outputs under `outputs/`.

Outputs
- Filtered VCF per sample.
- GATK logs per sample.

Exit criteria
- VCFs exist and are non-empty for each sample.

Next stage
- Proceed to `04_cohort_filter`.
