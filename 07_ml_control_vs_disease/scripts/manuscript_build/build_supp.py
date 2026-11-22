"""Supplementary Materials (.docx + CSV) for the three revisions."""
import json, shutil, sys
from pathlib import Path
import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.shared import Pt, Cm

sys.path.insert(0, str(Path(__file__).parent))
from results_numbers import RES, load

ART = Path(r"D:\! ! ! Defense Dissertation - State 13.08.2026\! ! ! Final documents ! ! !\0. ----WAIT---- Articles (KBTU, NANRK, Aqtobe)\Articles\FINAL_2026-11-21")
AN = Path(r"V:\! ! ! PAD\Final version\results_GATK_primary_2026-05-30\all_samples_hg38_matched_ref_2026-05-31\ijms_revision_analysis_2026-06-05")
SCRIPTS = Path(r"V:\! ! ! PAD\Final version\repo\07_ml_control_vs_disease\scripts")
N = load()
qc = pd.read_csv(ART / "1_NANRK" / "2_figures" / "per_run_qc_counts.tsv", sep="\t")
manifest = json.loads((RES.parent / "feature_set_three_design_benchmark" / "manifest.json").read_text())


def new_doc(title, subtitle):
    d = Document()
    W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    for z in d.settings.element.iter(W + "zoom"):
        z.set(W + "percent", "100")  # python-docx template omits the required attribute
    st = d.styles["Normal"]; st.font.name = "Times New Roman"; st.font.size = Pt(11)
    st.element.rPr.rFonts.set("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia", "Times New Roman")
    for s in d.sections:
        s.left_margin = s.right_margin = Cm(2); s.top_margin = s.bottom_margin = Cm(2)
    p = d.add_paragraph(); r = p.add_run(title); r.bold = True; r.font.size = Pt(14); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = d.add_paragraph(); r = p.add_run(subtitle); r.italic = True; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return d


def h(d, text):
    p = d.add_paragraph(); r = p.add_run(text); r.bold = True; r.font.size = Pt(12)
    p.paragraph_format.space_before = Pt(10); p.paragraph_format.keep_with_next = True


def para(d, text):
    p = d.add_paragraph(text); p.paragraph_format.space_after = Pt(4); p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def table(d, df, caption, note=None, size=8.5):
    p = d.add_paragraph(); r = p.add_run(caption); r.bold = True; p.paragraph_format.keep_with_next = True
    t = d.add_table(rows=1, cols=len(df.columns)); t.style = "Table Grid"
    for j, c in enumerate(df.columns):
        cell = t.rows[0].cells[j]; cell.text = ""; rr = cell.paragraphs[0].add_run(str(c)); rr.bold = True; rr.font.size = Pt(size)
    for _, row in df.iterrows():
        cells = t.add_row().cells
        for j, v in enumerate(row):
            if isinstance(v, float):
                v = f"{v:.4g}" if abs(v) < 1000 else f"{v:,.0f}"
            elif isinstance(v, (int,)) and not isinstance(v, bool):
                v = f"{v:,}"
            cells[j].text = ""; rr = cells[j].paragraphs[0].add_run("–" if pd.isna(v) or str(v).strip().lower() in ("nan", "none") else str(v)); rr.font.size = Pt(size)
    tr = t.rows[0]._tr; trPr = tr.get_or_add_trPr(); trPr.append(parse_xml(f'<w:tblHeader {nsdecls("w")}/>'))
    if note:
        p = d.add_paragraph(); r = p.add_run(note); r.italic = True; r.font.size = Pt(9)


def copy_csv(dst, names):
    dst.mkdir(parents=True, exist_ok=True)
    for src, out in names:
        df = pd.read_csv(src, sep="\t") if str(src).endswith(".tsv") else pd.read_csv(src)
        df.to_csv(dst / out, index=False)


