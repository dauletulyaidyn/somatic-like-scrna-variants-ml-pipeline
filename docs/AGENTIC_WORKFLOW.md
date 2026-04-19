# Agentic Workflow

The canonical workflow for the legacy `01_...12_` pipeline is now:

1. There is one `main_agent` for the whole workflow.
2. For each stage, the `main_agent` invokes a subordinate `stage_preflight_agent` or skill to validate inputs and readiness.
3. If preflight passes, the `main_agent` invokes a subordinate `stage_execution_agent` or skill to run the deterministic stage script.
4. After execution, the `main_agent` invokes a subordinate `stage_review_agent` or skill to verify the run and the outputs.
5. Then the `main_agent` invokes a subordinate `stage_report_agent` or skill to generate a mini report and mini interpretation for that stage.
6. The `main_agent` decides whether to advance to the next stage.
7. After the last stage, the `main_agent` generates the final integrated report, interpretation, and the bundle of figures and tables produced across the workflow.

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

## Design rule

Bioinformatics and ML stages remain deterministic Python / shell scripts.
The agentic layer does not replace the scientific code with chat output.
It wraps each stage with subordinate validation/review/report agents and a single controlling main agent.
