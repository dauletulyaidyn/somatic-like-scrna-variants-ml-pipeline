## Gene sets for pathway enrichment

Stage `10_mutational_analysis` runs over-representation analysis (ORA) against one or more local `.gmt` files.

Notes
- `.gmt` is a tab-delimited format: `TERM<TAB>DESCRIPTION<TAB>GENE1<TAB>GENE2...`
- Gene identifiers are expected to be HGNC-style gene symbols (matching `gene_name` in `06_gene_burden` output).
- Replace `example_pathways.gmt` with a real pathway collection (Reactome/KEGG/GO, etc.) and update
  `config/mutational_analysis_config.json` (`gene_sets_gmt`) to point to it.

