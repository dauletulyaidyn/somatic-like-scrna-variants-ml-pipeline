# 06_gene_burden: Somatic-like gene-burden features

Purpose
- Build gene-level burden features from variant->gene table.

Inputs
- `05_variant_to_gene/outputs/artifacts/variant_gene_long.tsv`.
- Per-sample VCFs from `03_bcftools_call/outputs/artifacts/`.

Outputs
- Gene-burden matrix (TSV/CSV), genes x samples.
- Stage outputs saved under `outputs/`.

How to run (manual)
1) Ensure Python + pandas/numpy are installed.
2) Set paths in `config/gene_burden_config.json`.
3) Run:
   - `bash scripts/run_06_gene_burden_stage.sh`

Pre-run checks (manual)
- Verify OS and environment.
  - Windows: use WSL2 (per root TECH_SPEC) and run commands inside WSL.
  - macOS/Linux: run natively.
- Confirm variant->gene table exists.
- You are responsible for errors/logs when running manually.

Success criteria
- Gene-burden matrix exists and is non-empty.

Next stage
- Proceed to `07_ml_control_vs_disease`.
