# Agentic Workflow Review

This document is the review version of the current repository workflow.
It is meant to be read inside VS Code / Cursor / Claude Code / Codex so you can point to the exact place that should change.

## 1. Canonical Agentic Control Loop

```mermaid
flowchart TD
    U["User opens repo in VS Code / Cursor / Claude Code / Codex"] --> M["Main agent starts<br/>scripts/run_agentic_pipeline.py"]
    M --> L1["Load stage order<br/>01_input_data -> ... -> 12_integrated_interpretation"]

    subgraph LOOP["Per-stage agentic loop (applies to every stage 01..12)"]
        A["Main agent reads stage contract<br/>inputs, tools, outputs, review focus, report focus"]
        B["Subordinate preflight agent or skill<br/>check inputs, config, tools, paths"]
        C{"Preflight PASS?"}
        D["Subordinate execution agent or skill<br/>run deterministic stage script"]
        E{"Execution PASS?"}
        F["Subordinate review agent or skill<br/>check outputs, expected files, tables, metrics"]
        G{"Review PASS?"}
        H["Subordinate report agent or skill<br/>write mini_report.md + JSON artifacts"]
        I["Main agent decision<br/>advance or stop"]
        J["Main agent<br/>move to next stage"]
        K["Stop and mark error<br/>manual fix / rerun needed"]

        A --> B --> C
        C -- No --> K
        C -- Yes --> D --> E
        E -- No --> K
        E -- Yes --> F --> G
        G -- No --> K
        G -- Yes --> H --> I
        I -- Yes --> J
        I -- No --> K
    end

    J --> Z{"Last stage reached?"}
    Z -- No --> A
    Z -- Yes --> R["Main agent finalization<br/>generate final integrated report,<br/>final interpretation,<br/>bundle manifest, figures, tables"]
```

## 2. Detailed Legacy `01..12` Data Flow

```mermaid
flowchart TD
    FASTQ["data/fastq/<br/>raw FASTQ files"]
    META["data/metadata/metadata.tsv<br/>raw metadata"]
    REF["config/ref/<br/>genome.fa, genes.gtf,<br/>STAR_index, whitelist.txt"]
    CLMAP["data/metadata/cell_cluster_map.tsv"]

    S01["01_input_data<br/>validate FASTQ naming,<br/>validate metadata,<br/>write cleaned metadata"]
    O01["data/metadata/metadata.cleaned.tsv"]

    S02["02_starsolo<br/>STARsolo alignment,<br/>barcode-aware BAMs,<br/>alignment artifacts"]
    O02["02_starsolo/outputs/artifacts/<br/>BAM, Solo.out, barcode-aware outputs"]

    S03["03_gatk_call<br/>SplitNCigarReads,<br/>HaplotypeCaller,<br/>filter PASS variants"]
    O03["03_gatk_call/outputs/artifacts/<br/>filtered per-sample VCFs"]

    S04["04_cohort_filter<br/>build cohort.common.vcf<br/>using min_samples + min_vaf"]
    O04["04_cohort_filter/outputs/artifacts/<br/>cohort.common.vcf"]

    S05["05_variant_to_gene<br/>map cohort variants to genes<br/>using genes.gtf"]
    O05["05_variant_to_gene/outputs/artifacts/<br/>variant_gene_long.tsv"]

    S06["06_gene_burden<br/>build gene x sample<br/>burden matrix"]
    O06["06_gene_burden/outputs/artifacts/<br/>gene_burden_matrix.tsv"]

    S07["07_ml_control_vs_disease<br/>logistic regression + CV + permutation"]
    O07["07_ml_control_vs_disease/outputs/metrics/<br/>ML metrics + permutation outputs"]

    S08["08_cellsnp<br/>cellsnp-lite per-cell allele counting<br/>using BAM + cohort VCF"]
    O08["08_cellsnp/outputs/artifacts/<br/>per-sample cellSNP directories"]

    S09["09_cluster_aggregation<br/>aggregate allele counts by cluster"]
    O09["09_cluster_aggregation/outputs/artifacts/<br/>cluster mutation tables"]

    S10["10_mutational_analysis<br/>sample-level mutation burden,<br/>SNV/indel counts, signatures"]
    O10["10_mutational_analysis/outputs/metrics/<br/>mutation_burden.tsv,<br/>mutation_signatures.tsv,<br/>driver/pathway placeholders"]

    S11["11_correlation<br/>primary integrative stage:<br/>gene burden + mutation burden + signatures +<br/>cluster mutation summaries + optional STARsolo summaries + metadata<br/>goal: quantify mutation-expression associations"]
    O11["11_correlation/outputs/<br/>sample_integration.tsv,<br/>correlation_matrix.tsv,<br/>correlation_pairs.tsv,<br/>condition_summary.tsv,<br/>integration_notes.md,<br/>plots"]

    S12["12_integrated_interpretation<br/>collect reproducibility outputs,<br/>copy report bundle,<br/>write final agentic report,<br/>compare mutation-expression patterns with literature"]
    O12["for_report/<br/>figures, tables, agentic stage reports,<br/>agentic_final_report.md,<br/>agentic_stage_manifest.tsv"]

    FASTQ --> S01
    META --> S01
    S01 --> O01

    FASTQ --> S02
    O01 --> S02
    REF --> S02
    S02 --> O02

    O02 --> S03
    REF --> S03
    S03 --> O03

    O03 --> S04
    S04 --> O04

    O04 --> S05
    REF --> S05
    S05 --> O05

    O05 --> S06
    O03 --> S06
    S06 --> O06

    O06 --> S07
    O01 --> S07
    S07 --> O07

    O02 --> S08
    O04 --> S08
    REF --> S08
    S08 --> O08

    O08 --> S09
    CLMAP --> S09
    S09 --> O09

    O03 --> S10
    S10 --> O10

    O06 --> S11
    O10 --> S11
    O09 --> S11
    O02 --> S11
    O01 --> S11
    S11 --> O11

    O07 --> S12
    O11 --> S12
    O10 --> S12
    O09 --> S12
    S12 --> O12
```

