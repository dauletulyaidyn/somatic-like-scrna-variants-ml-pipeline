"""KBTU Herald #3290, revision 2: rebuild on the GATK call set with GEO labels.
Yellow highlight = text changed or added relative to rev1."""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import docbuild as db
from docbuild import r, f, sub, sup, nary, d
from results_numbers import load, MODELS, SHORT, D_GLOB, D_TRAIN, D_PERS, D_EXPR, fmt, fint

ART = Path(r"D:\! ! ! Defense Dissertation - State 13.08.2026\! ! ! Final documents ! ! !\0. ----WAIT---- Articles (KBTU, NANRK, Aqtobe)\Articles")
SRC = ART / "2_KBTU" / "KBTU_revision_2026-11-17" / "Gene-Burden_PAD_KBTU_rev1.docx"
OUT = ART / "FINAL_2026-11-21" / "2_KBTU"
FIG = OUT / "2_figures"
N = load()
don, idt, nul = N["donor"], N["ident"], N["null"]

def ident(md, which):
    x = idt[idt.min_dp == md]
    if which == "within": x = x[x.same_gsm]
    elif which == "pair": x = x[x.donor_pair == "Sc_Skin1 vs Sc_W2"]
    else: x = x[(~x.same_gsm) & (x.donor_pair != "Sc_Skin1 vs Sc_W2")]
    return x

w10, w20, b10, b20, s10, s20 = ident(10, "within"), ident(20, "within"), ident(10, "b"), ident(20, "b"), ident(10, "pair").iloc[0], ident(20, "pair").iloc[0]
nm = {k: don.loc[k] for k in don.index}
J, GC, GB, EX = (nm["PASS-locus Jaccard"], nm["Genotype concordance (shared loci)"], nm["Gene-burden Spearman (cohort filter)"], nm["Expression Pearson (log1p CPM)"])
condp = [J.p_condition_exact, GC.p_condition_exact, GB.p_condition_exact, EX.p_condition_exact]
tr = nul.loc[D_TRAIN]; gl = nul.loc[D_GLOB]; pe = nul.loc[D_PERS]; ex = nul.loc[D_EXPR]
null_means = list(tr.null_ba) + list(pe.null_ba) + list(gl.null_ba)
pmin_all = min(nul.p_ba)
folds = N["folds"]; gf = folds[folds.design == "GSM-LOGO"]; pf = folds[folds.design == "Person-LOGO"]
pf_pair = pf[pf.heldout == "P_Skin1_W2"].iloc[0]
hi_auc = pe[pe.auc >= 0.8]

br = N["brier"]
bt = br.loc[D_TRAIN].loc[MODELS]; bg = br.loc[D_GLOB].loc[MODELS]; bp = br.loc[D_PERS].loc[MODELS]
bg_low = bg[bg.observed_brier < 0.25]
bp_min = bp[bp.exact_p_brier <= 1 / 35 + 1e-9]
b = db.Builder(SRC)
H = lambda t: b.P(10, "【" + t + "】", hl=True)          # section heading (centered, bold)
Hk = lambda i: b.keep(i)
S = lambda t: b.P(17, "【⟪" + t + "⟫】", hl=True)        # subsection heading
T = lambda t, hl=True: b.P(11, t, hl=hl)                 # body paragraph
CAP = lambda t: b.P(22, t, hl=True)                       # figure caption
TCAP = lambda t: b.P(11, t, hl=True, align="left", ppr_over=None)

