# AI Tech Spec: 07_ml_we_vs_uwe

Objective
- Execute ML: WE vs UWE and produce the expected outputs.

Entry
- Working directory: $(System.Collections.Hashtable.id)
- Required inputs: gene-burden matrix + labels

Prerequisites
- Python 3.10+
- pandas
- numpy
- scikit-learn

Actions
1) Validate inputs exist and are non-empty.
2) Run the stage script(s) under scripts/.
3) Write outputs to outputs/metrics/ and outputs/artifacts/ as appropriate.

Outputs
- CV metrics + permutation p-values
- All outputs stored under outputs/.

Exit criteria
- Outputs exist and pass basic sanity checks (non-empty, expected columns where applicable).

Next stage
- Proceed to $(System.Collections.Hashtable.next).