## 3. Stage Registry

The stage pattern is always:

- `main_agent` assigns the stage
- `stage_preflight_agent` validates readiness
- `stage_execution_agent` runs the script
- `stage_review_agent` validates outputs
- `stage_report_agent` writes the mini report
- `main_agent` decides whether to advance

| Stage | Deterministic execution target | What review must confirm | Why the stage exists |
| --- | --- | --- | --- |
| `01_input_data` | validate FASTQ naming and metadata consistency | cleaned metadata exists and sample IDs are aligned | prevent contamination of every downstream step |
| `02_starsolo` | build alignment and barcode-aware STARsolo outputs | expected alignment artifacts exist for downstream mutation and single-cell analysis | create the expression-aware backbone |
| `03_gatk_call` | produce filtered expressed-variant calls per sample | filtered VCFs exist and are ready for cohort filtering and mutation summaries | convert aligned RNA reads into variant evidence |
| `04_cohort_filter` | derive the cohort-common variant set | cohort-common VCF exists and is non-empty | reduce sample-level calls to a shared mutation space |
| `05_variant_to_gene` | annotate cohort-common variants to genes | long-format variant-to-gene table exists | connect mutations to biological feature units |
| `06_gene_burden` | build the gene-by-sample burden matrix | matrix has gene rows and sample columns | create the feature space for statistics and modeling |
| `07_ml_control_vs_disease` | run classification and permutation testing | metrics and permutation outputs exist and are interpretable | test whether mutation-derived gene features separate groups |
| `08_cellsnp` | compute per-cell allele counts for cohort-common sites | per-sample cellsnp outputs exist | restore single-cell mutation evidence |
| `09_cluster_aggregation` | aggregate cellsnp outputs to clusters | cluster-level mutation summary tables exist | connect mutation burden to cellular structure |
| `10_mutational_analysis` | summarize sample-level mutation burden and signatures | burden and signature tables exist and are non-empty | characterize mutation load before integration |
| `11_correlation` | integrate mutation burden, signatures, cluster summaries, and expression-linked summaries | correlation outputs support mutation-expression association analysis | perform the main scientific integration step |
| `12_integrated_interpretation` | assemble report bundle and final narrative | final bundle is complete and ready for reproducibility review | compare observed mutation-expression relationships with published work |

## 4. Interpretation Priority

- `01..10` are enabling stages.
- `11_correlation` is the main inferential stage.
- `12_integrated_interpretation` must not just copy files. It must explain whether the observed mutation-linked signals are associated with expression-linked signals and how that compares with other studies.

The final workflow should answer:

1. Do mutation burden or mutation signatures track expression-linked sample differences?
2. Do cluster-level mutation summaries align with cluster marker programs or cell-type structure?
3. Are the observed associations strong, weak, or inconsistent?
4. Are they compatible with published studies on scRNA-seq variant analysis, wound biology, and mutation-associated transcriptional change?
5. Is the claim only correlation, or is there evidence strong enough to discuss candidate mutation-associated influence on expression?

## 5. Agentic Artifacts Written For Every Stage

```mermaid
flowchart LR
    S["Any stage 01..12"] --> P["outputs/agentic/<stage>.preflight.json"]
    S --> E["outputs/agentic/<stage>.execution.json"]
    S --> R["outputs/agentic/<stage>.review.json"]
    S --> M["outputs/agentic/<stage>.mini_report.md"]
    S --> J["outputs/agentic/<stage>.mini_report.json"]
    S --> D["outputs/agentic/<stage>.main_agent_decision.json"]
```

## 6. Current Interpretation Of The Repo

- The repo is now modeled as one legacy `01..12` canonical pipeline with one controlling `main_agent`.
- The scientific computations still live inside deterministic scripts.
- Subordinate agents or skills handle stage-local validation, execution, review, and mini-report generation.
- The `main_agent` decides whether a stage is ready to run, whether the workflow may advance, and generates the final integrated output bundle.
- The main scientific endpoint is not Stage `07` ML in isolation. It is the mutation-expression integration produced in Stage `11` and interpreted in Stage `12`.
- The place where you are most likely to request structural changes is either:
  - stage order
  - stage dependencies
  - stage outputs
  - agent roles
  - what should count as PASS/FAIL per stage
  - what must be included in the final report bundle