# ---------------- front matter
b.keep(0); b.keep(1); b.keep(2)
b.P(3, "【Sample Identity as a Source of Data Leakage in Machine Learning on scRNA-seq Expressed-Variant Features: A Genotype Audit and Exact Permutation Test of Grouped Validation】", hl=True)
b.keep(4); b.keep(5)
T(
 "Machine-learning studies that derive features from expressed variants in single-cell RNA sequencing (scRNA-seq) usually analyse a few biological samples, each sequenced in several runs. This study tests whether such features capture the class label or the individual. "
 f"Fourteen runs from seven GEO samples in two classes (BioProject PRJNA736095; four unwounded-skin and three wound-edge samples, labels taken from GEO) were processed with STARsolo and GATK HaplotypeCaller, giving 9,528,556 distinct PASS calls. "
 "Run-to-run similarity was measured with four label-free measures (locus Jaccard index, genotype concordance, gene-burden correlation and expression correlation); sample identity was audited by genotype concordance at read depth of at least 10 and 20; and six classifiers were evaluated by leave-one-group-out validation against an exact null distribution over all 35 possible group labelings. "
 f"For every measure, the nearest neighbour of each run was the other run of the same GEO sample (14 of 14; permutation p < 0.001), whereas similarity did not differ between same-condition and different-condition pairs (exact p = {min(condp):.2f}–{max(condp):.2f}). "
 f"Genotype concordance identified two samples recorded as different donors (Sc_Skin1 and Sc_W2) as one individual: {s20.gt_concordance_hc:.3f} at depth of at least 20, the same level as runs of one sample ({w20.gt_concordance_hc.min():.3f}–{w20.gt_concordance_hc.max():.3f}), against at most {b20.gt_concordance_hc.max():.3f} for all other pairs. "
 f"No classifier was significant against the exact null in any design (smallest p = {pmin_all:.3f}). With loci selected from training runs only, all six models gave a group-level balanced accuracy of 0.500, and the mean of the null distribution was {min(null_means):.2f}–{max(null_means):.2f}, so 0.5 is not a valid chance reference for leave-one-group-out validation. "
 f"The Brier score, added as a probabilistic metric, was {bt.observed_brier.min():.3f}–{bt.observed_brier.max():.3f} for all models with training-only loci, worse than the 0.25 of a constant prediction, so a balanced accuracy of 0.500 concealed confident misclassification. In this cohort, expressed-variant features recover individual identity rather than the class label. Genotype-based identity checks, grouping by individual and exact permutation nulls should precede any report of classification performance.", hl=True)
b.keep(7)
b.P(8, "【Keywords:】 ⟦machine learning; data leakage; grouped cross-validation; permutation test; sample identity; expressed variants; single-cell RNA sequencing⟧")
b.keep(9)

# ---------------- Introduction
Hk(10)
T("Machine-learning models are increasingly trained on features engineered from high-throughput sequencing data. Such data combine two difficulties: the number of features exceeds the number of independent samples by several orders of magnitude, and the samples themselves are often not independent. Public single-cell RNA sequencing (scRNA-seq) cohorts are a typical case. A cohort may contain only a handful of biological samples, each sequenced in several runs, while the class labels are attached to samples rather than to runs or cells. The series used here, GSE176415, contains seven samples of two tissue classes, unwounded skin and wound edge, sequenced as fourteen runs [1].")
T("In such data a classifier can reach high accuracy by learning which sample, or which person, a run comes from instead of learning the class. Whether this happens depends on the whole feature-engineering pipeline and on how validation is organised, and it can be checked only when the pipeline is transparent and the dependence structure of the data is known.")
b.keep(13)
T("Coordinate-level variants are too sparse for sample-level learning. Rare-variant genetics addresses a related problem by aggregating variants within functional units such as genes, which can increase statistical power when individual variant effects are weak. Following this representational idea, a gene can serve as an interpretable aggregation unit that reduces coordinate instability caused by uneven RNA coverage and aligns features with pathway databases. At the same time, high-dimensional genomic classification is vulnerable to feature leakage, unstable selection, and optimistic resampling [8], [9]. Small-sample cross-validation has large uncertainty, and gene selection before cross-validation biases prediction estimates [8], [9], whereas sample-level summaries provide more reliable inferential units than individual cells [10].", hl=False)
T("A further source of dependence is genetic identity. Most variants called from RNA are germline alleles, so two runs, or two samples, from one person share most of their calls; variant calling from scRNA-seq has in fact been used to verify the identity of cell lines [4]. If a feature set encodes the person, a classifier evaluated on runs, or on samples that come from the same person, can reach high accuracy without learning the condition. For the cohort studied here, Kunikeyev et al. [12] reported that run-level cross-validation of a logistic-regression gene-burden model gave balanced accuracy 0.973, which fell to 0.708 under sample-grouped validation and was not significant in a sample-level permutation test. Whether the features carry any condition signal at all, and whether the GEO samples are independent individuals, was not examined.", hl=True)
T("This paper addresses that gap with a label-free audit of the feature space followed by exact permutation testing of grouped validation. Its contributions are: (1) a comparison of within-sample and between-sample run similarity under four measures, which shows that expressed-variant and expression profiles are dominated by sample identity; (2) a genotype-concordance audit that reveals two GEO samples from one individual, so that the seven samples correspond to six persons; (3) an exact null distribution over all 35 group labelings for six classifiers under sample-level and person-level grouping, which shows that no design exceeds chance and that chance itself lies below 0.5; and (4) practical rules for reporting expressed-variant classifiers in small cohorts. The study is a methodological audit; it does not claim class-specific variants or a deployable classifier.", hl=True)

