# Changelog

All notable changes to this project are documented here. The project follows Semantic Versioning.

## [1.1.0] - 2026-09-04

### Added

- Group-aware GSM leave-one-group-out validation and exact grouped permutation testing.
- Training-only recurrent-locus sensitivity analysis to audit feature-selection leakage.
- Three-design model benchmarking for mutation-derived, expression, and combined feature spaces.
- Main-agent orchestration, stage review artifacts, watchdog support, and improved Flask monitoring.
- Russian end-to-end usage guide with full-cohort and lightweight paired-FASTQ smoke workflows.

### Fixed

- STARsolo no longer receives duplicate `--outTmpDir` arguments.
- STARsolo outputs are written under the correct per-sample directory.
- Stage 02 now rejects missing or empty BAM, BAI, matrix, barcode, or feature artifacts.
- Stages 03 and 08 preserve the SRR sample identifier for nested STARsolo BAM files.
- Stage 04 reads only final `*.filtered.vcf` files and no longer counts intermediate VCFs as additional samples.

### Known limitations

- Classification and correlation are not statistically defined for a one-sample smoke dataset.
- The current final collector does not yet generate standalone Materials and Methods HTML and Results HTML.
- External cohort validation remains required before clinical or biomarker claims.

## [1.0.0] - 2026-01-31

### Added

- Twelve-stage expression and RNA-derived variant workflow.
- Stage status UI, cluster-level cellSNP aggregation, and preflight documentation.

### Fixed

- Initial WSL invocation, path resolution, and STARsolo temporary-directory handling.
