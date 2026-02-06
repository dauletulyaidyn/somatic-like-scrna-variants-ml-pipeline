# 10_mutational_analysis: Mutational analysis outputs

Purpose
- Derive mutational analysis summaries from filtered VCFs.

Inputs
- Filtered VCFs from `03_bcftools_call/outputs/artifacts/`.
- Gene-burden matrix from `06_gene_burden/outputs/artifacts/gene_burden_matrix.tsv`.
- One or more pathway gene set `.gmt` files (see `config/ref/gene_sets/`).

Outputs
- SNV/indel burden per sample.
- Simple mutational signatures (base change counts).
- Driver gene hit counts (optional list).
- Pathway enrichment (ORA; hypergeometric test + BH FDR) for genes with burden > 0 per sample (and `cohort_union`).
- Stage outputs saved under `outputs/`.

How to run (manual)
1) Ensure Python + pandas/numpy are installed.
2) Set paths in `config/mutational_analysis_config.json`.
3) Run:
   - `bash scripts/run_10_mutational_analysis_stage.sh`

Pre-run checks (manual)
- Verify OS and environment.
  - Windows: use WSL2 (per root TECH_SPEC) and run commands inside WSL.
  - macOS/Linux: run natively.
- Confirm input VCFs exist.
- Confirm `gene_sets_gmt` in `config/mutational_analysis_config.json` points to a valid `.gmt` file.
- You are responsible for errors/logs when running manually.

Success criteria
- Output tables exist and are non-empty.

Next stage
- Proceed to `11_correlation`.
