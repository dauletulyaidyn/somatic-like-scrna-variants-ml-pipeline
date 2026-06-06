# AI Tech Spec: 11_correlation

Objective
- Treat this as the main integrative scientific stage of the workflow.
- Build an integrated sample-level expression-mutation summary using gene burden, mutational burden, mutational signatures, optional cluster-level burden, optional STARsolo-derived sample metrics, and metadata.
- The downstream expectation is that Stage 12 will compare the observed mutation-expression relationships with published studies, so Stage 11 must produce outputs that support that interpretation.

Entry
- Working directory: `11_correlation`
- Required inputs:
  - Gene-burden matrix from `06_gene_burden/outputs/artifacts/`
  - Mutational analysis outputs from `10_mutational_analysis/outputs/metrics/`
- Optional inputs:
  - Cluster counts from `09_cluster_aggregation/outputs/artifacts/`
  - STARsolo outputs from `02_starsolo/outputs/artifacts/`
  - Metadata from `data/metadata/metadata.cleaned.tsv`

Prerequisites
- Python 3.10+
- pandas
- numpy
- scipy

OS check
- Windows: require WSL2; execute all commands inside WSL.
- macOS/Linux: run natively.

Actions
1) Verify all inputs exist.
2) Ensure `config/correlation_config.json` is filled.
3) Build integrated per-sample metrics across burden / signatures / cluster burden / optional STARsolo and metadata layers.
4) Compute pairwise Spearman correlations and FDR.
5) Highlight which mutation-derived quantities most strongly associate with expression-linked quantities.
6) Save outputs under `outputs/`.

Outputs
- Integrated sample table.
- Correlation matrix + pairwise correlation table + FDR.
- Condition-level summary table.
- Integration notes and plots.

Exit criteria
- Integrated sample table and correlation outputs exist and are non-empty.
- The outputs are interpretable enough for final comparison with external studies on mutation-associated transcriptional change.

Next stage
- Proceed to `12_integrated_interpretation`.
