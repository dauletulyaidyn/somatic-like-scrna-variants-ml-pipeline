# 11_correlation: Correlation with mutational analysis

Purpose
- Build an integrated sample-level view across gene burden, mutational burden, mutational signatures, optional cluster-level burden, optional STARsolo-derived sample metrics, and metadata.

Inputs
- Gene-burden matrix from `06_gene_burden/outputs/artifacts/`.
- Cluster counts from `09_cluster_aggregation/outputs/artifacts/`.
- Mutational analysis tables from `10_mutational_analysis/outputs/metrics/`.
- Optional STARsolo sample metrics from `02_starsolo/outputs/artifacts/`.
- Optional metadata from `data/metadata/metadata.cleaned.tsv`.

Outputs
- Integrated sample table.
- Pairwise Spearman correlation tables + FDR.
- Condition-level summaries.
- Integration notes and plots.
- Stage outputs saved under `outputs/`.

How to run (manual)
1) Ensure Python + pandas/numpy/scipy are installed.
2) Set paths in `config/correlation_config.json`.
3) Run:
   - `bash scripts/run_11_correlation_stage.sh`

Pre-run checks (manual)
- Verify OS and environment.
  - Windows: use WSL2 (per root TECH_SPEC) and run commands inside WSL.
  - macOS/Linux: run natively.
- Confirm all input tables exist.
- You are responsible for errors/logs when running manually.

Success criteria
- Integrated sample table and correlation outputs exist and are non-empty.

Next stage
- Proceed to `12_integrated_interpretation`.
