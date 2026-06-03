# 03_gatk_call: GATK RNA-seq variant calling

Purpose
- Call expressed variants from CB/UB-tagged BAM files using the GATK RNA-seq workflow.

Inputs
- CB/UB BAM + BAI from `02_starsolo/outputs/artifacts/`.
- Reference genome FASTA (for example `config/ref/genome.fa`).

Outputs
- PASS-only filtered VCF per sample.
- Intermediate GATK logs per sample.
- Stage outputs saved under `outputs/`.

How to run (manual)
1) Ensure `gatk`, `samtools`, and Java are installed.
2) Set paths in `config/gatk_config.json`.
3) Run:
   - `python scripts/run_gatk.py --bam-dir ../02_starsolo/outputs/artifacts --config ../config/gatk_config.json --outdir outputs/artifacts`

How to keep two samples running in parallel
- Use the repository-level launcher from the repo root:
  `python scripts/launch_gatk_parallel_supervisor.py --run-root "PATH_TO_GATK_RUN_FOLDER" --max-parallel 2`
- By default it reads BAMs from `PATH_TO_GATK_RUN_FOLDER/input_bam_remaining_13`, writes per-sample input link folders named `input_bam_parallel_<sample>`, and starts one-sample `run_gatk.py` workers until two samples are active.
- It launches the next pending sample when one active sample finishes.

Success criteria
- Filtered VCFs exist and are non-empty for each sample.

Next stage
- Proceed to `04_cohort_filter`.