# ---------------- Methods
Hk(16)
Hk(17)
T("The public data originate from NCBI BioProject PRJNA736095 and GEO series GSE176415, a public human scRNA-seq series of wound-edge and unwounded-skin samples [1]. ⟦The single-cell series contains seven GEO samples: four unwounded-skin samples (Sc_Skin1–Sc_Skin4; GSM5364333–GSM5364336) and three wound-edge samples (Sc_W1–Sc_W3; GSM5364337–GSM5364339). Each sample was sequenced as two SRA runs, giving eight unwounded-skin runs (SRR14762238–SRR14762245) and six wound-edge runs (SRR14762246–SRR14762248 and SRR14762250–SRR14762252). Condition labels were taken directly from the GEO sample titles; the labels used in the previous version of this manuscript were inverted relative to GEO and have been corrected throughout (Supplementary Table S1). GEO does not provide donor identifiers, and the sample metadata list Sc_Skin1 and Sc_W2 with the same sex and age (male, 69 years). The run (n = 14) is the unit for similarity analysis, whereas the GEO sample (n = 7) and the individual (n = 6, after the identity audit) are the units for validation.⟧", hl=False)
Hk(19)
T("⟦The workflow contains four layers: alignment, variant calling, feature construction, and the audit itself (Figure 1).⟧ FASTQ reads were aligned to the GRCh38 reference with the splice-aware STAR aligner v2.7.10a in STARsolo mode (https://github.com/alexdobin/STAR) ⟦with GENCODE release 43 annotation [11]. Variants were called separately for each run with GATK v4.6.2.0 (https://gatk.broadinstitute.org) following the RNA-seq best-practice route: read-group assignment, SplitNCigarReads, HaplotypeCaller (soft-clipped bases ignored, calling confidence 20) and hard filtering with QD < 2, FS > 30, MQ < 40 and SOR > 3; only PASS records were retained. Pseudobulk expression counts per run were transformed to log1p(CPM) for 18,860 genes. Analyses used Python with scikit-learn 1.9.0 (https://scikit-learn.org) and XGBoost 3.2.0. Every run retains its alignment, raw and filtered VCF, variant-to-gene table and feature row, and all result tables are released with per-group predictions (Supplementary Materials).⟧", hl=False)
b.picture(21, str(FIG / "Figure_1_audit_workflow.png"), 16.0)
CAP("Figure 1 – Workflow of the identity and validation audit")
S("Recurrent loci and gene burden")
T("Let V_{s} denote the set of PASS loci of run s and S the set of runs used to build features. The support of locus v is the number of runs in S that carry it, and the recurrent set R contains loci with support of at least four runs and a maximum variant allele fraction of at least 0.05:", hl=True)
b.equation(27, sub(r("f"), r("v")) + r("=") + nary("∑", r("s∈S"), "", r("1") + d(r("v∈") + sub(r("V"), r("s")), "[", "]")) + r(",    R=") + d(r("v: ") + sub(r("f"), r("v")) + r("≥4,  ") + sub(r("max"), r("s∈S"), ) + sub(r("VAF"), r("sv")) + r("≥0.05"), "{", "}"), 1)
T("The gene burden of gene g in run s counts the recurrent loci of s that overlap exons of g, where M_{vg} = 1 if locus v overlaps an exon of g:", hl=True)
b.equation(29, sub(r("GB"), r("s,g")) + r("=") + nary("∑", r("v∈R∩") + sub(r("V"), r("s")), "", sub(r("M"), r("vg"))), 2)
T("In the global design S contains all 14 runs (27,230 genes); in the training-only design R and the burden matrix are rebuilt inside every fold from the training runs only, so the held-out runs do not influence which loci become features.", hl=True)
S("Label-free similarity measures")
T("Four similarity measures were computed for all 91 run pairs: the Jaccard index of PASS loci, the genotype concordance on shared loci, the Spearman correlation of gene-burden profiles, and the Pearson correlation of log1p(CPM) expression profiles. With h_{s}(v) the genotype class of locus v in run s (heterozygous or homozygous alternative):", hl=True)
b.equation(27, r("J") + d(r("s,t")) + r("=") + f(d(sub(r("V"), r("s")) + r("∩") + sub(r("V"), r("t")), "|", "|"), d(sub(r("V"), r("s")) + r("∪") + sub(r("V"), r("t")), "|", "|")) + r(",    GC") + d(r("s,t")) + r("=") + f(r("1"), d(sub(r("V"), r("s")) + r("∩") + sub(r("V"), r("t")), "|", "|")) + nary("∑", r("v∈") + sub(r("V"), r("s")) + r("∩") + sub(r("V"), r("t")), "", r("1") + d(sub(r("h"), r("s")) + d(r("v")) + r("=") + sub(r("h"), r("t")) + d(r("v")), "[", "]")), 3)
T("Pairs were divided into three classes: two runs of the same GEO sample (7 pairs), runs of different samples with the same condition (36 pairs), and runs of different samples with different conditions (48 pairs). The sample effect was measured as the mean similarity of same-sample pairs minus that of all other pairs and was tested against 10,000 random re-pairings of the 14 runs; in addition, the share of runs whose most similar run belonged to the same sample (1-NN identification) was recorded. The condition effect was measured as the mean similarity of same-condition minus different-condition pairs among different-sample pairs and was tested exactly against all 35 ways of labelling three of the seven samples as wound edge.", hl=True)
S("Genotype identity audit")
T("Calls with low depth are dominated by allelic dropout. The audit therefore restricted each run to calls with read depth of at least 10, or at least 20, and computed the genotype concordance and Jaccard index on these high-confidence calls for every run pair. Two runs from one person are expected to reach the concordance observed between the two runs of one GEO sample, whereas runs from different persons share fewer loci and disagree more often in genotype class.", hl=True)
S("Classifiers, grouped validation and exact null")
T(f"Six classifiers with fixed hyperparameters were compared: L2-regularised logistic regression with balanced class weights, a multilayer perceptron (16 hidden units, alpha = 1.0), a 500-tree random forest, an RBF-kernel support vector machine, k-nearest neighbours (k = 3, distance weighting) and XGBoost (150 trees of depth 2, learning rate 0.03). Variance filtering and standardisation were fitted inside each training fold. Four leave-one-group-out designs were evaluated: sample-level (GSM) folds with global loci, GSM folds with training-only loci, person-level folds with training-only loci in which Sc_Skin1 and Sc_W2 are held out together (six folds), and GSM folds with expression features. Held-out run probabilities were averaged per GEO sample, a sample was called wound edge when the mean probability was at least 0.5, and balanced accuracy and ROC-AUC were computed on the seven sample-level predictions:", hl=True)
b.equation(41, r("BA=") + f(r("1"), r("2")) + d(f(r("TP"), r("TP+FN")) + r("+") + f(r("TN"), r("TN+FP"))), 4)
T("Because feature construction is label-free in every design, the folds were built once and every model was refitted under all 35 labelings of the seven samples. The exact p-value of an observed balanced accuracy is the share of labelings, including the observed one, that reach at least the same value; its smallest attainable value is 1/35 ≈ 0.029:", hl=True)
b.equation(43, sub(r("p"), r("exact")) + r("=") + f(r("1"), r("35")) + nary("∑", r("π=1"), r("35"), r("1") + d(sub(r("BA"), r("π")) + r("≥") + sub(r("BA"), r("obs")), "[", "]")), 5)

