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
  - `status/`   : Flask status web UI
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

Core tools (stage-specific use)
- STAR/STARsolo
- samtools
- bcftools + htslib + tabix
- cellsnp-lite

Core Python libs (stage-specific use)
- numpy, pandas, scipy
- scikit-learn
- scanpy/anndata (optional)
- flask (status UI)

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
  - `pip install numpy pandas scipy scikit-learn scanpy anndata flask`
- macOS:
  - `brew install star samtools bcftools htslib tabix`
  - `pip install numpy pandas scipy scikit-learn scanpy anndata flask`
  - `conda install -c bioconda -c conda-forge cellsnp-lite`
- Linux (Ubuntu/Debian):
  - `sudo apt-get install -y samtools bcftools tabix`
  - `pip install numpy pandas scipy scikit-learn scanpy anndata flask`
  - `conda install -c bioconda -c conda-forge star cellsnp-lite`

Resource guidance (rough)
- STARsolo alignment: CPU 8-16 cores; RAM 32-64 GB; disk 100+ GB
- bcftools calling: CPU 4-8 cores; RAM 8-16 GB
- cellsnp-lite: CPU 4-8 cores; RAM 16-32 GB
- ML + correlation: CPU 2-8 cores; RAM 8-16 GB

Status system (required)
- Initialize status DB before running any stage:
  - `python scripts/status.py init --config config/status_config.json`
- Each stage run script logs start/finish/error and scans outputs.
- Web UI:
  - `python status/app.py --port 5556`
  - Open `http://localhost:5556`

Initial inputs (required)
- `data/fastq/` : raw scRNA-seq FASTQ files.
- `data/metadata/metadata.tsv` : sample metadata with columns:
  - `sample_id` (matches FASTQ filename prefix)
  - `condition` (control [baseline, untreated] or disease [condition, treated])
  - `run_id`

Reference preparation (required before Stage 02)
- Set reference file locations:
  - `config/ref/genome.fa`
  - `config/ref/genes.gtf`
  - `config/ref/STAR_index/`
  - `config/ref/whitelist.txt`
- Example: GENCODE human GRCh38 primary assembly (FASTA) + matching GTF:
  - FASTA: `https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_48/GRCh38.primary_assembly.genome.fa.gz`
  - GTF: `https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_48/gencode.v48.primary_assembly.annotation.gtf.gz`
- Example download commands:
```bash
mkdir -p config/ref
curl -L -o config/ref/genome.fa.gz https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_48/GRCh38.primary_assembly.genome.fa.gz
curl -L -o config/ref/genes.gtf.gz https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_48/gencode.v48.primary_assembly.annotation.gtf.gz
gunzip -c config/ref/genome.fa.gz > config/ref/genome.fa
gunzip -c config/ref/genes.gtf.gz > config/ref/genes.gtf
```
- STAR index build (use the same FASTA/GTF):
```bash
mkdir -p config/ref/STAR_index
STAR --runMode genomeGenerate \
  --genomeDir config/ref/STAR_index \
  --genomeFastaFiles config/ref/genome.fa \
  --sjdbGTFfile config/ref/genes.gtf \
  --sjdbOverhang <READ_LENGTH_MINUS_1> \
  --runThreadN <THREADS>
```
- Whitelist (10x): pick the correct barcode list for your chemistry; 10x publishes the names and mapping by chemistry in their barcode inclusion list doc. Download or copy into `config/ref/whitelist.txt`.
  - 3' v3/v3.1: `3M-february-2018.txt.gz`
  - 3' v2: `737k-august-2016.txt`
  - If you have Cell Ranger installed, the lists are inside its `lib/python/cellranger/barcodes/` directory.
  - Direct download mirrors (if needed):
```bash
curl -L -o config/ref/whitelist.txt.gz https://github.com/10XGenomics/cellranger/raw/master/lib/python/cellranger/barcodes/3M-february-2018.txt.gz
gunzip -c config/ref/whitelist.txt.gz > config/ref/whitelist.txt
```
- Auto-download policy (required): the agent must download the correct whitelist for the dataset chemistry and place it at `config/ref/whitelist.txt` before running Stage 02. If chemistry is unknown, the agent must ask the user or infer from dataset metadata and report the choice.

FASTQ expectations
- User-provided scRNA-seq dataset (control vs disease).
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
