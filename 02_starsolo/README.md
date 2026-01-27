# 02_starsolo: STARsolo alignment

Purpose
- Align scRNA-seq reads and produce CB/UB-tagged BAM/BAI for downstream variant calling.

Inputs
- FASTQ files in `data/fastq/` with consistent naming.
- `data/metadata/metadata.cleaned.tsv` (from Stage 01).
- Reference genome FASTA (e.g., `config/ref/genome.fa`).
- Gene annotation GTF (e.g., `config/ref/genes.gtf`).
- STAR genome index directory (built from the same FASTA+GTF).

Outputs
- CB/UB-tagged BAM + BAI for each sample.
- STARsolo summary logs per sample.
- Stage outputs saved under `outputs/`.

How to run (manual)
1) Ensure STAR and STARsolo are installed and on PATH.
2) Edit `config/starsolo_config.json` (paths + CB/UMI settings).
3) Run the stage script:
   - `bash scripts/run_02_starsolo_stage.sh`
4) Outputs are written into `outputs/`.

Config notes (important)
- `star_index`: STAR genome index directory.
- `gtf`: gene annotation GTF (same build as STAR index).
- `solo` fields must match your library chemistry (CB/UMI positions and whitelist).

Pre-run checks (manual)
- Verify OS and environment.
  - Windows: use WSL2 (per root TECH_SPEC) and run commands inside WSL.
  - macOS/Linux: run natively.
- Verify STAR/STARsolo and samtools are installed.
- Confirm reference FASTA, GTF, and STAR index paths are correct.
- You are responsible for errors/logs when running manually.

Success criteria
- For each sample, BAM and BAI are present and non-empty.
- STARsolo log files are present.

Next stage
- Proceed to `03_bcftools_call`.