T("⟦In addition to balanced accuracy, which records only on which side of 0.5 the mean probability of a sample falls, the sample-level probabilities were scored with the Brier score (6), the mean squared difference between the predicted wound-edge probability p_{g} and the label y_{g} of the seven samples. Lower values are better, and a constant prediction of 0.5 for every sample scores 0.25. Its exact p-value is the share of the 35 labelings whose Brier score is at most the observed one. The Brier score was not used in the previous analysis of this cohort [9].⟧")
b.equation(43, r("BS=") + f(r("1"), r("7")) + nary("∑", r("g=1"), r("7"), sup(d(sub(r("p"), r("g")) + r("−") + sub(r("y"), r("g"))), r("2"))), 6)

# ---------------- Results
Hk(47)
S("Call set and quality control")
per = N["per"]
T(f"Per run, GATK produced {fint(per.n_pass.min())}–{fint(per.n_pass.max())} PASS calls (median 1,272,246.5), of which {100*per.n_snp.sum()/per.n_pass.sum():.1f}% were single-nucleotide variants; the union over all runs contained 9,528,556 distinct loci. Coverage was low, as expected for droplet scRNA-seq: the median read depth at PASS calls was {per.median_dp.min():.0f}–{per.median_dp.max():.0f} and only {per.pct_dp_ge10.min():.1f}–{per.pct_dp_ge10.max():.1f}% of calls had depth of at least 10. The two runs of each sample yielded almost the same number of calls, but only {100*0.068:.1f}–{100*0.116:.1f}% of their shared loci had identical depth and allele fraction, which confirms that they are separate sequencing runs rather than duplicated files. With the global recurrence rule, each run kept 25–37% of its PASS calls (Supplementary Table S1).", hl=True)
S("Runs cluster by sample, not by condition")
T(f"Table 1 and Figures 2–3 summarise the similarity analysis. For all four measures, runs of the same sample were far more similar than runs of different samples: the mean Jaccard index was {J.within:.3f} against {J.between_all:.3f}, genotype concordance {GC.within:.3f} against {GC.between_all:.3f}, gene-burden correlation {GB.within:.3f} against {GB.between_all:.3f}, and expression correlation {EX.within:.3f} against {EX.between_all:.3f}. The most similar run of every run was its partner from the same sample (14 of 14 for each measure), and none of the 10,000 random re-pairings reached the observed sample effect (p < 0.001). By contrast, different-sample pairs that shared a condition were not more similar than pairs with different conditions; the difference was close to zero or negative and its exact p-value was {condp[0]:.2f}, {condp[1]:.2f}, {condp[2]:.2f} and {condp[3]:.2f}, respectively. The variant-derived features, and the expression profiles as well, therefore describe which sample a run came from, not its class label.", hl=True)
TCAP("Table 1 – Mean similarity by pair class and permutation tests (14 runs, 91 pairs)")
rows = [["Measure", "Same sample (7 pairs)", "Different samples, same condition (36)", "Different samples, different condition (48)", "1-NN sample identification", "Sample effect, p", "Condition effect, exact p"]]
for name, lab in [("PASS-locus Jaccard", "Locus Jaccard index"), ("Genotype concordance (shared loci)", "Genotype concordance"), ("Gene-burden Spearman (cohort filter)", "Gene-burden Spearman ρ"), ("Expression Pearson (log1p CPM)", "Expression Pearson r")]:
    x = don.loc[name]
    rows.append([lab, fmt(x.within), fmt(x.between_same), fmt(x.between_diff), f"{int(round(14*x.nn_donor_id_acc))}/14", "< 0.001", f"{x.p_condition_exact:.3f}"])
