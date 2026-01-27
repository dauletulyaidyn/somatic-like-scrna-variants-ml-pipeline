# 01_input_data: Input data

Purpose
- Prepare raw scRNA-seq FASTQ and metadata for downstream steps.

Inputs
- Raw FASTQ files (R1/R2/R3 as applicable by platform).
- Sample metadata (TSV/CSV).

Outputs
- Standardized input directory with FASTQ files.
- Cleaned metadata table with sample IDs.

How to run (manual)
1) Place FASTQ files under `data/fastq/` with consistent naming.
2) Create `data/metadata/metadata.tsv` with at least: `sample_id`, `condition` (control [baseline, untreated] / disease [condition, treated]), `run_id`.
3) Run the check script:
   - `bash scripts/run_01_input_data_stage.sh`

Pre-run checks (manual)
- Verify OS and environment.
  - Windows: use WSL2 (per root TECH_SPEC) and run commands inside WSL.
  - macOS/Linux: run natively.
- Verify required tools/libraries are installed for this stage (Python 3.10+, pandas).
- If any dependency is missing, install it before running the script.
- You are responsible for errors/logs when running manually.

Metadata schema (minimal)
- `sample_id` (string): must match FASTQ prefix exactly.
- `condition` (string): `control` (baseline, untreated) or `disease` (condition, treated).
- `run_id` (string): run/library identifier (e.g., SRR accession).

Metadata schema (recommended)
- `patient_id` (string)
- `sample_type` (string; e.g., `baseline`, `condition`)
- `library_prep` (string)
- `batch` (string)
- `fastq_prefix` (string; only if different from `sample_id`)
- `notes` (string)

Example metadata (TSV)
```
sample_id	condition	run_id	patient_id	sample_type	batch
SRR14762238	control	SRR14762238	P01	baseline	B1
SRR14762239	disease	SRR14762239	P01	condition	B1
```

Consistent naming rules
- FASTQ prefix must equal `sample_id`.
- One sample = one prefix, repeated across all reads.
- Example for sample `SRR14762238`:
  - `data/fastq/SRR14762238_R1.fastq.gz`
  - `data/fastq/SRR14762238_R2.fastq.gz`
  - `data/fastq/SRR14762238_R3.fastq.gz`

Notes
- Keep raw FASTQ out of git.
- All downstream steps assume `metadata.cleaned.tsv`.
