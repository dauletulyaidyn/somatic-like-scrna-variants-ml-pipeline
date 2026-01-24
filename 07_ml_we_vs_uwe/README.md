# 07_ml_we_vs_uwe: ML classification

Purpose
- Train and evaluate ML models to classify WE vs UWE using gene-burden features.

Inputs
- Gene-burden matrix (genes x samples) from `06_gene_burden/outputs/artifacts/`.
- `data/metadata/metadata.cleaned.tsv` with labels.

Outputs
- CV metrics and permutation test results.
- Model summary tables and plots.
- Stage outputs saved under `outputs/`.

How to run (manual)
1) Ensure Python + numpy/pandas/scikit-learn are installed.
2) Set paths in `config/ml_config.json`.
3) Run:
   - `bash scripts/run_ml.sh`

Pre-run checks (manual)
- Verify OS and environment.
  - Windows: use WSL2 (per root TECH_SPEC) and run commands inside WSL.
  - macOS/Linux: run natively.
- Confirm feature matrix and metadata exist.
- You are responsible for errors/logs when running manually.

Success criteria
- Metrics table exists and is non-empty.
- Permutation test results exist.

Next stage
- Proceed to `08_cellsnp`.