b.data_table(rows, [3.4, 2.0, 2.4, 2.4, 2.0, 1.6, 1.8], font_size=20,
             note="Note: compiled by the authors from Supplementary Table S2 (result files A_donor_structure_summary.tsv and A_pairwise_similarity.tsv). Sample effect: 10,000 random re-pairings of the 14 runs; condition effect: all 35 labelings of the seven samples.")
b.picture(21, str(FIG / "Figure_2_similarity_heatmaps.png"), 16.0)
CAP("Figure 2 – Run-by-run similarity of PASS loci (A) and expression (B); white lines separate the seven GEO samples")
b.picture(21, str(FIG / "Figure_3_pair_classes.png"), 16.0)
CAP("Figure 3 – Similarity of run pairs by class for the four measures; black bars show class means")
S("Two GEO samples come from one individual")
T(f"The identity audit is shown in Table 2 and Figure 4. At read depth of at least 20, the two runs of each sample agreed in genotype class at {w20.gt_concordance_hc.min():.4f}–{w20.gt_concordance_hc.max():.4f} of their shared loci, whereas pairs of runs from different samples agreed at {b20.gt_concordance_hc.min():.3f}–{b20.gt_concordance_hc.max():.3f}. One pair of samples did not follow this pattern: runs of Sc_Skin1 (GSM5364333, unwounded skin) and Sc_W2 (GSM5364338, wound edge) agreed at {s20.gt_concordance_hc:.4f} on {fint(s20.n_shared_hc)} shared loci on average, which is inside the range of the within-sample pairs. The same result was obtained at depth of at least 10 ({s10.gt_concordance_hc:.4f} against {w10.gt_concordance_hc.min():.4f}–{w10.gt_concordance_hc.max():.4f} within samples and at most {b10.gt_concordance_hc.max():.3f} for other pairs). Their Jaccard index ({s20.jaccard_hc:.3f}) was lower than for runs of one sample ({w20.jaccard_hc.min():.3f}–{w20.jaccard_hc.max():.3f}) but higher than for any other pair (at most {b20.jaccard_hc.max():.3f}), as expected for two different tissues of one person, in which different genes are expressed. Together with the identical sex and age in the metadata, the genotypes show that Sc_Skin1 and Sc_W2 are unwounded skin and wound edge of the same individual. The seven GEO samples therefore represent six persons, and sample-level grouping leaves this person on both sides of a split in two of the seven folds.", hl=True)
TCAP("Table 2 – Genotype identity audit on high-confidence calls (mean over run pairs)")
def row(lbl, x10, x20):
    return [lbl, str(len(x20) if lbl != "Sc_Skin1 vs Sc_W2" else 1), f"{x10.gt_concordance_hc.min():.4f}–{x10.gt_concordance_hc.max():.4f}" if len(x10) > 1 else f"{x10.gt_concordance_hc.iloc[0]:.4f}",
            f"{x20.gt_concordance_hc.min():.4f}–{x20.gt_concordance_hc.max():.4f}" if len(x20) > 1 else f"{x20.gt_concordance_hc.iloc[0]:.4f}",
            f"{x20.jaccard_hc.min():.3f}–{x20.jaccard_hc.max():.3f}" if len(x20) > 1 else f"{x20.jaccard_hc.iloc[0]:.3f}"]
