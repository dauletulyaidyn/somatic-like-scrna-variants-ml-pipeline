# AI Tech Spec: 10_mutational_analysis

Objective
- Compute mutational analysis summaries from filtered VCFs.

Entry
- Working directory: `10_mutational_analysis`
- Required inputs:
  - Filtered VCFs from `03_bcftools_call/outputs/artifacts/`

Prerequisites
- Python 3.10+
- pandas
- numpy

OS check
- Windows: require WSL2; execute all commands inside WSL.
- macOS/Linux: run natively.

Actions
1) Verify filtered VCFs exist and are non-empty.
2) Ensure `config/mutational_analysis_config.json` is filled.
3) Run mutational analysis script.
4) Save outputs under `outputs/`.

Outputs
- Burden table.
- Signature counts.
- Driver counts (if driver list provided).
- Pathway enrichment table (placeholder).

Exit criteria
- Output tables exist and are non-empty.

Next stage
- Proceed to `11_correlation`.
