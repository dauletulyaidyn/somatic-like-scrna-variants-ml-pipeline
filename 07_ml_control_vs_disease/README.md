# 07_ml_control_vs_disease: ML classification

Purpose
- Train and evaluate ML models to classify control (baseline, untreated) vs disease (condition, treated) using gene-burden features.

Inputs
- Gene-burden matrix (genes x samples) from `06_gene_burden/outputs/artifacts/`.
- `data/metadata/metadata.cleaned.tsv` with labels.

Outputs
- CV metrics and permutation test results.
- Group-aware validation tables for non-independent run-level observations.
- Model summary tables and plots.
- Stage outputs saved under `outputs/`.

How to run (manual)
1) Ensure Python + numpy/pandas/scikit-learn are installed.
2) Set paths in `config/ml_config.json`.
3) Run:
   - `bash scripts/run_07_ml_control_vs_disease_stage.sh`

How to run group-aware validation (manual)
- Use this when multiple run-level observations can come from the same biological sample, donor proxy, or GEO/GSM group.
- Required metadata columns:
  - `sample_id`
  - label column, default `condition`
  - group column, default `gsm`
  - optional display column, default `sample_title`

Example:

```bash
python scripts/run_group_aware_validation.py \
  --feature-matrix ../06_gene_burden/outputs/artifacts/gene_burden_matrix.tsv \
  --metadata ../data/metadata/metadata.cleaned.tsv \
  --label-col condition \
  --positive-label wound \
  --group-col gsm \
  --group-title-col sample_title \
  --outdir outputs/group_validation
```

For a completed external GATK analysis bundle, point `--feature-matrix`, `--metadata`, and `--outdir` to that bundle. The script writes:
- `table_validation_for_report.tsv` and `.csv`
- `run_level_cv_summary.tsv`
- `group_validation_summary.tsv`
- `group_wise_predictions.tsv`
- `grouped_permutation_summary.tsv`
- `group_confusion_matrices.tsv`
- `group_validation_summary.md`

Validation design
- Run-level repeated stratified CV is retained only as a separability comparator.
- Group-aware leave-one-group-out validation keeps all rows from the held-out group out of training.
- Grouped permutation permutes labels at group level and preserves the number of positive groups.
- Preprocessing is leakage-safe: variance filtering and scaling are fit inside each CV fold.

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
