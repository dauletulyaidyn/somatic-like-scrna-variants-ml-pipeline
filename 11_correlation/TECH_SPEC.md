# AI Tech Spec: 11_correlation

Objective
- Execute Correlation with mutational analysis and produce the expected outputs.

Entry
- Working directory: $(System.Collections.Hashtable.id)
- Required inputs: gene-burden + cluster counts + mutational outputs

Prerequisites
- Python 3.10+
- pandas
- numpy
- scipy

Actions
1) Validate inputs exist and are non-empty.
2) Run the stage script(s) under scripts/.
3) Write outputs to outputs/metrics/ and outputs/artifacts/ as appropriate.

Outputs
- correlation/enrichment stats (TSV) + FDR
- All outputs stored under outputs/.

Exit criteria
- Outputs exist and pass basic sanity checks (non-empty, expected columns where applicable).

Next stage
- Proceed to $(System.Collections.Hashtable.next).