def copy_scripts(dst):
    dst.mkdir(parents=True, exist_ok=True)
    for f in ["light_00_cache_vcfs.py", "light_01_descriptive.py", "light_02_identity_check.py", "light_03_exact_null.py",
              "light_04_article_figures.py", "light_05_observed_predictions.py", "light_06_new_elements.py", "run_combined_three_design_benchmark.py"]:
        shutil.copy2(SCRIPTS / f, dst / f)


label_note = ("Condition labels were taken from the GEO sample titles of GSE176415: Sc_Skin1–Sc_Skin4 (GSM5364333–GSM5364336) are "
              "unwounded skin and Sc_W1–Sc_W3 (GSM5364337–GSM5364339) are wound edge. Each sample corresponds to two SRA runs. "
              "The labels used in the earlier analysis (WE for SRR14762238–SRR14762245 and UWE for SRR14762246–SRR14762252) were inverted "
              "relative to GEO for all 14 runs. All results in the revised manuscript were recomputed from the PASS VCF files with the GEO labels.")
software = ("STAR 2.7.10a (STARsolo, CB_UMI_Simple, GRCh38 primary assembly, GENCODE release 43); GATK 4.6.2.0: AddOrReplaceReadGroups, "
            "SplitNCigarReads, HaplotypeCaller (--dont-use-soft-clipped-bases true, --standard-min-confidence-threshold-for-calling 20), "
            "VariantFiltration (QD < 2.0, FS > 30.0, MQ < 40.0, SOR > 3.0), SelectVariants (--exclude-filtered). Recurrent loci: support ≥ 4 runs "
            "and maximum VAF ≥ 0.05 (VAF from FORMAT AD). Machine learning: Python 3, scikit-learn 1.9.0, XGBoost 3.2.0, NumPy 2.4.6; "
            "descriptive analyses: Python 3.14, NumPy 2.4.0, pandas 2.3.3, SciPy 1.16.3. Random seed 42 for all models and permutations. "
            f"Input hashes (SHA-256): combined feature matrix {manifest['inputs']['combined_matrix_sha256']}; metadata {manifest['inputs']['metadata_sha256']}; "
            f"variant-to-gene table {manifest['inputs']['variant_gene_tsv_sha256']}.")
identity_note = ("Genotype concordance was computed on loci called in both runs with FORMAT DP ≥ 10 or ≥ 20 in both; the genotype class is "
                 "heterozygous or homozygous alternative. Runs of Sc_Skin1 (GSM5364333) and Sc_W2 (GSM5364338) reach the concordance of "
                 "within-sample run pairs; both samples are listed in the metadata as male, 69 years. They are therefore treated as one individual "
                 "in person-level validation (six folds).")

