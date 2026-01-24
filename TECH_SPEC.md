# AI Tech Spec (Root)

Purpose
- Provide an entry point for AI agents to execute the pipeline end-to-end.

Repository layout
- Root folders:
  - `config/`   : shared configuration (references, parameters)
  - `data/`     : raw inputs (FASTQ, metadata)
  - `docs/`     : shared documentation
  - `notebooks/`: exploratory notebooks
  - `../results/`  : shared outputs outside repo (used for manuscript)
  - `for_report/`  : curated tables/figures copied by final stage
  - `scripts/`  : shared utilities
- Stage folders are numbered: `01_...` -> `02_...` -> ... -> `12_...`.
- Each stage folder contains:
  - `TECH_SPEC.md` (agent instructions)
  - `README.md` (manual instructions)
  - `scripts/`
  - `outputs/metrics/` and `outputs/artifacts/` (gitignored)

Global prerequisites (check before running any stage)
- OS/runtime:
  - Windows users must use WSL2 (Ubuntu) for toolchain stability.
  - macOS or Linux supported natively.
  - Python 3.10+ available.
- Core tools (stage-specific use):
  - STAR/STARsolo
  - samtools
  - bcftools + htslib + tabix
  - cellsnp-lite (for stage 08)
  - R (optional, if used for plots)
- Core Python libs (stage-specific use):
  - numpy, pandas
  - scipy
  - scikit-learn (ML stage)
  - scanpy/anndata (single-cell utilities, optional)

Global checks (examples)
- OS check:
  - Windows (PowerShell): `$PSVersionTable.OS`
  - macOS/Linux: `uname -a`
- Tool checks:
  - `python --version`
  - `STAR --version`
  - `samtools --version`
  - `bcftools --version`
  - `tabix --version`
  - `cellsnp-lite --help`

Installation policy
- All required tools/libs must be installed and verified before starting Stage 01.
- Stage scripts must NOT attempt installation or environment checks.
- Preferred approach: micromamba/conda environment per tool group.
- On Windows, the agent must install/enable WSL2 before proceeding and run all tool installs inside WSL.

OS-specific install recipes (reference)
- Windows (WSL2 Ubuntu; run inside WSL):
  - `sudo apt-get update`
  - `sudo apt-get install -y samtools bcftools tabix`
  - `conda install -c bioconda -c conda-forge star cellsnp-lite`
  - `pip install numpy pandas scipy scikit-learn scanpy anndata`
- macOS:
  - `brew install star samtools bcftools htslib tabix`
  - `pip install numpy pandas scipy scikit-learn scanpy anndata`
  - `conda install -c bioconda -c conda-forge cellsnp-lite`
- Linux (Ubuntu/Debian):
  - `sudo apt-get install -y samtools bcftools tabix`
  - `pip install numpy pandas scipy scikit-learn scanpy anndata`
  - `conda install -c bioconda -c conda-forge star cellsnp-lite`

Resource guidance (rough)
- STARsolo alignment: CPU 8-16 cores; RAM 32-64 GB (genome index dependent); disk 100+ GB
- bcftools calling: CPU 4-8 cores; RAM 8-16 GB; disk moderate
- cellsnp-lite: CPU 4-8 cores; RAM 16-32 GB; disk moderate
- ML + correlation: CPU 2-8 cores; RAM 8-16 GB

Initial inputs (required)
- `data/fastq/` : raw scRNA-seq FASTQ files.
- `data/metadata/metadata.tsv` : sample metadata with columns:
  - `sample_id` (matches FASTQ filename prefix)
  - `condition` (WE or UWE)
  - `run_id`

FASTQ expectations
- scRNA-seq dataset (PRJNA736095).
- Read structure used in this project:
  - R2 = barcode (CB/UB)
  - R3 = cDNA
  - R1 optional or index read

Naming convention
- `SAMPLEID_R1.fastq.gz`
- `SAMPLEID_R2.fastq.gz`
- `SAMPLEID_R3.fastq.gz`

Execution protocol
1) Start in `01_input_data/`.
2) Read `TECH_SPEC.md` and execute its actions.
3) Confirm outputs, then proceed to the next stage folder indicated by the spec.
4) Repeat until `12_integrated_interpretation/`.

Data hygiene
- Do not write outputs outside `../results/` or stage `outputs/` unless explicitly stated.

Report bundle
- The final stage copies stage outputs into `for_report/`.
- Naming convention: `<stage>_<index>_<purpose>.<ext>`, e.g. `08_cellsnp_1_heatmap.jpg`.
