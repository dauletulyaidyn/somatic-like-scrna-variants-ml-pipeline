# Changelog

## 0.9.0-beta.3 - 2026-03-23

Scope
- repository hygiene and documented contribution/release workflow

Major changes
- added `CONTRIBUTING.md` with the standard branch, commit, merge, and cleanup workflow
- added `docs/RELEASE_WORKFLOW.md` to document the repository release routine
- linked contribution and release workflow documentation from `README.md`

## 0.9.0-beta.2 - 2026-03-22

Scope
- first versioned GATK-based autonomous pipeline beta

Major changes
- replaced active `bcftools` stage with `03_gatk_call`
- added one-command autonomous runner with Flask status UI
- added WSL-aware execution path for Windows
- updated workflow to integrated expression, mutational analysis, and correlation structure
- added public smoke-test profile and validation notes

Stability fixes
- fixed broken stage wrapper scripts and GATK stage orchestration
- fixed status DB initialization and reset behavior
- fixed sample-id normalization in downstream stages
- fixed cellsnp output directory and sample barcode handling
- fixed cluster aggregation helper path and sample matching

Validation status
- public smoke-test completed end-to-end on a small ENA 10x dataset
- recommended release label: `working beta`, not yet production-certified
