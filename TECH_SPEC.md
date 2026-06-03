# AI Tech Spec (Root)

Purpose
- Provide an entry point for AI agents to execute the pipeline end-to-end.
- Support autonomous execution from a single command such as `zapusti analiz`.
- Treat `scripts/run_agentic_pipeline.py` as the canonical orchestration layer for the legacy `01_...12_` workflow.
- Keep formal release/version metadata out of the repo until the workflow is ready for publication or public distribution.

Repository layout
- Root folders:
  - `config/`   : shared configuration (references, parameters)
  - `data/`     : raw inputs (FASTQ, metadata)
  - `docs/`     : shared documentation
  - `notebooks/`: exploratory notebooks
  - `../results/`  : shared analysis outputs outside repo
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
- GATK 4 + Java
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
  - `gatk --help`
  - `cellsnp-lite --help`

Installation policy
- The autonomous runner may perform best-effort installation and environment checks before Stage 01.
- Stage-specific Python scripts remain computation-focused and do not install dependencies themselves.
- Preferred approach: micromamba/conda environment per tool group.
- On Windows, the agent should prefer WSL2 for bioinformatics toolchain stability.

OS-specific install recipes (reference)
- Windows (WSL2 Ubuntu; run inside WSL):
  - `sudo apt-get update`
  - `sudo apt-get install -y samtools default-jre`
  - `conda install -c bioconda -c conda-forge star gatk4 cellsnp-lite`
  - `pip install numpy pandas scipy scikit-learn scanpy anndata flask`
- macOS:
  - `brew install star samtools`
  - `pip install numpy pandas scipy scikit-learn scanpy anndata flask`
  - `conda install -c bioconda -c conda-forge gatk4 cellsnp-lite`
- Linux (Ubuntu/Debian):
  - `sudo apt-get install -y samtools default-jre`
  - `pip install numpy pandas scipy scikit-learn scanpy anndata flask`
  - `conda install -c bioconda -c conda-forge star gatk4 cellsnp-lite`

Resource guidance (rough)
- STARsolo alignment: CPU 8-16 cores; RAM 32-64 GB; disk 100+ GB
- GATK RNA calling: CPU 4-8 cores; RAM 16-32 GB
- cellsnp-lite: CPU 4-8 cores; RAM 16-32 GB
- ML + correlation: CPU 2-8 cores; RAM 8-16 GB

Status system (required)
- Initialize status DB before running any stage:
  - `python scripts/status.py init --config config/status_config.json`
- Each stage run script logs start/finish/error and scans outputs.
- Web UI:
  - `python status/app.py --port 5556`
  - Open `http://localhost:5556`
  - Canonical entrypoint: `python scripts/run_agentic_pipeline.py --auto-install --start-status`

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
- Bundled whitelists (preferred): repo includes common 10x whitelist files at `config/ref/whitelists/10x/`. Use these to avoid external downloads; copy the correct one to `config/ref/whitelist.txt` (gunzip first if needed).
  - 10x v1 (3-read): `737K-april-2014_rc.txt`
  - 10x 3' v2: `737K-august-2016.txt`
  - 10x 3' v3/v3.1: `3M-february-2018_TRU.txt.gz`
  - 10x 3' v4: `3M-3pgex-may-2023_TRU.txt.gz`
  - 10x 5' v3: `3M-5pgex-jan-2023.txt.gz`
  - 10x 3' LT: `9K-LT-march-2021.txt.gz`
  - 10x Fixed RNA Profiling: `737K-fixed-rna-profiling.txt.gz`
- Known dataset mappings (update if protocol differs):
  - PAD dataset (3-read): `read_structure=three_read`, whitelist `737K-april-2014_rc.txt` (10x v1).
  - Test FASTQ (2-read R1=28, R2~90): `read_structure=two_read`, whitelist `3M-february-2018_TRU.txt.gz` (10x 3' v3/v3.1).
  - CVD-like 10x v3/v3.1 datasets: `read_structure=two_read`, whitelist `3M-february-2018_TRU.txt.gz`.

Whitelist selection requirement
- Preferred autonomous behavior:
  - infer chemistry from known dataset mappings or `read_structure`
  - copy the corresponding bundled whitelist into `config/ref/whitelist.txt`
  - report the choice in logs/status
- If inference is ambiguous, the agent should request clarification.

FASTQ expectations
- User-provided scRNA-seq dataset (control vs disease).
- Supported read structures:
  - two_read (default): R1 = barcode (CB/UMI), R2 = cDNA.
  - three_read (legacy 10x v1): R1 = cDNA, R2 = CB, R3 = UMI (R2+R3 merged for STARsolo).
  - Set `read_structure` in `config/starsolo_config.json` to select.
  - Aliases: `common`, `tenx_v2`, `tenx_v3`, `tenx_v2v3`, `tenx_5p` map to two_read; `tenx_v1` maps to three_read.

Naming convention
- `SAMPLEID_R1.fastq.gz`
- `SAMPLEID_R2.fastq.gz`

Execution protocol
1) The single `main_agent` owns the whole workflow.
2) For each stage, a subordinate `stage_preflight_agent` or skill checks inputs, config paths, and required tools.
3) If preflight passes, a subordinate `stage_execution_agent` or skill runs the deterministic stage command.
4) After execution, a subordinate `stage_review_agent` or skill checks whether the outputs are valid for downstream use.
5) Then a subordinate `stage_report_agent` or skill writes a mini report and mini interpretation for the stage.
6) The `main_agent` decides whether the workflow may advance to the next stage.
7) After the last stage, the `main_agent` writes the final integrated report, final interpretation, and bundle-level figures/tables summary.

Canonical entrypoints
- `python scripts/run_agentic_pipeline.py --auto-install --start-status --use-wsl`
- `python scripts/launch_pipeline_background.py --use-wsl --watchdog-interval 10`
- `./zapusti_analiz.ps1`

Data hygiene
- Do not write outputs outside `../results/` or stage `outputs/` unless explicitly stated.

Report bundle
- The final stage copies stage outputs into `for_report/`.
- Naming convention: `<stage>_<index>_<purpose>.<ext>`, e.g. `08_cellsnp_1_heatmap.jpg`.
