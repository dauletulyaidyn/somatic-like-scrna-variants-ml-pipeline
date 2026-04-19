# Agentic Workflow Review

This document is the review version of the current repository workflow.
It is meant to be read inside VS Code / Cursor / Claude Code / Codex so you can point to the exact place that should change.

## 1. Canonical Agentic Control Loop

```mermaid
flowchart TD
    U["User opens repo in VS Code / Cursor / Claude Code / Codex"] --> M["Main agent starts<br/>scripts/run_agentic_pipeline.py"]
    M --> L1["Load stage order<br/>01_input_data -> ... -> 12_integrated_interpretation"]

    subgraph LOOP["Per-stage agentic loop (applies to every stage 01..12)"]
        A["Read stage contract<br/>inputs, tools, outputs, review focus"]
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

    S11["11_correlation<br/>integrated sample-level expression/mutation layer:<br/>gene burden + mutation burden + signatures +<br/>optional cluster burden + optional STARsolo cell counts + metadata"]
    O11["11_correlation/outputs/<br/>sample_integration.tsv,<br/>correlation_matrix.tsv,<br/>correlation_pairs.tsv,<br/>condition_summary.tsv,<br/>integration_notes.md,<br/>plots"]

    S12["12_integrated_interpretation<br/>collect manuscript-facing outputs,<br/>copy report bundle,<br/>write final agentic report"]
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

## 3. What Each Stage Means

- `01_input_data`: checks whether the raw dataset is even runnable. If this stage is wrong, every downstream stage is contaminated.
- `02_starsolo`: creates the alignment backbone and barcode-aware outputs needed by both the mutation branch and the per-cell branch.
- `03_gatk_call`: converts aligned RNA-seq reads into filtered per-sample expressed variant calls.
- `04_cohort_filter`: reduces the sample-level variant space into a cohort-common mutation set.
- `05_variant_to_gene`: links the cohort-common variants to gene intervals.
- `06_gene_burden`: converts variant-to-gene links into a feature matrix for downstream statistics and ML.
- `07_ml_control_vs_disease`: tests whether the burden matrix can separate control vs disease.
- `08_cellsnp`: goes back to the single-cell level and counts reference/alternate alleles per cell for the cohort-common sites.
- `09_cluster_aggregation`: converts per-cell allele counts into per-cluster mutation burden summaries.
- `10_mutational_analysis`: produces sample-level mutation burden and simple substitution-signature summaries.
- `11_correlation`: is now the real integration stage, not just a single narrow correlation. It joins burden, mutation, signature, cluster, STARsolo-derived, and metadata-level summaries.
- `12_integrated_interpretation`: packages all manuscript-facing outputs and final agentic reporting artifacts.

## 4. Agentic Artifacts Written For Every Stage

```mermaid
flowchart LR
    S["Any stage 01..12"] --> P["outputs/agentic/<stage>.preflight.json"]
    S --> E["outputs/agentic/<stage>.execution.json"]
    S --> R["outputs/agentic/<stage>.review.json"]
    S --> M["outputs/agentic/<stage>.mini_report.md"]
    S --> J["outputs/agentic/<stage>.mini_report.json"]
    S --> D["outputs/agentic/<stage>.main_agent_decision.json"]
```

## 5. Current Interpretation Of The Repo

- The repo is now modeled as one legacy `01..12` canonical pipeline with one controlling `main_agent`.
- The scientific computations still live inside deterministic scripts.
- Subordinate agents or skills handle stage-local validation, execution, review, and mini-report generation.
- The `main_agent` decides whether a stage is ready to run, whether the workflow may advance, and generates the final integrated output bundle.
- The place where you are most likely to request structural changes is either:
  - stage order
  - stage dependencies
  - stage outputs
  - agent roles
  - what should count as PASS/FAIL per stage
  - what must be included in the final report bundle
