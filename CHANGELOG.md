# Changelog
All notable changes to this project will be documented in this file.

This project follows Semantic Versioning:
- MAJOR: breaking changes to inputs/outputs or workflow
- MINOR: new functionality, backward compatible
- PATCH: bug fixes and docs updates

## [1.0.0] - 2026-01-31
### Added
- Stage status UI now shows configured inputs/outputs and file existence.
- Cluster-level aggregation helper for cellSNP outputs.
- Pre-flight checklist in README.

### Changed
- Stage runner scripts fixed for correct invocation and WSL compatibility.
- STARsolo runner resolves config paths, uses Linux tmp dir, and indexes BAMs.
- Active variant-calling stage is now GATK-based and imports or reproduces the canonical RNA calling workflow.
- Config defaults tuned for test runs (see `config/ml_config.json`) and STARsolo (`readFilesCommand`, barcode length).
- Enforced LF line endings for scripts and configs via `.gitattributes`.
- Documentation updated for reference setup and WSL STAR index location.

### Fixed
- Broken stage scripts that referenced empty commands/paths.
- Path resolution issues when running from non-repo directories.
- STARsolo failures on NTFS FIFO paths (WSL).