tab_runs = qc[["sample_id", "gsm", "title", "condition", "raw", "pass", "nonpass", "HighSOR", "LowQD", "HighFS", "cohort_recurrent"]].copy()
tab_runs.insert(4, "label_previous_version", ["WE" if c == "unwounded" else "UWE" for c in tab_runs.condition])
tab_runs.columns = ["SRA run", "GEO sample", "Title", "Label (GEO)", "Label (previous)", "Raw", "PASS", "Non-PASS", "HighSOR", "LowQD", "HighFS", "Recurrent ≥4"]
don = N["donor"].reset_index()[["measure", "within", "between_same", "between_diff", "nn_donor_id_acc", "p_donor_perm", "p_condition_exact"]]
don.columns = ["Measure", "Same sample", "Diff. samples, same cond.", "Diff. samples, diff. cond.", "1-NN identification", "Sample effect p (10,000 perm.)", "Condition effect exact p (35)"]
idt = N["ident"].copy()
idt = idt[["min_dp", "donor_pair", "same_gsm", "n_shared_hc", "gt_concordance_hc", "jaccard_hc"]].sort_values(["min_dp", "gt_concordance_hc"], ascending=[True, False])
idt.columns = ["Min. DP", "Sample pair", "Same GSM", "Shared loci (mean)", "Genotype concordance", "Jaccard"]
nul = N["null"].reset_index()[["design", "model", "ba", "p_ba", "auc", "p_auc", "null_ba", "null_auc"]]
nul.columns = ["Design", "Model", "Observed BA", "Exact p (BA)", "Observed ROC-AUC", "Exact p (AUC)", "Null mean BA", "Null mean AUC"]
folds = N["folds"]
sweep = N["sweep"][["min_support_runs", "n_loci", "n_genes", "pct_snp", "median_loci_per_run", "within", "between_same", "between_diff", "nn_donor_id_acc", "p_condition_exact"]].copy()
sweep.columns = ["k", "Loci", "Genes", "SNV %", "Median loci per run", "Jaccard same sample", "Jaccard diff., same cond.", "Jaccard diff., diff. cond.", "1-NN identification", "Condition exact p"]
cov = N["cov"]
rt = N["rt"]
obs = pd.read_csv(RES / "F_observed_sample_predictions.tsv", sep="\t")
brier = pd.read_csv(RES / "H_brier_exact_summary.tsv", sep="\t")
brier = brier[brier.model != "Elastic-net logistic regression"][["design", "model", "observed_brier", "exact_p_brier", "null_brier_mean", "observed_BA", "observed_AUC"]]
brier.columns = ["Design", "Model", "Brier score", "Exact p (Brier)", "Null mean Brier", "Observed BA", "Observed ROC-AUC"]
ndep = pd.read_csv(RES / "I_norm_coverage_dependence.tsv", sep="\t")
ndep.columns = ["Features", "ρ total burden vs median DP", "ρ total burden vs detected genes", "Median |ρ| gene vs DP", "Share genes |ρ| ≥ 0.5", "1-NN sample identification"]
nexa = pd.read_csv(RES / "I_norm_exact_summary.tsv", sep="\t")[["design", "observed_BA", "exact_p_BA", "observed_AUC", "exact_p_AUC", "null_BA_mean"]]
nexa.columns = ["Design (logistic regression)", "Observed BA", "Exact p (BA)", "Observed ROC-AUC", "Exact p (AUC)", "Null mean BA"]

# ---------------- KBTU (anonymous)
d = new_doc("Supplementary Materials", "Sample identity as a source of data leakage in machine learning on scRNA-seq expressed-variant features (revision 2)")
h(d, "Note S1. Correction of condition labels"); para(d, label_note)
h(d, "Note S2. Software, parameters and input hashes"); para(d, software); para(d, identity_note)
table(d, tab_runs, "Table S1. Runs, GEO samples, labels and call counts", "Recurrent: loci of the run that belong to the global recurrent set (support ≥ 4 runs, max VAF ≥ 0.05). Filter flags may overlap.", size=7.5)
table(d, don, "Table S2. Similarity by pair class (14 runs, 91 pairs)")
table(d, idt[idt["Min. DP"] == 20], "Table S3. Genotype identity audit at DP ≥ 20 (all 28 sample pairs; mean over run pairs)", "DP ≥ 10 values are in KBTU_S3_identity_pairs.csv.", size=8)
table(d, nul, "Table S4. Exact-null summary for all designs and models (35 labelings)", "GSM-LOGO: 7 folds; Person-LOGO: 6 folds with GSM5364333 and GSM5364338 held out together.", size=7.5)
table(d, folds, "Table S5. Training-only feature counts per fold")
table(d, brier, "Table S6. Brier score of sample-level probabilities with exact p over 35 labelings", "Brier = mean squared difference between the sample-level wound probability and the label; a constant prediction of 0.5 gives 0.250. Exact p = share of labelings with Brier at most the observed value.", size=7.5)
h(d, "CSV files")
para(d, "KBTU_S1_runs.csv; KBTU_S2_pairwise_similarity.csv (91 run pairs × 4 measures); KBTU_S3_identity_pairs.csv (91 run pairs at DP ≥ 10 and ≥ 20); "
        "KBTU_S4_exact_null_all_labelings.csv (35 labelings × 4 designs × 6 models); KBTU_S4b_observed_sample_predictions.csv and KBTU_S4c_observed_run_predictions.csv "
        "(held-out probabilities under the GEO labeling); KBTU_S5_fold_feature_counts.csv; KBTU_S6_brier_summary.csv. Analysis scripts are in the folder scripts/.")