rows = [["Sample pair", "Number of sample pairs", "Genotype concordance, DP ≥ 10", "Genotype concordance, DP ≥ 20", "Jaccard index, DP ≥ 20"],
        row("Two runs of the same sample", w10, w20), row("Sc_Skin1 vs Sc_W2", ident(10, "pair"), ident(20, "pair")), row("All other pairs of samples", b10, b20)]
b.data_table(rows, [4.6, 2.2, 3.2, 3.2, 2.8], font_size=20,
             note="Note: compiled by the authors from Supplementary Table S3 (result files E_identity_check_donor_pairs.tsv and E_identity_check_pairs.tsv). For pairs of different samples, values are averaged over the four run pairs.")
b.picture(21, str(FIG / "Figure_4_identity_audit.png"), 16.0)
CAP("Figure 4 – Genotype concordance and Jaccard index of high-confidence calls for all run pairs at read depth ≥ 10 (A) and ≥ 20 (B)")
S("Grouped validation against the exact null")
rng = lambda s: f"{s.min():.3f}–{s.max():.3f}"
T(f"Table 3 and Figure 5 compare the observed balanced accuracy of each classifier with the 35 values obtained under all group labelings. With global loci, logistic regression, the multilayer perceptron, the random forest and k-nearest neighbours reached 0.708, the value reported earlier for logistic regression [12], but this value was not significant (exact p = {gl[gl.ba > 0.7].p_ba.min():.3f}–{gl[gl.ba > 0.7].p_ba.max():.3f}; for logistic regression {int(round(35*gl.loc['Logistic regression (L2)'].p_ba))} of the 35 labelings reached it). When the recurrent loci were selected from the training runs only (636,538–797,513 loci in 25,381–26,324 genes per fold), every model assigned all held-out samples to the unwounded class and reached exactly 0.500 (p = {rng(tr.p_ba)}). Grouping by person did not change this: in the fold that holds out Sc_Skin1 and Sc_W2 together, {fint(pf_pair.n_recurrent_loci)} loci in {fint(pf_pair.n_genes)} genes were selected from the remaining runs, and all models again gave 0.500 (p = {rng(pe.p_ba)}). Expression features gave {rng(ex.ba)} with p = {rng(ex.p_ba)}. No model reached significance at the 0.05 level in any design.", hl=True)
T(f"The null distributions also show that 0.5 is not the chance level of these designs. The mean balanced accuracy over the 35 labelings was {rng(tr.null_ba)} with training-only loci, {rng(pe.null_ba)} with person-level folds and {rng(gl.null_ba)} with global loci. The reason is structural: holding out a group removes one of only three or four groups of its class from the training set, which shifts the fitted model towards the opposite class and penalises exactly the held-out group. A result of 0.5 under leave-one-group-out validation can therefore look like chance while lying above the actual null mean, and a result above 0.5 can still be ordinary. Under person-level folds, ROC-AUC values of {hi_auc.auc.min():.2f}–{hi_auc.auc.max():.2f} appeared for {len(hi_auc)} models with exact p = {hi_auc.p_auc.min():.3f}–{hi_auc.p_auc.max():.3f}; because balanced accuracy stayed at 0.500, the AUC pools probabilities from different fitted models, and 24 model–design combinations were tested, this is treated as a hypothesis for larger cohorts rather than as a finding.", hl=True)
TCAP("Table 3 – Group-level balanced accuracy and exact p-value over 35 labelings")
rows = [["Classifier", "GSM folds, global loci", "GSM folds, training-only loci", "Person folds, training-only loci", "GSM folds, expression", "Null mean, training-only loci"]]
for m in MODELS:
    rows.append([SHORT[m]] + [f"{nul.loc[(dd, m)].ba:.3f} (p = {nul.loc[(dd, m)].p_ba:.3f})" for dd in (D_GLOB, D_TRAIN, D_PERS, D_EXPR)] + [f"{tr.loc[m].null_ba:.3f}"])
b.data_table(rows, [3.2, 2.8, 2.8, 2.8, 2.8, 1.8], font_size=20,
             note="Note: compiled by the authors from Supplementary Table S4 (result file F_exact_null_all_labelings.tsv). GSM folds: 7 folds; person folds: 6 folds with Sc_Skin1 and Sc_W2 held out together. The smallest attainable p-value is 1/35 = 0.029.")
