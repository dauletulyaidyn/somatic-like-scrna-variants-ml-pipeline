# Leakage-audit checklist for scRNA-seq variant-derived ML (small cohorts)

Status refers to this pipeline (PRJNA736095, 14 SRR / 7 GSM), checked on 2026-11-21.

| # | Check | Why it matters | How checked here | Status |
|---|---|---|---|---|
| 1 | Labels come from the primary source (GEO sample titles), not from derived tables | Inverted or shifted labels silently change every result | `metadata.cleaned.tsv` matched to GEO titles: Sc_Skin1–4 unwounded, Sc_W1–3 wound | OK (legacy labels were inverted; corrected) |
| 2 | Unit of independence is defined (run, library, GSM, person) | Runs of one library are technical replicates | 2 SRR per GSM; within-GSM similarity ≫ between-GSM (Section A) | OK |
| 3 | Sample identity verified by genotype, not by metadata alone | Two GSMs from one person leak through GSM-grouped CV | High-depth genotype concordance (Section E) | **FLAG: Sc_Skin1 and Sc_W2 are genotype-identical (0.997 at DP≥20)** |
| 4 | Splits are grouped at the highest identity level | Run-level CV lets the model recognise the donor | GSM-LOGO and person-LOGO (Section F) | OK after fix |
| 5 | Feature selection (recurrent loci) is fitted inside each training fold | Cohort-wide filters use held-out runs | Training-only loci, support ≥ 4, max VAF ≥ 0.05 | OK |
| 6 | Scaling / variance filter fitted inside folds | Classic preprocessing leak | sklearn Pipeline per fold | OK |
| 7 | Grouped predictions aggregated to one score per group | Otherwise paired runs double-count | Run probabilities averaged per GSM | OK |
| 8 | Significance assessed with a group-level permutation null | Run-level permutation is anti-conservative | Exact null over all 35 GSM labelings (Section F) | OK |
| 9 | Attainable p-value resolution reported | With 7 groups the smallest p is 1/35 ≈ 0.029 | Reported | OK |
| 10 | Technical covariates checked against call counts | RNA-seq variant counts track coverage/expression | Spearman vs detected genes / depth (Section C) | OK — strong coverage dependence |
| 11 | Filter thresholds shown as a sensitivity curve, not a single value | One threshold can hide instability | k = 1..14 sweep (Section B) | OK |
| 12 | Per-fold predictions and feature counts released | Lets reviewers recompute every metric | `predictions.tsv`, `F_exact_null_all_labelings.tsv`, fold counts | OK |
| 13 | Input hashes and software versions recorded | Reproducibility | `manifest.json` SHA-256; GATK/STAR versions in VCF headers | Partial: scikit-learn version of original run not recorded |
| 14 | Data-integrity anomalies listed | Silent pipeline errors | Section E | **FLAG: SRR14762241 has no BAM on disk; its expression counts (1,409) are 4× below its pair while its call count matches (608,763 vs 608,759)** |
