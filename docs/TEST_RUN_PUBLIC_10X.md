# Public Test Run

This repository now includes a small isolated smoke-test profile under `config/test_run/` and `data/test_run/`.

Selected ENA public dataset
- Study: `PRJNA713808`
- Organism: `Mus musculus`
- Protocol: 10x scRNA-seq
- Runs:
  - `SRR13942350` control
  - `SRR13942411` control
  - `SRR13942654` disease
  - `SRR13942615` disease

Notes
- This test profile is separate from the default manuscript-oriented human configuration.
- Mouse reference files are expected under `config/test_run/ref_mouse/`.
- Later correlation stages also require `data/test_run/cell_barcodes.txt` and `data/test_run/cell_cluster_map.tsv`, which are generated after alignment for the smoke test.
