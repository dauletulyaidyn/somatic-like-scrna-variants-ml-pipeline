# 07_ml_control_vs_disease: ML classification

Purpose
- Train and evaluate ML models to classify control (baseline, untreated) vs disease (condition, treated) using gene-burden features or an explicitly declared combined feature matrix.

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
- This is the preferred validation mode for non-independent run-level observations.
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
- The default stage script `run_ml.py` reports run-level repeated stratified CV only as a separability comparator.
- The default stage script uses a leakage-safe scikit-learn Pipeline: `VarianceThreshold -> StandardScaler -> L2 logistic regression`, fit separately inside each CV training fold.
- Group-aware leave-one-group-out validation keeps all rows from the held-out group out of training.
- Grouped permutation permutes labels at group level and preserves the number of positive groups.
- Group-aware validation uses the same leakage-safe Pipeline, with variance filtering and scaling fit inside each run-level or group-held-out fold.
- If PCA, SelectKBest, model selection, or hyperparameter search is added in future analyses, those steps must be placed inside the fold-level Pipeline or nested inside the training fold.

Combined classifier benchmark across three validation designs
- `scripts/run_combined_three_design_benchmark.py` compares the same classifier set using **only the combined early-concatenation input** (expression + mutation-derived features).
- It reports three distinct designs: SRR-level repeated CV, GSM-LOGO with globally formed recurrent loci, and GSM-LOGO with recurrent loci/gene burden rebuilt using only the training SRRs in each fold.
- In the training-only design, the expression block remains part of the combined input, while the mutation-derived block is reconstructed per fold before concatenation. Model preprocessing is also fit inside each fold.
- Separate plots are written for every design, plus one three-panel comparison. LOGO bars are aggregate metrics over seven held-out GSM predictions and therefore are not shown with a fabricated fold SD.

Example:

```bash
python scripts/run_combined_three_design_benchmark.py \
  --combined-matrix /path/to/combined_gatk_variant_plus_expression_matrix.tsv \
  --metadata /path/to/metadata.cleaned.tsv \
  --vcf-dir /path/to/input_pass_vcfs \
  --variant-gene-tsv /path/to/variant_gene.tsv \
  --outdir results/combined_three_design_benchmark
```

The recurrent-locus defaults reproduce the declared PAD branch (`min_samples=4`, `min_vaf=0.05`). The combined matrix is an internal early-fusion comparator, not evidence of independent clinical generalization.

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
