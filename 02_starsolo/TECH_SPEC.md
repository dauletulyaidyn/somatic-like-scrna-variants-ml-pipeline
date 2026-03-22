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
   - Preferred: copy from bundled `config/ref/whitelists/10x/` and gunzip if needed.
3) Ensure `config/starsolo_config.json` is filled (paths + CB/UMI settings).
   - Set `read_structure`:
     - `two_read` (default): R1 = CB/UMI, R2 = cDNA.
     - `three_read`: R1 = cDNA, R2 = CB, R3 = UMI (R2+R3 merged).
     - Aliases: `common`, `tenx_v2`, `tenx_v3`, `tenx_v2v3`, `tenx_5p` => two_read; `tenx_v1` => three_read.
   - Confirm chemistry with the user before running, and select the matching whitelist.
4) For each sample, run STARsolo with:
   - two_read: cDNA = R2, barcode = R1 (CB/UMI)
   - three_read: cDNA = R1, barcode = R2+R3 (CB+UMI merged)
5) Save outputs under `outputs/`.

Outputs
- CB/UB BAM + BAI per sample.
- STARsolo logs per sample.

Exit criteria
- BAM/BAI exist and are non-empty for each sample.
- STARsolo logs exist (Log.final.out).

Next stage
- Proceed to `03_gatk_call`.

