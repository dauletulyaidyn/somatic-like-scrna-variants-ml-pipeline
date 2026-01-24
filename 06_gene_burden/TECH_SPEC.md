# AI Tech Spec: 06_gene_burden

Objective
- Execute Somatic-like gene-burden features and produce the expected outputs.

Entry
- Working directory: $(System.Collections.Hashtable.id)
- Required inputs: long TSV

Prerequisites
- Python 3.10+
- pandas
- numpy

Actions
1) Validate inputs exist and are non-empty.
2) Run the stage script(s) under scripts/.
3) Write outputs to outputs/metrics/ and outputs/artifacts/ as appropriate.

Outputs
- gene-burden matrix (TSV/CSV)
- All outputs stored under outputs/.

Exit criteria
- Outputs exist and pass basic sanity checks (non-empty, expected columns where applicable).

Next stage
- Proceed to $(System.Collections.Hashtable.next).

