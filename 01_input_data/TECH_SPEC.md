# AI Tech Spec: 01_input_data

Objective
- Standardize input FASTQ layout and clean sample metadata.

Entry
- Working directory: `01_input_data`
- Required inputs:
  - FASTQ directory: `data/fastq/`
  - Metadata file: `data/metadata/metadata.tsv`

Prerequisites
- Python 3.10+
- pandas

OS check
- Windows: require WSL2; execute all commands inside WSL.
- macOS/Linux: run natively.

Actions
1) Validate that FASTQ files exist in `data/fastq/`.
2) Validate metadata schema (min columns: `sample_id`, `condition`, `run_id`).
3) Cross-check metadata sample IDs against FASTQ prefixes.
4) Write cleaned metadata to `data/metadata/metadata.cleaned.tsv`.

Outputs
- `data/metadata/metadata.cleaned.tsv`

Exit criteria
- Cleaned metadata file exists and has >= 1 sample.
- All metadata sample IDs have matching FASTQ prefixes.

Next stage
- Proceed to `02_starsolo`.
- Use `metadata.cleaned.tsv` as input labels.
