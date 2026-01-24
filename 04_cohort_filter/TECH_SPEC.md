# AI Tech Spec: 04_cohort_filter

Objective
- Execute Cohort-common filter and produce the expected outputs.

Entry
- Working directory: $(System.Collections.Hashtable.id)
- Required inputs: filtered VCF (all samples)

Prerequisites
- bcftools
- tabix

Actions
1) Validate inputs exist and are non-empty.
2) Run the stage script(s) under scripts/.
3) Write outputs to outputs/metrics/ and outputs/artifacts/ as appropriate.

Outputs
- cohort VCF
- All outputs stored under outputs/.

Exit criteria
- Outputs exist and pass basic sanity checks (non-empty, expected columns where applicable).

Next stage
- Proceed to $(System.Collections.Hashtable.next).

