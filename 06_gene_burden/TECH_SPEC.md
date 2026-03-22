# AI Tech Spec: 06_gene_burden

Objective
- Build gene-level burden matrix from variant->gene table.

Entry
- Working directory: `06_gene_burden`
- Required inputs:
  - Variant->gene long TSV from `05_variant_to_gene/outputs/artifacts/`
  - Per-sample VCFs from `03_gatk_call/outputs/artifacts/`

Prerequisites
- Python 3.10+
- pandas
- numpy

OS check
- Windows: require WSL2; execute all commands inside WSL.
- macOS/Linux: run natively.

Actions
1) Verify variant->gene TSV exists and is non-empty.
2) Ensure `config/gene_burden_config.json` is filled.
3) Run gene-burden script.
4) Save outputs under `outputs/`.

Outputs
- Gene-burden matrix (TSV/CSV).

Exit criteria
- Output matrix exists and is non-empty.

Next stage
- Proceed to `07_ml_control_vs_disease`.
