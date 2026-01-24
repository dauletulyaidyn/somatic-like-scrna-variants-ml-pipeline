# 05_variant_to_gene: Variant -> gene tables

Purpose
- Annotate cohort VCF variants with gene context and build long variant-gene tables.

Inputs
- Cohort VCF from `04_cohort_filter/outputs/artifacts/`.
- Gene annotation GTF (e.g., `config/ref/genes.gtf`).

Outputs
- Long TSV of variant->gene annotations.
- Stage outputs saved under `outputs/`.

How to run (manual)
1) Ensure Python + pandas are installed.
2) Set paths in `config/variant_to_gene_config.json`.
3) Run:
   - `bash scripts/run_variant_to_gene.sh`

Pre-run checks (manual)
- Verify OS and environment.
  - Windows: use WSL2 (per root TECH_SPEC) and run commands inside WSL.
  - macOS/Linux: run natively.
- Confirm cohort VCF and GTF exist.
- You are responsible for errors/logs when running manually.

Success criteria
- Long TSV exists and is non-empty.

Next stage
- Proceed to `06_gene_burden`.
