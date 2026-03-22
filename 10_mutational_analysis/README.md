# 10_mutational_analysis: Mutational analysis outputs

Purpose
- Derive mutational analysis summaries from filtered VCFs.

Inputs
- Filtered VCFs from `03_gatk_call/outputs/artifacts/`.

Outputs
- SNV/indel burden per sample.
- Simple mutational signatures (base change counts).
- Driver gene hit counts (optional list).
- Pathway-level mutation enrichment (placeholder table).
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
- You are responsible for errors/logs when running manually.

Success criteria
- Output tables exist and are non-empty.

Next stage
- Proceed to `11_correlation`.
