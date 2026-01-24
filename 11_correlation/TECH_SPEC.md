# AI Tech Spec: 11_correlation

Objective
- Compute correlations/enrichment between gene-burden, cluster counts, and mutational outputs.

Entry
- Working directory: `11_correlation`
- Required inputs:
  - Gene-burden matrix from `06_gene_burden/outputs/artifacts/`
  - Cluster counts from `09_cluster_aggregation/outputs/artifacts/`
  - Mutational analysis outputs from `10_mutational_analysis/outputs/metrics/`

Prerequisites
- Python 3.10+
- pandas
- numpy
- scipy

OS check
- Windows: require WSL2; execute all commands inside WSL.
- macOS/Linux: run natively.

Actions
1) Verify all inputs exist.
2) Ensure `config/correlation_config.json` is filled.
3) Run correlation script.
4) Save outputs under `outputs/`.

Outputs
- Correlation tables + FDR.
- Overlap/enrichment summaries.

Exit criteria
- Output tables exist and are non-empty.

Next stage
- Proceed to `12_integrated_interpretation`.
