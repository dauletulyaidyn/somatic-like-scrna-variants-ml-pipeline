# 03_bcftools_call Legacy Archive

This archive marker records that the former `03_bcftools_call` stage has been retired from the active pipeline.

Current state
- the active pipeline uses `03_gatk_call`
- downstream configs and autonomous orchestration target the GATK-based stage
- `03_bcftools_call/` is retained in-place only for historical comparison and compatibility with older notes

Do not use `03_bcftools_call` for new analyses.
