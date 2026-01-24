# Stage 01: Input data

Purpose
- Prepare raw scRNA-seq FASTQ and metadata for downstream steps.
- Ensure consistent sample IDs and file layout.

Inputs
- Raw FASTQ files (R1/R2/R3 as applicable by platform).
- Sample metadata (TSV/CSV).

Outputs
- Standardized input directory with FASTQ files.
- Cleaned metadata table with sample IDs.

How to run (manual)
1) Place FASTQ files under `data/fastq/` with consistent naming.
2) Create `data/metadata/metadata.tsv` with at least: `sample_id`, `condition` (WE/UWE), `run_id`.
3) Run the check script:
   - `python scripts/validate_inputs.py --fastq-dir ../data/fastq --metadata ../data/metadata/metadata.tsv --out ../data/metadata/metadata.cleaned.tsv`

Pre-run checks (manual)
- Verify required tools/libraries are installed for this stage (Python 3.10+, pandas).
- If any dependency is missing, install it before running the script.

Metadata schema (minimal)
- `sample_id` (string): must match FASTQ prefix exactly.
- `condition` (string): `WE` or `UWE`.
- `run_id` (string): run/library identifier (e.g., SRR accession).

Metadata schema (recommended)
- `patient_id` (string)
- `sample_type` (string; e.g., `wound_edge`, `unwounded_skin`)
- `library_prep` (string)
- `batch` (string)
- `fastq_prefix` (string; only if different from `sample_id`)
- `notes` (string)

Example metadata (TSV)
```
sample_id	condition	run_id	patient_id	sample_type	batch
SRR14762238	WE	SRR14762238	P01	wound_edge	B1
SRR14762239	UWE	SRR14762239	P01	unwounded_skin	B1
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
