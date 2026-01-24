# 08_cellsnp: cellsnp-lite

Purpose
- cellsnp-lite.

Inputs
- CB/UB BAM + barcodes + VCF

Outputs
- per-cell AD/DP matrices (MTX) + variants.tsv
- Stage outputs are stored in outputs/ (metrics and artifacts).

How to run (manual)
1) Review input paths and references.
2) Run the stage script(s) in scripts/.
3) Confirm outputs are created in outputs/.

Success criteria
- Expected outputs are produced and non-empty.

Next stage
- Proceed to $(System.Collections.Hashtable.next).
