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
  - Barcode whitelist file (chemistry-specific)

Prerequisites
- STAR (STARsolo)
- samtools

OS check
- Windows: require WSL2; execute all commands inside WSL.
- macOS/Linux: run natively.

Actions
1) Verify FASTQ files exist for all samples in `metadata.cleaned.tsv`.
2) Verify reference FASTA, GTF, STAR index, and whitelist are available.
   - See root `TECH_SPEC.md` > "Reference preparation (required before Stage 02)" for download links and build steps.
   - If whitelist is missing, download the correct 10x list (chemistry-specific) and save it as `config/ref/whitelist.txt`.
3) Ensure `config/starsolo_config.json` is filled (paths + CB/UMI settings).
4) For each sample, run STARsolo with:
   - cDNA read = R2
   - barcode read = R1 (CB/UMI)
5) Save outputs under `outputs/`.

Outputs
- CB/UB BAM + BAI per sample.
- STARsolo logs per sample.

Exit criteria
- BAM/BAI exist and are non-empty for each sample.
- STARsolo logs exist (Log.final.out).

Next stage
- Proceed to `03_bcftools_call`.

