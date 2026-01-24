# AI Tech Spec: 03_bcftools_call

Objective
- Call expressed variants from CB/UB-tagged BAM files using bcftools.

Entry
- Working directory: `03_bcftools_call`
- Required inputs:
  - BAM/BAI from `02_starsolo/outputs/artifacts/`
  - Reference genome FASTA
  - Optional: regions BED

Prerequisites
- bcftools
- samtools
- tabix

OS check
- Windows: require WSL2; execute all commands inside WSL.
- macOS/Linux: run natively.

Actions
1) Verify BAM/BAI exist for all samples in `02_starsolo/outputs/artifacts/`.
2) Verify reference FASTA exists.
3) Ensure `config/bcftools_config.json` is filled.
4) Run bcftools pipeline per sample.
5) Save outputs under `outputs/`.

Outputs
- Filtered VCF per sample.
- bcftools logs per sample.

Exit criteria
- VCFs exist and are non-empty for each sample.

Next stage
- Proceed to `04_cohort_filter`.
