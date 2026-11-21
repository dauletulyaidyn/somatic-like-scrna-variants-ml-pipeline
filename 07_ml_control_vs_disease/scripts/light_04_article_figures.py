#!/usr/bin/env python3
"""Publication figures for the NAN RK (pipeline) and KBTU (donor-structure) revisions.
Reads results of light_01..03 and the cached PASS calls; writes 600-dpi PNGs."""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np
import pandas as pd

plt.rcParams.update({"font.family": "Arial", "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8,
                     "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7, "axes.spines.top": False,
                     "axes.spines.right": False, "savefig.dpi": 600})
BLUE, ORANGE, GREY, TEAL, RED, PURPLE = "#356da8", "#d06b36", "#8a8a8a", "#2a9d8f", "#8b1e1e", "#6b78b4"
W = 6.3  # inches, full text width


def short(title: str) -> str:
    return title.replace("Sc_", "")


def box(ax, x, y, w, h, title, lines, color, fs=7):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.008,rounding_size=0.015", fc=color + "18", ec=color, lw=1))
    ax.text(x + w / 2, y + h - 0.035, title, ha="center", va="top", fontsize=fs + 0.5, fontweight="bold", color="#222222")
    ax.text(x + w / 2, y + h - 0.09, "\n".join(lines), ha="center", va="top", fontsize=fs - 0.5, color="#333333", linespacing=1.35)


def arrow(ax, x0, y0, x1, y1):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="-|>", lw=1, color="#444444"))


def pipeline_nanrk(out: Path):
    fig, ax = plt.subplots(figsize=(W, 2.5)); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    top = [("1. Input & labels", ["PRJNA736095 FASTQ", "14 SRR runs, 7 GSM", "labels from GEO titles", "(4 unwounded / 3 wound)"], BLUE),
           ("2. STARsolo", ["GRCh38 + GENCODE v43", "CB/UMI-tagged BAM", "per-run expression"], BLUE),
           ("3. GATK 4.6.2 calling", ["SplitNCigarReads", "HaplotypeCaller (conf. 20)", "hard filters: QD<2, FS>30,", "MQ<40, SOR>3 -> PASS"], ORANGE),
           ("4. Recurrent loci", ["support >= 4 runs", "max VAF >= 0.05", "global or training-only", "(inside each fold)"], ORANGE)]
    bot = [("5. Variant-to-gene", ["GENCODE exon overlap", "944,972 locus-gene pairs"], TEAL),
           ("6. Gene burden", ["count of recurrent loci", "per gene and run", "27,230 genes (global)"], TEAL),
           ("7. Grouped validation", ["GSM- and person-level", "leave-one-group-out", "exact 35-labeling null"], PURPLE),
           ("8. Audit outputs", ["QC & coverage tables", "filter-sensitivity curve", "runtime/storage profile", "hashes, predictions"], PURPLE)]
    w, h, gap = 0.225, 0.42, 0.025
    for k, (t, l, c) in enumerate(top):
        x = 0.01 + k * (w + gap); box(ax, x, 0.55, w, h, t, l, c)
        if k: arrow(ax, x - gap + 0.002, 0.76, x - 0.002, 0.76)
    for k, (t, l, c) in enumerate(bot):
        x = 0.01 + (3 - k) * (w + gap); box(ax, x, 0.02, w, h, t, l, c)
        if k: arrow(ax, x + w + gap - 0.002, 0.23, x + w + 0.002, 0.23)
    arrow(ax, 0.01 + 3 * (w + gap) + w / 2, 0.55, 0.01 + 3 * (w + gap) + w / 2, 0.445)
    fig.savefig(out / "Figure_1_pipeline.png", bbox_inches="tight"); plt.close(fig)


