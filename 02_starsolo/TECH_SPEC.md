# AI Tech Spec: 02_starsolo

Objective
- Run STARsolo to align scRNA-seq reads and generate CB/UB-tagged BAM/BAI.

Entry
- Working directory: `02_starsolo`
- Required inputs:
  - FASTQ in `data/fastq/`
  - `data/metadata/metadata.cleaned.tsv`
  - Reference genome FASTA
  - Gene annotation GTF
  - STAR index directory (built from the same FASTA+GTF)

Prerequisites
- STAR (STARsolo)
- samtools

Actions
1) Verify FASTQ files exist for all samples in `metadata.cleaned.tsv`.
2) Verify reference FASTA, GTF, and STAR index are available.
3) For each sample, run STARsolo with:
   - cDNA read = R3
   - barcode read = R2 (CB/UB)
4) Save outputs under `outputs/`.

Outputs
- CB/UB BAM + BAI per sample.
- STARsolo logs per sample.

Exit criteria
- BAM/BAI exist and are non-empty for each sample.
- STARsolo logs exist (Log.final.out).

Next stage
- Proceed to `03_bcftools_call`.