out = ART / "2_KBTU" / "4_supplementary"; out.mkdir(parents=True, exist_ok=True)
d.save(out / "KBTU_rev2_Supplementary_Materials.docx")
tab_runs.to_csv(out / "KBTU_S1_runs.csv", index=False)
copy_csv(out, [(RES / "A_pairwise_similarity.tsv", "KBTU_S2_pairwise_similarity.csv"), (RES / "E_identity_check_pairs.tsv", "KBTU_S3_identity_pairs.csv"),
               (RES / "F_exact_null_all_labelings.tsv", "KBTU_S4_exact_null_all_labelings.csv"), (RES / "F_observed_sample_predictions.tsv", "KBTU_S4b_observed_sample_predictions.csv"),
               (RES / "F_observed_run_predictions.tsv", "KBTU_S4c_observed_run_predictions.csv"), (RES / "F_training_only_fold_counts.tsv", "KBTU_S5_fold_feature_counts.csv")])
brier.to_csv(out / "KBTU_S6_brier_summary.csv", index=False)
copy_scripts(out / "scripts")

# ---------------- NAN RK
d = new_doc("Supplementary Materials", "A reproducible GATK-based feature-engineering pipeline for machine learning on single-cell RNA-seq expressed variants (revision 6)")
h(d, "Note S1. Label reconciliation"); para(d, label_note)
h(d, "Note S2. Software, parameters and input hashes"); para(d, software); para(d, identity_note)
para(d, "The pipeline's cohort VCF contains 882,138 recurrent loci; the independent re-implementation used for the audit (light_01) gives 883,831 (difference 0.19%, caused by the handling of multi-allelic records). All audit statistics use the re-implementation.")
table(d, tab_runs, "Table S1. Per-run call counts and hard-filter flags", "Filter flags may overlap; Non-PASS = records failing at least one filter.", size=7.5)
per = N["per"][["sample_id", "title", "condition", "n_pass", "n_snp", "n_indel", "pct_hom_alt", "median_dp", "mean_dp", "pct_dp_ge10", "bam_gb", "expr_total_counts", "detected_genes"]]
table(d, per, "Table S2a. Coverage proxies per run", "BAM of SRR14762241 was not archived (missing).", size=7.5)
table(d, cov, "Table S2b. Spearman correlations of PASS calls with coverage proxies")
table(d, sweep, "Table S3. Recurrence-threshold sweep (max VAF ≥ 0.05)", "Gene counts for k < 4 are capped because the variant-to-gene table covers recurrent loci (k ≥ 4) only.", size=7.5)
rtt = rt[["sample_id", "AddOrReplaceReadGroups_elapsed_min", "SplitNCigarReads_elapsed_min", "HaplotypeCaller_elapsed_min", "VariantFiltration_elapsed_min", "SelectVariants_elapsed_min", "total_min", "bam_gb", "resume_used"]].copy()
rtt.columns = ["Run", "ReadGroups, min", "SplitNCigar, min", "HaplotypeCaller, min", "Filtration, min", "Select, min", "Total, min", "BAM, GB", "Resumed"]
table(d, rtt, "Table S4. GATK wall-clock time per run and step", size=7.5)
table(d, nul, "Table S5a. Exact-null summary (35 labelings)", size=7.5)
o2 = obs.copy(); o2.columns = ["Design", "Model", "GEO sample", "True label (1 = wound)", "Mean P(wound)", "Predicted label"]
table(d, ndep, "Table S6a. Raw and coverage-normalised gene burden: dependence on depth and sample identification", "Normalised burden = burden / PASS calls of the run × 10⁵.", size=8)
table(d, nexa, "Table S6b. Logistic regression on raw and normalised burden, exact p over 35 labelings", size=8)
table(d, o2[o2.Design.str.contains("training-only")], "Table S5b. Held-out sample-level predictions under the GEO labeling (training-only designs)", "All designs: NANRK_S5_observed_sample_predictions.csv.", size=7)
out = ART / "1_NANRK" / "4_supplementary"; out.mkdir(parents=True, exist_ok=True)
d.save(out / "NANRK_rev6_Supplementary_Materials.docx")
tab_runs.to_csv(out / "NANRK_S1_runs_and_filters.csv", index=False)
copy_csv(out, [(RES / "C_per_run_calls_vs_coverage.tsv", "NANRK_S2a_coverage_per_run.csv"), (RES / "C_coverage_correlations.tsv", "NANRK_S2b_coverage_correlations.csv"),
               (RES / "B_cohort_filter_sweep.tsv", "NANRK_S3_threshold_sweep.csv"), (RES / "D_gatk_runtime_per_run.tsv", "NANRK_S4_runtime_per_run.csv"),
               (RES / "F_exact_null_all_labelings.tsv", "NANRK_S5_exact_null_all_labelings.csv"), (RES / "F_observed_sample_predictions.tsv", "NANRK_S5_observed_sample_predictions.csv"),
               (RES / "F_observed_run_predictions.tsv", "NANRK_S5_observed_run_predictions.csv"),
               (RES / "I_norm_coverage_dependence.tsv", "NANRK_S6a_normalised_burden_coverage.csv"), (RES / "I_norm_exact_summary.tsv", "NANRK_S6b_normalised_burden_exact_null.csv")])