def audit_workflow_kbtu(out: Path):
    fig, ax = plt.subplots(figsize=(W, 2.0)); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    items = [("PASS calls", ["14 runs, GATK", "9.53 M loci", "(union)"], BLUE),
             ("Run similarity", ["Jaccard, genotype", "burden, expression", "3 pair classes"], ORANGE),
             ("Identity audit", ["genotype concordance", "at DP >= 10 / 20", "GSM vs person"], RED),
             ("Grouped CV", ["GSM-LOGO and", "person-LOGO", "6 classifiers"], PURPLE),
             ("Exact null", ["all 35 labelings", "of 7 GSM groups", "p resolution 1/35"], TEAL)]
    w, gap = 0.18, 0.025
    for k, (t, l, c) in enumerate(items):
        x = 0.005 + k * (w + gap); box(ax, x, 0.05, w, 0.9, t, l, c, fs=7.5)
        if k: arrow(ax, x - gap + 0.002, 0.5, x - 0.002, 0.5)
    fig.savefig(out / "Figure_1_audit_workflow.png", bbox_inches="tight"); plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", type=Path, required=True)
    ap.add_argument("--cache-dir", type=Path, required=True)
    ap.add_argument("--analysis-dir", type=Path, required=True)
    ap.add_argument("--nanrk", type=Path, required=True)
    ap.add_argument("--kbtu", type=Path, required=True)
    a = ap.parse_args()
    for d in (a.nanrk, a.kbtu): d.mkdir(parents=True, exist_ok=True)
    meta = pd.read_csv(a.analysis_dir / "metadata.cleaned.tsv", sep="\t")
    samples, titles, gsm, cond = meta.sample_id.tolist(), meta.sample_title.tolist(), meta.gsm.tolist(), meta.condition.tolist()
    labels = [f"{short(t)}-{s[-2:]}" for t, s in zip(titles, samples)]

    # ---------------- NAN RK ----------------
    pipeline_nanrk(a.nanrk)
    au = pd.read_csv(a.analysis_dir / "audit" / "gatk_per_sample_variant_audit.tsv", sep="\t").set_index("sample_id").loc[samples]
    fc = pd.read_csv(a.analysis_dir / "audit" / "gatk_filter_counts.tsv", sep="\t").pivot(index="sample_id", columns="filter", values="count").loc[samples].fillna(0)
    caches = [np.load(a.cache_dir / f"{s}.npz") for s in samples]
    union = np.unique(np.concatenate([c["key"] for c in caches]))
    sup = np.zeros(len(union), np.int16); mv = np.zeros(len(union), np.float32); pos = []
    for c in caches:
        p = np.searchsorted(union, c["key"]); pos.append(p); sup[p] += 1; np.maximum.at(mv, p, c["vaf"])
    sel = (sup >= 4) & (mv >= 0.05)
    cohort_per_run = np.array([sel[p].sum() for p in pos])
    qc = pd.DataFrame({"sample_id": samples, "title": titles, "gsm": gsm, "condition": cond,
                       "raw": au.raw_records.values, "pass": au.with_filters_pass_records.values,
                       "nonpass": au.with_filters_nonpass_records.values, "cohort_recurrent": cohort_per_run,
                       "HighSOR": fc.get("HighSOR", 0).values, "LowQD": fc.get("LowQD", 0).values, "HighFS": fc.get("HighFS", 0).values})
    qc["pct_removed_by_hard_filters"] = 100 * qc.nonpass / qc.raw
    qc["pct_pass_retained_as_recurrent"] = 100 * qc.cohort_recurrent / qc["pass"]
    qc.to_csv(a.nanrk / "per_run_qc_counts.tsv", sep="\t", index=False)
    fig, axes = plt.subplots(1, 2, figsize=(W, 2.6), gridspec_kw={"width_ratios": [1.6, 1]})
    x = np.arange(len(samples)); bw = 0.27
    ax = axes[0]
    ax.bar(x - bw, qc.raw / 1e6, bw, color="#c9c9c9", label="raw HaplotypeCaller")
    ax.bar(x, qc["pass"] / 1e6, bw, color=BLUE, label="PASS (hard filters)")
    ax.bar(x + bw, qc.cohort_recurrent / 1e6, bw, color=ORANGE, label="recurrent (>=4 runs)")
    ax.set_xticks(x, labels, rotation=60, ha="right"); ax.set_ylabel("records, millions"); ax.legend(frameon=False, ncol=1, loc="upper left")
    ax.set_title("A. Call counts per run"); ax.axvline(7.5, color=GREY, lw=0.6, ls=":")
    ax = axes[1]
    bottom = np.zeros(len(samples))
    for f, c in [("HighSOR", PURPLE), ("LowQD", TEAL), ("HighFS", RED)]:
        v = 100 * qc[f] / qc.raw; ax.bar(x, v, 0.7, bottom=bottom, color=c, label=f); bottom += v
    ax.set_xticks(x, labels, rotation=60, ha="right"); ax.set_ylabel("% of raw records flagged"); ax.legend(frameon=False, fontsize=6.5)
    ax.set_title("B. Hard-filter flags (may overlap)")
    fig.tight_layout(); fig.savefig(a.nanrk / "Figure_2_call_counts_qc.png"); plt.close(fig)

    per = pd.read_csv(a.res / "C_per_run_calls_vs_coverage.tsv", sep="\t")
    cor = pd.read_csv(a.res / "C_coverage_correlations.tsv", sep="\t")
    fig, axes = plt.subplots(1, 3, figsize=(W, 2.2))
    for ax, col, lab in zip(axes, ["median_dp", "detected_genes", "bam_gb"], ["median DP at PASS calls", "detected genes (expression)", "BAM size, GB"]):
        for cnd, mk, c in [("unwounded", "o", BLUE), ("wound", "s", ORANGE)]:
            d = per[per.condition == cnd]; ax.scatter(d[col], d.n_pass / 1e6, marker=mk, color=c, s=18, label=cnd, edgecolor="white", lw=0.4)
        r = cor[(cor.x == col) & cor.level.str.startswith("run")].iloc[0]
        ax.set_xlabel(lab); ax.set_title(f"rho = {r.spearman_rho:.2f}, p = {r.p:.1g}")
    axes[0].set_ylabel("PASS calls, millions"); axes[0].legend(frameon=False, loc="lower right")
    fig.tight_layout(); fig.savefig(a.nanrk / "Figure_3_coverage_dependence.png"); plt.close(fig)

    sw = pd.read_csv(a.res / "B_cohort_filter_sweep.tsv", sep="\t")
    fig, axes = plt.subplots(1, 3, figsize=(W, 2.2))
    ax = axes[0]; ax.plot(sw.min_support_runs, sw.n_loci, "o-", ms=3, color=BLUE, label="loci"); ax.plot(sw.min_support_runs, sw.n_genes, "s-", ms=3, color=TEAL, label="genes")
    ax.set_yscale("log"); ax.set_xlabel("min. supporting runs k"); ax.set_title("A. Feature-space size"); ax.legend(frameon=False)
    ax = axes[1]
    for col, lab, c in [("within", "same GSM", ORANGE), ("between_same", "diff. GSM, same cond.", BLUE), ("between_diff", "diff. GSM, diff. cond.", GREY)]:
        ax.plot(sw.min_support_runs, sw[col], "o-", ms=3, color=c, label=lab)
    ax.set_xlabel("min. supporting runs k"); ax.set_ylabel("mean Jaccard"); ax.set_title("B. Run similarity"); ax.legend(frameon=False, fontsize=6)
    ax = axes[2]; ax.plot(sw.min_support_runs, sw.nn_donor_id_acc, "o-", ms=3, color=ORANGE, label="1-NN GSM identification")
    ax.plot(sw.min_support_runs, sw.p_condition_exact, "s-", ms=3, color=BLUE, label="condition effect, exact p"); ax.axhline(0.05, ls=":", color="black", lw=0.7)
    ax.set_ylim(0, 1.05); ax.set_xlabel("min. supporting runs k"); ax.set_title("C. Group vs condition signal"); ax.legend(frameon=False, fontsize=6, loc="center left")
    for ax in axes: ax.axvline(4, ls="--", color=RED, lw=0.8)
    fig.tight_layout(); fig.savefig(a.nanrk / "Figure_4_filter_sensitivity.png"); plt.close(fig)

    rt = pd.read_csv(a.res / "D_gatk_runtime_per_run.tsv", sep="\t").set_index("sample_id").loc[samples]
    steps = [("AddOrReplaceReadGroups", "#bbbbbb"), ("SplitNCigarReads", BLUE), ("HaplotypeCaller", ORANGE), ("VariantFiltration", TEAL), ("SelectVariants", PURPLE)]
    fig, ax = plt.subplots(figsize=(W, 2.3)); bottom = np.zeros(len(samples))
    for s, c in steps:
        v = rt[f"{s}_elapsed_min"].fillna(0).to_numpy() / 60; ax.bar(x, v, 0.7, bottom=bottom, color=c, label=s); bottom += v
    ax.set_xticks(x, labels, rotation=60, ha="right"); ax.set_ylabel("wall-clock hours"); ax.legend(frameon=False, ncol=3, loc="upper left", fontsize=6.5)
    ax.set_ylim(0, bottom.max() * 1.35)
    fig.tight_layout(); fig.savefig(a.nanrk / "Figure_5_runtime.png"); plt.close(fig)

    # ---------------- KBTU ----------------
    audit_workflow_kbtu(a.kbtu)
    mats = {"PASS-locus Jaccard": "A_matrix_pass_locus.tsv", "Expression Pearson (log1p CPM)": "A_matrix_expression.tsv"}
    fig, axes = plt.subplots(1, 2, figsize=(W, 3.1))
    for ax, (name, f), tag in zip(axes, mats.items(), "AB"):
        m = pd.read_csv(a.res / f, sep="\t", index_col=0).loc[samples, samples].to_numpy()
        off = m[~np.eye(len(m), dtype=bool)]
        im = ax.imshow(m, cmap="viridis", vmin=off.min(), vmax=off.max())
        ax.set_xticks(range(len(m)), labels, rotation=90, fontsize=6); ax.set_yticks(range(len(m)), labels, fontsize=6)
        for k in range(1, 7): ax.axhline(2 * k - 0.5, color="white", lw=0.5); ax.axvline(2 * k - 0.5, color="white", lw=0.5)
        ax.set_title(f"{tag}. {name}"); cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03); cb.ax.tick_params(labelsize=6)
    fig.tight_layout(); fig.savefig(a.kbtu / "Figure_2_similarity_heatmaps.png"); plt.close(fig)

    pairs = pd.read_csv(a.res / "A_pairwise_similarity.tsv", sep="\t"); summ = pd.read_csv(a.res / "A_donor_structure_summary.tsv", sep="\t").set_index("measure")
    order = ["within donor", "between donors, same condition", "between donors, different condition"]; cols = [ORANGE, BLUE, GREY]
    fig, axes = plt.subplots(1, 4, figsize=(W, 2.3)); rng = np.random.default_rng(3)
    names = ["PASS-locus Jaccard", "Genotype concordance (shared loci)", "Gene-burden Spearman (cohort filter)", "Expression Pearson (log1p CPM)"]
    short_names = ["A. Locus Jaccard", "B. Genotype concordance", "C. Gene-burden Spearman", "D. Expression Pearson"]
    for ax, n, sn in zip(axes, names, short_names):
        part = pairs[pairs.measure == n]
        for k, (cls, c) in enumerate(zip(order, cols)):
            v = part[part.pair_class == cls].value.to_numpy()
            ax.scatter(k + rng.uniform(-0.17, 0.17, len(v)), v, s=7, color=c, alpha=0.85, lw=0)
            ax.hlines(v.mean(), k - 0.3, k + 0.3, color="black", lw=1.2)
        st = summ.loc[n]; ax.set_xticks(range(3), ["same\nGSM", "diff. GSM\nsame cond.", "diff. GSM\ndiff. cond."], fontsize=6)
        ax.set_title(f"{sn}\nGSM p<0.001; cond. p={st.p_condition_exact:.2f}", fontsize=7)
    fig.tight_layout(); fig.savefig(a.kbtu / "Figure_3_pair_classes.png"); plt.close(fig)

    idp = pd.read_csv(a.res / "E_identity_check_donor_pairs.tsv", sep="\t")
    fig, axes = plt.subplots(1, 2, figsize=(W, 2.5))
    for ax, md, tag in zip(axes, [10, 20], "AB"):
        d = idp[idp.min_dp == md].sort_values("gt_concordance_hc")
        colors = [ORANGE if s else (RED if p == "Sc_Skin1 vs Sc_W2" else GREY) for s, p in zip(d.same_gsm, d.donor_pair)]
        ax.scatter(d.gt_concordance_hc, d.jaccard_hc, c=colors, s=16, edgecolor="white", lw=0.4)
        r = d[d.donor_pair == "Sc_Skin1 vs Sc_W2"].iloc[0]
        ax.annotate("Skin1 vs W2", (r.gt_concordance_hc, r.jaccard_hc), xytext=(-48, 12), textcoords="offset points", fontsize=6.5, color=RED, arrowprops=dict(arrowstyle="-", color=RED, lw=0.6))
        ax.set_xlabel(f"genotype concordance, shared calls DP >= {md}"); ax.set_ylabel(f"Jaccard of calls with DP >= {md}"); ax.set_title(f"{tag}. DP >= {md}")
    axes[0].scatter([], [], c=ORANGE, s=16, label="runs of the same GSM"); axes[0].scatter([], [], c=GREY, s=16, label="runs of different GSMs")
    axes[0].scatter([], [], c=RED, s=16, label="Sc_Skin1 vs Sc_W2"); axes[0].legend(frameon=False, loc="upper left", fontsize=6)
    fig.tight_layout(); fig.savefig(a.kbtu / "Figure_4_identity_audit.png"); plt.close(fig)

    nul = pd.read_csv(a.res / "F_exact_null_all_labelings.tsv", sep="\t")
    designs = ["GSM-LOGO, global loci (mutation)", "GSM-LOGO, training-only loci (mutation)", "Person-LOGO, training-only loci (mutation)", "GSM-LOGO, expression only"]
    dn = ["A. GSM-LOGO, global loci", "B. GSM-LOGO, training-only loci", "C. Person-LOGO, training-only", "D. GSM-LOGO, expression"]
    models = list(dict.fromkeys(nul.model)); ml = ["LR", "MLP", "RF", "SVM", "kNN", "XGB"]
    fig, axes = plt.subplots(1, 4, figsize=(W, 2.4), sharey=True)
    for ax, d, t in zip(axes, designs, dn):
        part = nul[nul.design == d]
        for k, m in enumerate(models):
            v = part[(part.model == m) & ~part.is_observed].balanced_accuracy.to_numpy()
            ax.scatter(k + rng.uniform(-0.2, 0.2, len(v)), v, s=4, color=GREY, alpha=0.6, lw=0)
            ax.hlines(part[part.model == m].balanced_accuracy.mean(), k - 0.3, k + 0.3, color="black", lw=0.9)
            o = part[(part.model == m) & part.is_observed].balanced_accuracy.iloc[0]
            ax.scatter([k], [o], s=22, color=ORANGE, marker="D", zorder=3, edgecolor="white", lw=0.4)
        ax.axhline(0.5, ls="--", color=RED, lw=0.7); ax.set_xticks(range(len(ml)), ml, rotation=90); ax.set_title(t, fontsize=7)
    axes[0].set_ylabel("group-level balanced accuracy")
    fig.tight_layout(); fig.savefig(a.kbtu / "Figure_5_exact_null.png"); plt.close(fig)
    print("figures written"); print(qc.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
