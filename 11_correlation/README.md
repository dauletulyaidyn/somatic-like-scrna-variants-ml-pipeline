# 11_correlation: Correlation with mutational analysis

Purpose
- Correlate gene-burden and cluster-level counts with mutational analysis outputs.

Inputs
- Gene-burden matrix from `06_gene_burden/outputs/artifacts/`.
- Cluster counts from `09_cluster_aggregation/outputs/artifacts/`.
- Mutational analysis tables from `10_mutational_analysis/outputs/metrics/`.

Outputs
- Correlation tables (Spearman/Pearson) + FDR.
- Overlap/enrichment summaries.
- Stage outputs saved under `outputs/`.

How to run (manual)
1) Ensure Python + pandas/numpy/scipy are installed.
2) Set paths in `config/correlation_config.json`.
3) Run:
   - `bash scripts/run_correlation.sh`

Pre-run checks (manual)
- Verify OS and environment.
  - Windows: use WSL2 (per root TECH_SPEC) and run commands inside WSL.
  - macOS/Linux: run natively.
- Confirm all input tables exist.
- You are responsible for errors/logs when running manually.

Success criteria
- Correlation tables exist and are non-empty.

Next stage
- Proceed to `12_integrated_interpretation`.
