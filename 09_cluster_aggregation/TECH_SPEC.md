# AI Tech Spec: 09_cluster_aggregation

Objective
- Aggregate cellsnp-lite AD/DP matrices into per-cluster counts.

Entry
- Working directory: `09_cluster_aggregation`
- Required inputs:
  - cellsnp outputs from `08_cellsnp/outputs/artifacts/`
  - cell->cluster map TSV

Prerequisites
- Python 3.10+
- numpy
- scipy

OS check
- Windows: require WSL2; execute all commands inside WSL.
- macOS/Linux: run natively.

Actions
1) Verify cellsnp outputs exist for each sample.
2) Verify cell->cluster map exists.
3) Ensure `config/cluster_aggregation_config.json` is filled.
4) Run cluster aggregation script.
5) Save outputs under `outputs/`.

Outputs
- Per-cluster TSVs per sample.

Exit criteria
- Cluster count TSVs exist and are non-empty.

Next stage
- Proceed to `10_mutational_analysis`.
