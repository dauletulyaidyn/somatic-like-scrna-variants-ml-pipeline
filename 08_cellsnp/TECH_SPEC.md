# AI Tech Spec: 08_cellsnp

Objective
- Execute cellsnp-lite and produce the expected outputs.

Entry
- Working directory: $(System.Collections.Hashtable.id)
- Required inputs: CB/UB BAM + barcodes + VCF

Prerequisites
- cellsnp-lite
- samtools
- tabix

Actions
1) Validate inputs exist and are non-empty.
2) Run the stage script(s) under scripts/.
3) Write outputs to outputs/metrics/ and outputs/artifacts/ as appropriate.

Outputs
- per-cell AD/DP matrices (MTX) + variants.tsv
- All outputs stored under outputs/.

Exit criteria
- Outputs exist and pass basic sanity checks (non-empty, expected columns where applicable).

Next stage
- Proceed to $(System.Collections.Hashtable.next).

