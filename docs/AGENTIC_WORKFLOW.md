# Agentic Workflow

The canonical workflow for the legacy `01_...12_` pipeline is:

1. There is one `main_agent` for the whole workflow.
2. For each stage, the `main_agent` invokes a subordinate `stage_preflight_agent` or skill to validate inputs and readiness.
3. If preflight passes, the `main_agent` invokes a subordinate `stage_execution_agent` or skill to run the deterministic stage script.
4. After execution, the `main_agent` invokes a subordinate `stage_review_agent` or skill to verify the run and the outputs.
5. Then the `main_agent` invokes a subordinate `stage_report_agent` or skill to generate a mini report and mini interpretation for that stage.
6. Only the `main_agent` decides whether the workflow may advance to the next stage.
7. After the last stage, the `main_agent` generates the final integrated report, interpretation, and the bundle of figures and tables produced across the workflow.

## Scientific Priority

The pipeline is not organized around mutation calling alone.
Its scientific endpoint is the integrated interpretation of whether mutation-linked signals track expression-linked signals.

The workflow priority is:

1. Generate validated alignment, variant, burden, and cluster-level mutation artifacts in Stages `01..10`.
2. Use `11_correlation` as the primary integration stage for mutation burden, signatures, cluster-level mutation summaries, and expression-linked summaries.
3. Use `12_integrated_interpretation` to compare the observed mutation-expression relationships with other studies and to discuss whether the observed associations are compatible with mutation-associated expression changes.

The repo should therefore be read as:

- `01..10`: enabling stages
- `11`: main integrative scientific stage
- `12`: final literature-aware interpretation stage

## Canonical runner

- `python scripts/run_agentic_pipeline.py --auto-install --start-status --use-wsl`
- `./zapusti_analiz.ps1`

## Agent roles

- `Codex`:
  - main agent
  - stage execution agent
  - stage report agent
- `Qwen`:
  - stage preflight agent
  - adversarial input/output sanity checks
- `Claude`:
  - stage review agent
  - scientific/methodological signoff
- `Cursor`:
  - optional implementation/debugging support
  - not used as the canonical signoff source

## Control Model

- Exactly one `main_agent` controls progression through the pipeline.
- Subordinate agents or skills are used for stage-local work only.
- A stage never advances itself.
- Only the `main_agent` can decide that the current stage is complete and that the workflow may proceed.

## Stage Pattern

Every numbered stage follows the same control contract:

1. `stage_preflight_agent`
   - checks required inputs, config paths, tools, and stage-specific readiness
2. `stage_execution_agent`
   - runs the deterministic stage script
3. `stage_review_agent`
   - validates that expected outputs exist and are suitable for downstream use
4. `stage_report_agent`
   - writes a short stage report and stage-local interpretation
5. `main_agent`
   - decides whether to continue or stop

This pattern is mandatory for every stage from `01_input_data` through `12_integrated_interpretation`.

## Stage Intent

- `01_input_data`: establish trustworthy sample and metadata readiness.
- `02_starsolo`: create the expression-aware alignment backbone used by the mutation and single-cell branches.
- `03_gatk_call`: generate filtered expressed-variant calls per sample.
- `04_cohort_filter`: define the cohort-level mutation set used downstream.
- `05_variant_to_gene`: connect cohort variants to genes.
- `06_gene_burden`: build the sample-by-gene mutation burden feature matrix.
- `07_ml_control_vs_disease`: test whether mutation-derived gene features separate biological groups.
- `08_cellsnp`: recover per-cell allele information for cohort-common variants.
- `09_cluster_aggregation`: summarize mutation burden at the cluster level.
- `10_mutational_analysis`: quantify sample-level mutational burden and signature structure.
- `11_correlation`: perform the main mutation-expression integration step and identify the strongest associations between mutation-linked and expression-linked summaries.
- `12_integrated_interpretation`: produce the final report, figures, tables, and literature-aware interpretation of mutation-expression coupling.

## External agent adapters

The repo is designed to work even when external agent CLIs or APIs are not configured.

- Builtin deterministic validation is the canonical signoff mechanism.
- Optional external adapters for Codex / Claude / Qwen / Cursor can be configured in `config/agentic_pipeline_config.json`.
- When adapters are enabled, the runner writes prompt files and captures responses under each stage `outputs/agentic/` directory.
- If `required_for_advance` is enabled for a role, the provider response must include an approval token matching `approval_regex`.

## Stage artifacts

For each stage, the runner writes:

- `<stage>/outputs/agentic/<stage>.preflight.json`
- `<stage>/outputs/agentic/<stage>.execution.json`
- `<stage>/outputs/agentic/<stage>.review.json`
- `<stage>/outputs/agentic/<stage>.mini_report.md`
- `<stage>/outputs/agentic/<stage>.mini_report.json`
- `<stage>/outputs/agentic/<stage>.main_agent_decision.json`

Optional external prompt/response artifacts are also written next to these files.

## Final artifacts

At the end of the workflow, the `main_agent` writes:

- `12_integrated_interpretation/outputs/agentic/final_report.md`
- `12_integrated_interpretation/outputs/agentic/final_report.json`
- `for_report/agentic_final_report.md`
- `for_report/agentic_stage_manifest.tsv`
- `for_report/agentic_stage_reports/`

## Interpretation Rule

The final workflow interpretation must explicitly answer:

1. Which mutation-derived quantities changed across samples or groups?
2. Which expression-linked quantities changed across samples or groups?
3. Which mutation-expression associations were strongest in `11_correlation`?
4. Do those associations agree with, extend, or conflict with other studies?
5. Does the evidence support association only, or is there a justified argument for mutation-associated influence on expression programs?

## Design rule

Bioinformatics and ML stages remain deterministic Python / shell scripts.
The agentic layer does not replace the scientific code with chat output.
It wraps each stage with subordinate validation/review/report agents and a single controlling main agent.
