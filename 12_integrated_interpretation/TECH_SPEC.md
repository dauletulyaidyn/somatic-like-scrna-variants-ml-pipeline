# AI Tech Spec: 12_integrated_interpretation

Objective
- Execute Integrated interpretation and produce the expected outputs.

Entry
- Working directory: $(System.Collections.Hashtable.id)
- Required inputs: ML metrics + correlation results

Prerequisites
- Python 3.10+
- pandas

Actions
1) Validate inputs exist and are non-empty.
2) Run the stage script(s) under scripts/.
3) Write outputs to outputs/metrics/ and outputs/artifacts/ as appropriate.

Outputs
- final conclusions/figures
- All outputs stored under outputs/.

Exit criteria
- Outputs exist and pass basic sanity checks (non-empty, expected columns where applicable).

Next stage
- Proceed to $(System.Collections.Hashtable.next).

