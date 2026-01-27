# AI Tech Spec: 07_ml_control_vs_disease

Objective
- Train ML models to classify control (baseline, untreated) vs disease (condition, treated) using gene-burden features.

Entry
- Working directory: `07_ml_control_vs_disease`
- Required inputs:
  - Gene-burden matrix from `06_gene_burden/outputs/artifacts/`
  - `data/metadata/metadata.cleaned.tsv`

Prerequisites
- Python 3.10+
- pandas
- numpy
- scikit-learn

OS check
- Windows: require WSL2; execute all commands inside WSL.
- macOS/Linux: run natively.

Actions
1) Verify gene-burden matrix exists and is non-empty.
2) Verify metadata exists and contains `sample_id` + `condition`.
3) Ensure `config/ml_config.json` is filled.
4) Run ML script.
5) Save outputs under `outputs/`.

Notes
- Class balance can be n != m; warn users about strong imbalance and use stratified CV or class weights as needed.
- `positive_label` should be set to `disease`.

Outputs
- CV metrics and permutation test results.
- Model summary tables and plots.

Exit criteria
- Metrics and permutation outputs exist.

Next stage
- Proceed to `08_cellsnp`.