b.picture(21, str(FIG / "Figure_5_exact_null.png"), 16.0)
CAP("Figure 5 – Observed balanced accuracy (orange diamonds) against all 35 group labelings (grey points; black bars show the null mean) for four validation designs")

S("Probability quality: the Brier score")
T(f"Table 4 adds the Brier score to the comparison. With training-only loci every model had a balanced accuracy of exactly 0.500, which reads as chance, yet the Brier scores were {bt.observed_brier.min():.3f}–{bt.observed_brier.max():.3f}, all worse than the 0.25 of a constant prediction: the models were not uncertain but confidently wrong. For logistic regression the three wound-edge samples received wound probabilities of 0.015, 0.005 and 0.294. With global loci the Brier score of {len(bg_low)} models was slightly below 0.25 ({bg_low.observed_brier.min():.3f}–{bg_low.observed_brier.max():.3f}), but none was significant (exact p ≥ {bg.exact_p_brier.min():.3f}). The largest single error in this design shows the identity effect directly: Sc_Skin1, an unwounded-skin sample, received a wound probability of 0.9997 from logistic regression, because the other sample of the same person, Sc_W2, was in the training set with the wound label; Sc_W2 in turn received 0.24. Under person-level folds {len(bp_min)} models ({', '.join(SHORT[m] for m in bp_min.index)}) reached the smallest attainable exact p of 0.029 for the Brier score, in line with their ROC-AUC, but their scores ({', '.join(f'{v:.3f}' for v in bp_min.observed_brier)}) were still worse than the constant reference, and with 24 model–design combinations none remains significant after Holm correction.")
TCAP("Table 4 – Brier score of the sample-level probabilities and exact p-value over 35 labelings (lower is better; constant 0.5 gives 0.250)")
rows = [["Classifier", "GSM folds, global loci", "GSM folds, training-only loci", "Person folds, training-only loci", "GSM folds, expression"]]
for m in MODELS:
    rows.append([SHORT[m]] + [f"{br.loc[(dd, m)].observed_brier:.3f} (p = {br.loc[(dd, m)].exact_p_brier:.3f})" for dd in (D_GLOB, D_TRAIN, D_PERS, D_EXPR)])
b.data_table(rows, [3.4, 3.2, 3.2, 3.2, 3.0], font_size=20,
             note="Note: compiled by the authors from Supplementary Table S6 (result file H_brier_exact_summary.tsv). Brier score as in (6) over the seven sample-level probabilities; exact p is the share of the 35 labelings with a Brier score at most the observed one.")

