# AI Tech Spec: 03_gatk_call

Objective
- Call expressed variants from CB/UB-tagged BAM files with GATK HaplotypeCaller.

Entry
- Working directory: `03_gatk_call`
- Required inputs:
  - BAM/BAI from `02_starsolo/outputs/artifacts/`
  - Reference genome FASTA
  - `config/gatk_config.json`

Prerequisites
- GATK 4
- samtools
- tabix

OS check
- Windows: require WSL2; execute all commands inside WSL.
- macOS/Linux: run natively.

Actions
1) Verify BAM/BAI exist for all samples in `02_starsolo/outputs/artifacts/`.
2) Verify reference FASTA exists.
3) Ensure `config/gatk_config.json` is filled.
4) If `mode=import_existing`, import the canonical GATK outputs from the external workspace.
5) If `mode=run_fresh`, execute:
   - `AddOrReplaceReadGroups`
   - `MarkDuplicates`
   - `SplitNCigarReads`
   - `HaplotypeCaller`
   - `VariantFiltration`
   - PASS-only export to the active stage output directory
6) Save outputs under `outputs/`.

Outputs
- Filtered VCF per sample.
- Import or execution logs per sample.

Exit criteria
- VCFs exist and are non-empty for each sample.

Next stage
- Proceed to `04_cohort_filter`.
