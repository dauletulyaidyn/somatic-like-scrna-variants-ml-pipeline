# AI Tech Spec: 10_mutational_analysis

Objective
- Compute mutational analysis summaries from filtered VCFs.

Entry
- Working directory: `10_mutational_analysis`
- Required inputs:
  - Filtered VCFs from `03_gatk_call/outputs/artifacts/`
  - Gene-burden matrix from `06_gene_burden/outputs/artifacts/gene_burden_matrix.tsv`
  - One or more pathway gene set `.gmt` files (see `config/ref/gene_sets/`)

Prerequisites
- Python 3.10+
- pandas
- numpy
- scipy (recommended; otherwise a slower exact fallback is used)

OS check
- Windows: require WSL2; execute all commands inside WSL.
- macOS/Linux: run natively.

Actions
1) Verify filtered VCFs exist and are non-empty.
2) Ensure `config/mutational_analysis_config.json` is filled.
3) Run mutational analysis script.
4) Save outputs under `outputs/`.

Outputs
- Burden table.
- Signature counts.
- Driver counts (if driver list provided).
- Pathway enrichment table (ORA; hypergeometric + BH FDR).

Exit criteria
- Output tables exist and are non-empty.

Next stage
- Proceed to `11_correlation`.
