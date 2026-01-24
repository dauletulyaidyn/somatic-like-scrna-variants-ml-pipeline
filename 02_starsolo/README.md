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
2) Set paths to reference FASTA, GTF, and STAR index.
3) For each sample, run STARsolo using:
   - R3 as cDNA read
   - R2 as barcode read (CB/UB)
4) Write BAM/BAI and logs into `outputs/`.

Success criteria
- For each sample, BAM and BAI are present and non-empty.
- STARsolo log files are present.

Next stage
- Proceed to `03_bcftools_call`.
