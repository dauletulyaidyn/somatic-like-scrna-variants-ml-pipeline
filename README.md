# Pipeline Repository

Author: Kunikeyev Aidyn  
DOI:  
Git:  

This repository contains a stage-by-stage pipeline for expressed-variant analysis from scRNA-seq.

## What this is
- Data source: scRNA-seq with control (baseline, untreated) vs disease (condition, treated) groups.
- Goal: extract expressed variants, build gene-burden features, classify control (baseline, untreated) vs disease (condition, treated), and correlate with mutational analysis outputs.
- Each stage lives in its own folder with:
  - `TECH_SPEC.md` (AI agent instructions)
  - `README.md` (manual run instructions)
  - `scripts/` (bash + python as needed)
  - `outputs/metrics/` and `outputs/artifacts/` (ignored by git)

## Root folders (common)
- `config/`     : shared configuration (references, parameters)
- `data/`       : raw inputs (FASTQ, metadata); not tracked by git
- `docs/`       : shared documentation and runbooks
- `notebooks/`  : exploratory notebooks
- `../results/` : shared outputs outside repo (used for manuscript)
- `for_report/` : curated tables/figures copied by final stage
- `scripts/`    : shared utilities used across stages
- `status/`     : Flask status web UI (port 5556)

## Requirements (manual run)
If you run without the AI agent, **you are responsible** for:
- Installing all required tools and Python libraries per stage.
- Providing sufficient compute resources (CPU/RAM/disk).
- Monitoring logs and handling errors.
- All tools/libs must be installed and verified before starting Stage 01.
- Stage scripts do not perform installation or environment checks.

Minimum environment
- Windows with WSL2 (Ubuntu) for Windows users.
- macOS or Linux supported natively.
- Python 3.10+.

Core tools (used across stages)
- STAR/STARsolo, samtools
- bcftools + htslib + tabix
- cellsnp-lite (single-cell stage)

Core Python libraries (stage-specific)
- numpy, pandas
- scipy
- scikit-learn
- scanpy/anndata (optional)
- flask (status UI)

OS-specific setup (summary)
- Windows (use WSL2 Ubuntu; run installs inside WSL):
  - `sudo apt-get update`
  - `sudo apt-get install -y samtools bcftools tabix`
  - `conda install -c bioconda -c conda-forge star cellsnp-lite`
  - `pip install numpy pandas scipy scikit-learn scanpy anndata flask`
- macOS:
  - `brew install star samtools bcftools htslib tabix`
  - `pip install numpy pandas scipy scikit-learn scanpy anndata flask`
  - `conda install -c bioconda -c conda-forge cellsnp-lite`
- Linux (Ubuntu/Debian):
  - `sudo apt-get install -y samtools bcftools tabix`
  - `pip install numpy pandas scipy scikit-learn scanpy anndata flask`
  - `conda install -c bioconda -c conda-forge star cellsnp-lite`

## Stage folders
- `01_input_data/`
- `02_starsolo/`
- `03_bcftools_call/`
- `04_cohort_filter/`
- `05_variant_to_gene/`
- `06_gene_burden/`
- `07_ml_control_vs_disease/`
- `08_cellsnp/`
- `09_cluster_aggregation/`
- `10_mutational_analysis/`
- `11_correlation/`
- `12_integrated_interpretation/`

## Required initial inputs
Place raw inputs in `data/` (not tracked by git):
- FASTQ: `data/fastq/`
- Metadata: `data/metadata/metadata.tsv`

## Whitelist selection (required)
Before running Stage 02, you must select the correct 10x whitelist for your library chemistry:
- Identify chemistry (e.g., 10x 3' v3/v3.1, 3' v2, 3' v1, 5' v3).
- Copy the corresponding file from `config/ref/whitelists/10x/` into `config/ref/whitelist.txt` (gunzip if needed).
- If chemistry is unknown, stop and determine it from protocol/metadata before proceeding.

### FASTQ expectations
- Data type: scRNA-seq.
- STARsolo is configured for platforms with CB/UB tags from barcode reads.
- Expected reads for this project:
  - two_read (default): R1 = barcode (CB/UMI), R2 = cDNA.
  - three_read (legacy 10x v1): R1 = cDNA, R2 = CB, R3 = UMI (R2+R3 merged).
  - Aliases: `common`, `tenx_v2`, `tenx_v3`, `tenx_v2v3`, `tenx_5p` => two_read; `tenx_v1` => three_read.

### FASTQ naming
Use consistent sample prefixes:
- `SAMPLEID_R1.fastq.gz`
- `SAMPLEID_R2.fastq.gz`
- `SAMPLEID_R3.fastq.gz` (required only for three_read)

All downstream stages assume `metadata.cleaned.tsv` from Stage 01.

## Status web UI (port 5556)
1) Install Flask: `pip install flask`
2) Run server: `python status/app.py --port 5556`
3) Open: `http://localhost:5556`

## Start here
1) Go to `01_input_data/`.
2) Follow `README.md` for manual execution or `TECH_SPEC.md` for AI-agent execution.

## Report bundle convention
- The final stage copies tables/figures from each stage into `for_report/`.
- Filenames must start with the stage name and an index, then a short purpose, e.g.:
  - `08_cellsnp_1_heatmap.jpg`
  - `08_cellsnp_1_heatmap.csv`
  - `08_cellsnp_2_summary.tsv`
