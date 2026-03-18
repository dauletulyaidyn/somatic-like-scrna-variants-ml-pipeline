# UMAP overview (4 panels) — explanation

## Top-left: Leiden Clusters
- Each point is a **cell** embedded into 2D (UMAP1/UMAP2) based on expression features.
- Colors/labels are **Leiden cluster IDs** (0–37). These are algorithmic IDs, not biological names by default.
- To attach human-readable names, you need marker features; this script exports a first-pass mapping.

## Top-right: Sample ID
- Same UMAP coordinates, but colored by **sample (SRR)**.
- Interpretation:
  - **Good mixing** (many colors within the same region) suggests batch integration worked.
  - **Separated islands dominated by one color** suggests sample/batch effects.
- With 14 samples, a single legend is hard to read; a clearer plot is WE vs UWE (2 colors) or faceting.

## Bottom-left: Condition
- Should show WE vs UWE (2 categories).
- In the current `clustered_adata.h5ad`, `condition` is constant (`control`), so this panel is not informative.

## Bottom-right: N genes
- QC metric: number of detected genes per cell (`n_genes`).
- Low values: low-quality/low-complexity cells.
- Very high values: can indicate high complexity or potential doublets.

## Outputs
- Cluster names table: `cluster_marker_names.csv`

