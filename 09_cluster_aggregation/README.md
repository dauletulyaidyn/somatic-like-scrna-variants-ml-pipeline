# 09_cluster_aggregation: Cluster aggregation

Purpose
- Aggregate per-cell allele counts into per-cluster variant counts.

Inputs
- cellsnp outputs from `08_cellsnp/outputs/artifacts/<sample>/`.
- Cell->cluster map TSV (e.g., `data/metadata/cell_cluster_map.tsv`).

Outputs
- Per-cluster counts TSV per sample.
- Stage outputs saved under `outputs/`.

How to run (manual)
1) Ensure Python + numpy/scipy are installed.
2) Set paths in `config/cluster_aggregation_config.json`.
3) Run:
   - `bash scripts/run_09_cluster_aggregation_stage.sh`

Pre-run checks (manual)
- Verify OS and environment.
  - Windows: use WSL2 (per root TECH_SPEC) and run commands inside WSL.
  - macOS/Linux: run natively.
- Confirm cellsnp outputs and cluster map exist.
- You are responsible for errors/logs when running manually.

Success criteria
- Per-cluster TSVs exist for each sample.

Next stage
- Proceed to `10_mutational_analysis`.
