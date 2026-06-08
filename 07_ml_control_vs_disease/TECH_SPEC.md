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
4) Run the fold-safe ML script for run-level separability, or the group-aware validation script when metadata contains repeated biological/group units.
5) Save outputs under `outputs/`.

Notes
- Class balance can be n != m; warn users about strong imbalance and use stratified CV or class weights as needed.
- `positive_label` should be set to `disease`.
- The default run-level model is a scikit-learn Pipeline: `VarianceThreshold -> StandardScaler -> L2 logistic regression`.
- Variance filtering, scaling, and model fitting must be fit only inside each training fold.
- Group-aware validation is the preferred independence-aware check when multiple rows share a donor, sample, GSM, or other biological grouping variable.
- If PCA, SelectKBest, model selection, or hyperparameter tuning is added, keep those operations inside the training fold or use nested validation.

Outputs
- CV metrics and permutation test results.
- Model summary tables and plots.
- Group-aware validation outputs when `run_group_aware_validation.py` is used.

Exit criteria
- Metrics and permutation outputs exist.

Next stage
- Proceed to `08_cellsnp`.
