# AI Tech Spec: 09_cluster_aggregation

Objective
- Execute Cluster aggregation and produce the expected outputs.

Entry
- Working directory: $(System.Collections.Hashtable.id)
- Required inputs: cellsnp outputs + cell->cluster map

Prerequisites
- Python 3.10+
- numpy
- scipy

Actions
1) Validate inputs exist and are non-empty.
2) Run the stage script(s) under scripts/.
3) Write outputs to outputs/metrics/ and outputs/artifacts/ as appropriate.

Outputs
- per-cluster counts (TSV)
- All outputs stored under outputs/.

Exit criteria
- Outputs exist and pass basic sanity checks (non-empty, expected columns where applicable).

Next stage
- Proceed to $(System.Collections.Hashtable.next).

