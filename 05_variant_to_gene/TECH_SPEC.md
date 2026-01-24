# AI Tech Spec: 05_variant_to_gene

Objective
- Build long variant->gene annotation table from cohort VCF.

Entry
- Working directory: `05_variant_to_gene`
- Required inputs:
  - Cohort VCF from `04_cohort_filter/outputs/artifacts/`
  - Gene annotation GTF

Prerequisites
- Python 3.10+
- pandas
- numpy

OS check
- Windows: require WSL2; execute all commands inside WSL.
- macOS/Linux: run natively.

Actions
1) Verify cohort VCF exists and is non-empty.
2) Verify GTF exists.
3) Ensure `config/variant_to_gene_config.json` is filled.
4) Run variant->gene script.
5) Save outputs under `outputs/`.

Outputs
- Long TSV of variant->gene annotations.

Exit criteria
- Output TSV exists and is non-empty.

Next stage
- Proceed to `06_gene_burden`.
