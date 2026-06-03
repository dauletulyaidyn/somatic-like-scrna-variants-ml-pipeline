# scRNA-seq Agentic Pipeline

Author: Kunikeyev Aidyn

This repository contains one working pipeline for integrated scRNA-seq expression and mutation analysis.

The canonical workflow is the legacy `01_...12_` stage chain, controlled by one `main_agent`.

## What The Repo Does

Input:
- scRNA-seq FASTQ files
- sample metadata
- reference genome, GTF, STAR index, and 10x whitelist

Main outputs:
- STARsolo alignment artifacts
- filtered RNA-seq variant calls from GATK
- cohort-common variants
- variant-to-gene tables
- gene burden matrix
- control vs disease ML results
- cellsnp-lite per-cell allele counts
- cluster-level mutation summaries
- mutational burden and signature tables
- integrated expression-mutation correlation outputs
- final reproducibility report bundle in `for_report/`

## Agent Model

There is one controlling `main_agent`.

For every stage, the `main_agent` does this:
1. calls a subordinate preflight agent or skill
2. calls a subordinate execution agent or skill
3. calls a subordinate review agent or skill
4. calls a subordinate mini-report agent or skill
5. decides whether the workflow can move to the next stage

After the last stage, the `main_agent` writes the final integrated report, interpretation, and bundle summary.

Scientific priority:
- `01..10` generate the validated inputs needed for interpretation.
- `11_correlation` is the primary integrative stage.
- `12_integrated_interpretation` must explain whether mutation-linked signals are associated with expression-linked signals and how that compares with other studies.

Current role mapping:
- `Codex`: `main_agent`, `stage_execution_agent`, `stage_report_agent`
- `Qwen`: `stage_preflight_agent`
- `Claude`: `stage_review_agent`
- `Cursor`: optional implementation support

More detail:
- `docs/AGENTIC_WORKFLOW.md`
- `docs/AGENTIC_WORKFLOW_REVIEW.md`

## Stage Order

The canonical pipeline is:

1. `01_input_data`
   Validates FASTQ naming and metadata, then writes cleaned metadata.
2. `02_starsolo`
   Runs STARsolo and produces barcode-aware alignment outputs.
3. `03_gatk_call`
   Runs RNA-seq variant calling and writes filtered per-sample VCFs.
4. `04_cohort_filter`
   Builds a cohort-common VCF.
5. `05_variant_to_gene`
   Maps cohort variants to genes using the GTF.
6. `06_gene_burden`
   Builds the gene-by-sample burden matrix.
7. `07_ml_control_vs_disease`
   Runs ML classification and permutation testing.
8. `08_cellsnp`
   Runs cellsnp-lite for per-cell allele counting.
9. `09_cluster_aggregation`
   Aggregates cellsnp outputs to cluster-level mutation summaries.
10. `10_mutational_analysis`
   Builds sample-level mutation burden and signature summaries.
11. `11_correlation`
   Builds the main mutation-expression integration layer and identifies the strongest associations.
12. `12_integrated_interpretation`
   Collects outputs into the final bundle and writes the final literature-aware reporting artifacts.

## Minimal Repo Layout

- `01_input_data/` ... `12_integrated_interpretation/`: canonical stages
- `config/`: pipeline configs and references
- `data/`: user-provided FASTQ and metadata
- `docs/`: workflow documentation
- `scripts/`: shared runner and helper scripts
- `status/`: Flask status UI
- `for_report/`: final bundle created by the last stage

## Required Inputs

Put your working inputs here:

- `data/fastq/`
- `data/metadata/metadata.tsv`

Required metadata columns:
- `sample_id`
- `condition`
- `run_id`

## Required References

The pipeline expects:

- `config/ref/genome.fa`
- `config/ref/genes.gtf`
- `config/ref/STAR_index/`
- `config/ref/whitelist.txt`

The repository already contains bundled 10x whitelist files in:
- `config/ref/whitelists/10x/`

Before running Stage 02, choose the correct whitelist for the library chemistry and copy it to:
- `config/ref/whitelist.txt`

## FASTQ Expectations

Supported read layouts:
- `two_read`: `R1=barcode/UMI`, `R2=cDNA`
- `three_read`: `R1=cDNA`, `R2=CB`, `R3=UMI`

Expected naming:
- `SAMPLEID_R1.fastq.gz`
- `SAMPLEID_R2.fastq.gz`
- `SAMPLEID_R3.fastq.gz` for `three_read` mode only

## Quick Start

Recommended on Windows:

```powershell
./zapusti_analiz.ps1
```

Equivalent explicit command:

```powershell
python scripts/run_agentic_pipeline.py --auto-install --start-status --use-wsl
```

Recommended on Linux/macOS:

```bash
python scripts/run_agentic_pipeline.py --auto-install --start-status
```

Background runner with watchdog:

```powershell
python scripts/launch_pipeline_background.py --use-wsl --watchdog-interval 10
```

## Status UI

Start manually if needed:

```bash
python status/app.py --port 5556
```

Open:
- `http://localhost:5556`

The UI shows:
- stage status
- runner state
- watchdog state
- event log
- scanned output files

For a GATK run folder:

```bash
python scripts/launch_gatk_status_server.py --run-root "PATH_TO_GATK_RUN_FOLDER" --port 5556
```

Open:
- `http://localhost:5556/gatk`

The GATK page refreshes every 10 seconds and shows active process, current sample, current step, per-sample outputs, and variant counts for completed VCF files.

To keep exactly two GATK samples running in parallel for a run folder:

```bash
python scripts/launch_gatk_parallel_supervisor.py --run-root "PATH_TO_GATK_RUN_FOLDER" --max-parallel 2
```

The supervisor starts one-sample workers from `input_bam_remaining_13`, keeps at most two active samples, and launches the next pending sample when a slot opens. It skips stopped or failed samples by default so partial outputs are not overwritten silently.

## What Gets Written Per Stage

Every stage writes agentic artifacts under:
- `<stage>/outputs/agentic/`

Important files:
- `<stage>.preflight.json`
- `<stage>.execution.json`
- `<stage>.review.json`
- `<stage>.mini_report.md`
- `<stage>.mini_report.json`
- `<stage>.main_agent_decision.json`

## Final Outputs

The final stage writes:
- `12_integrated_interpretation/outputs/agentic/final_report.md`
- `12_integrated_interpretation/outputs/agentic/final_report.json`
- `for_report/agentic_final_report.md`
- `for_report/agentic_stage_manifest.tsv`
- `for_report/agentic_stage_reports/`

The `for_report/` directory is a reproducibility report bundle with selected stage outputs and summaries.

## Manual Run Note

If you do not use the agentic runner, you are responsible for:
- environment setup
- tool installation
- resource management
- stage order
- validation of outputs

## Important Docs

- `docs/AGENTIC_WORKFLOW.md`
- `docs/AGENTIC_WORKFLOW_REVIEW.md`
- `TECH_SPEC.md`

## Current Repo State

This is a working research repo state.

Formal release metadata, publication packaging, and public-distribution polish are intentionally not maintained here yet.