# ---------------- Discussion
Hk(74)
T("The audit explains why expressed-variant classifiers look accurate in this cohort and why the accuracy disappears under proper grouping. Expressed variants are, first of all, a genotype: two runs of one sample share three times as many loci as runs of different samples, and their genotype classes agree almost perfectly. Any feature built from these calls, including gene-level burden, inherits this structure, and a flexible model can identify the run's sample from it without any wound-related signal. Run-level cross-validation, in which the partner run of each test run is in the training set, therefore measures sample identification. The same structure was found in expression profiles, so the problem is not specific to variants; it is a property of small cohorts with replicate runs [8], [10].", hl=True)
T("The identity audit adds a less obvious point: the grouping unit supplied by the public metadata is not necessarily the person. GEO samples are usually treated as donors, but here two of them come from one individual. Genotype concordance on high-depth calls is a cheap check that requires no extra data, because the calls are already produced by the variant branch [4]. In this cohort the paired sample did not create a significant result, but in other designs, for example paired samples of both classes from every donor, ignoring it would place one person in both the training and the test set of every split.", hl=True)
T("The Brier score adds what balanced accuracy hides. A balanced accuracy of 0.5 reads as chance, but the probabilities behind it were confidently wrong, and the most confident error with global loci came from the two samples of one person, each predicted with the label of the other. A proper scoring rule costs nothing extra in an exact test and shows whether a model is merely uncertain or systematically misled.", hl=True)
T(f"The exact null is the appropriate reference for small grouped designs. With seven groups there are only 35 labelings, so the full distribution can be computed for every model at little cost, the smallest attainable p-value is 0.029, and no permutation sampling error arises. The distribution also corrects the intuition that 0.5 is the chance level: under leave-one-group-out validation the null mean was {min(null_means):.2f}–{max(null_means):.2f} in our designs, so reports should compare against the null rather than against 0.5.", hl=True)
T(f"Several limitations apply. The cohort contains seven samples from six persons, so the analysis can reject strong claims but cannot detect weak condition effects; with 35 labelings even a perfect classifier would reach only p = 0.029. Variant calls from droplet scRNA-seq have low depth, are conditional on expression and include RNA-editing and mapping artefacts [5], [6], [7]; the identity audit is robust to these effects because it compares runs processed identically, but it does not validate individual loci. The identity of Sc_Skin1 and Sc_W2 is inferred from genotypes and metadata and has not been confirmed by the data submitters. Finally, the training-only design selects loci by support and allele fraction only; other feature definitions, for example normalised burdens or consequence weights, may behave differently and should be audited in the same way.", hl=True)
Hk(77)
T("This study audited machine-learning features derived from expressed variants in a public scRNA-seq cohort with two tissue classes. Run-level similarity showed that variant-derived and expression features identify the GEO sample of every run, whereas they carry no detectable difference between conditions. A genotype-concordance check found that two samples registered as different donors come from one individual, so the seven samples represent six persons. Against an exact null over all 35 labelings, none of six classifiers was significant under sample-level or person-level grouping, all reached exactly 0.500 when loci were selected inside training folds, and the null mean lay below 0.5. The Brier score showed that a balanced accuracy of 0.500 concealed confidently wrong probabilities. For studies of this kind we recommend five steps before any performance is reported: verify sample identity by genotype concordance, group validation by individual, build all data-dependent features inside training folds, compare results with an exact or permutation null rather than with 0.5, and report a proper scoring rule such as the Brier score next to balanced accuracy.", hl=True)
b.keep(79); b.keep(80); b.keep(81)
T("The authors acknowledge the NCBI SRA and GEO data providers and the contributors of the original PRJNA736095 study. ⟦During the revision of this manuscript in November 2026, Claude (Anthropic; model Claude Opus 5.5) was used to write analysis scripts on the authors' instructions, to draft the revised text and tables from the result files, and for language editing. All analyses were run, checked and interpreted by the authors, who reviewed and edited all content and take full responsibility for the final manuscript.⟧ The authors declare no conflicts of interest.", hl=False)
b.keep(83)
T("Source data: PRJNA736095 / GSE176415. ⟦Result tables, per-group predictions and analysis scripts are provided as Supplementary Materials;⟧ identifying repository links are supplied separately and will be restored after anonymous peer review.", hl=False)
b.keep(85)
T("Supplementary Materials (KBTU_rev2_Supplementary_Materials.docx) contain Note S1 (correction of condition labels), Note S2 (software and parameters), Table S1 (runs, GEO samples, labels and call counts), Table S2 (similarity summary), Table S3 (identity audit), Table S4 (exact-null summary), Table S5 (training-only feature counts per fold) and Table S6 (Brier scores). The accompanying CSV files contain all run-pair similarities, all run-pair identity statistics, the balanced accuracy and ROC-AUC of every model under all 35 labelings, and the training-only feature counts of every fold.", hl=True)
# reproducibility note removed (issue resolved); references
b.keep(89)
ref_start = len(b.out)
for i in [91, 93, 94, 95, 96, 97, 98, 99, 100]:  # [1] Gornik and [3] Theocharidis removed
    if i == 93:
        b.P(90, "[4]\tD. Ramazzotti et al., “Variant calling from scRNA-seq data allows the assessment of cellular identity in patient-derived cell lines,” Nature Communications, vol. 13, art. 2718, 2022, doi: ⟦10.1038/s41467-022-30230-w⟧.")
    elif i == 94:
        b.P(90, "[5]\tM. Wiens et al., “⟦Benchmarking bulk and single-cell variant-calling approaches on Chromium scRNA-seq and scATAC-seq libraries⟧,” Genome Research, vol. 34, ⟦no. 8,⟧ pp. 1196–1210, 2024, doi: 10.1101/gr.277066.122.")
    else:
        b.keep(i)
b.P(90, "[12]\tA. Kunikeyev, A. A. Salybekov, A. Yerimbetova, and B. Omarov, “Integrating mutation-derived and expression features from single-cell RNA sequencing: pitfalls of standard cross-validation in small-cohort settings,” International Journal of Molecular Sciences, vol. 27, no. 14, art. 6429, 2026, doi: 10.3390/ijms27146429.", hl=True)

# numbering follows first citation; Kunikeyev (cited in the introduction) now precedes Frankish (methods)
db.renumber_citations(b.out, {2: 1, 4: 2, 5: 3, 6: 4, 7: 5, 8: 6, 9: 7, 10: 8, 12: 9, 11: 10})
refs = b.out[ref_start:]
refs.sort(key=lambda el: int(re.match(r"\[(\d+)\]", "".join(t.text or "" for t in el.iter(db.qn("w:t")))).group(1)))
b.out[ref_start:] = refs

OUT.mkdir(parents=True, exist_ok=True)
b.save(OUT / "1_article" / "Gene-Burden_KBTU_rev2_highlighted.docx")
print("saved")