copy_scripts(out / "scripts")

# ---------------- ARU (Kazakh/Russian notes)
d = new_doc("Қосымша материалдар / Дополнительные материалы", "Мақала #1319, v9: үлгілердің генотиптік сәйкестігі және дәл пермутациялық тест")
h(d, "S1-ескертпе. Үлгілердің сәйкестігі / Примечание S1. Идентичность образцов")
para(d, "Генотиптік сәйкестік оқылым тереңдігі DP ≥ 10 немесе ≥ 20 болатын ортақ PASS локустарында есептелді (гетерозигота немесе баламалы аллель бойынша гомозигота). Sc_Skin1 (GSM5364333) және Sc_W2 (GSM5364338) жүргізілімдері бір үлгінің жүргізілімдері деңгейінде сәйкес келеді; метадеректер бойынша екеуі де 69 жастағы ер адам. Сондықтан адам бойынша топтастыруда олар бірге шығарылды (6 фолд).")
para(d, "Генотипическое совпадение рассчитано на общих локусах PASS с глубиной DP ≥ 10 или ≥ 20 (гетерозигота или гомозигота по альтернативному аллелю). Прогоны Sc_Skin1 (GSM5364333) и Sc_W2 (GSM5364338) совпадают на уровне прогонов одного образца; по метаданным оба — мужчины 69 лет. При группировке по человеку они исключались вместе (6 фолдов).")
table(d, idt[idt["Min. DP"] == 20], "S1-кесте / Таблица S1. Генотиптік сәйкестік, DP ≥ 20 (28 үлгі жұбы)", size=8)
table(d, nul[~nul.Design.str.contains("expression")], "S2-кесте / Таблица S2. Дәл пермутациялық тест (35 белгілеу)", size=7.5)
o3 = obs[~obs.design.str.contains("expression")].copy(); o3.columns = ["Design", "Model", "GEO sample", "True (1 = wound)", "Mean P(wound)", "Predicted"]
table(d, o3, "S3-кесте / Таблица S3. GEO белгілері бойынша үлгілер деңгейіндегі болжамдар", size=7)
out = ART / "3_ARU" / "4_supplementary"; out.mkdir(parents=True, exist_ok=True)
d.save(out / "ARU_v9_Қосымша_материалдар.docx")
copy_csv(out, [(RES / "E_identity_check_pairs.tsv", "ARU_S1_identity_pairs.csv"), (RES / "F_exact_null_all_labelings.tsv", "ARU_S2_exact_null_all_labelings.csv"),
               (RES / "F_observed_sample_predictions.tsv", "ARU_S3_observed_sample_predictions.csv")])
print("supplements written")
