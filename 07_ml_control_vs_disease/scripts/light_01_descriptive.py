#!/usr/bin/env python3
"""Label-free descriptive analyses on the cached PASS calls.

A. Donor structure: within-GSM vs between-GSM similarity of runs
   (PASS-locus Jaccard, genotype concordance, gene-burden Spearman, expression Pearson).
B. Cohort-filter sensitivity: support threshold k = 1..14 (max VAF >= 0.05).
C. Coverage confounding: per-run call counts vs coverage proxies.
D. Compute profile from the GATK completion audit.
E. Run-identity audit (within-pair identical-call fraction; Sc_Skin1 vs Sc_W2).
Condition labels follow GEO sample titles (Sc_Skin* = unwounded, Sc_W* = wound).
"""
from __future__ import annotations

import argparse
import itertools
import json
import zlib
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

RNG = np.random.default_rng(42)
CHROMS = [f"chr{c}" for c in list(range(1, 23)) + ["X", "Y", "M"]]
CHROM_INDEX = {c: i + 1 for i, c in enumerate(CHROMS)}


def enc(chrom, pos, ref, alt):
    idx = CHROM_INDEX.get(chrom, 100 + (zlib.crc32(chrom.encode()) % 27))
    return (idx << 56) | (int(pos) << 24) | (zlib.crc32(f"{ref}>{alt}".encode()) & 0xFFFFFF)


def pair_classes(gsm, cond):
    n = len(gsm)
    out = {}
    for i, j in itertools.combinations(range(n), 2):
        if gsm[i] == gsm[j]:
            out[(i, j)] = "within donor"
        elif cond[i] == cond[j]:
            out[(i, j)] = "between donors, same condition"
        else:
            out[(i, j)] = "between donors, different condition"
    return out


def all_labelings(gsms, n_pos):
    return [set(c) for c in itertools.combinations(gsms, n_pos)]


def donor_stats(sim, gsm, cond, n_perm=10000):
    """sim: n x n similarity. Returns dict of class means, permutation p for donor effect,
    exact p for condition effect (35 relabelings of GSM condition), 1-NN donor ID."""
    n = len(gsm)
    iu = list(itertools.combinations(range(n), 2))
    def class_means(g, c):
        w, bs, bd = [], [], []
        for i, j in iu:
            v = sim[i, j]
            if g[i] == g[j]:
                w.append(v)
            elif c[i] == c[j]:
                bs.append(v)
            else:
                bd.append(v)
        return np.mean(w), np.mean(bs), np.mean(bd), np.mean(bs + bd)
    w, bs, bd, b = class_means(gsm, cond)
    t_donor = w - b
    # null: random pairing of runs into 7 pairs
    null = []
    for _ in range(n_perm):
        perm = RNG.permutation(n)
        g = np.empty(n, dtype=object)
        for k in range(n // 2):
            g[perm[2 * k]] = g[perm[2 * k + 1]] = f"p{k}"
        ww, _, _, bb = class_means(list(g), cond)
        null.append(ww - bb)
    p_donor = (1 + np.sum(np.asarray(null) >= t_donor)) / (1 + n_perm)
    # exact condition test over relabelings of the 7 GSMs (4 unwounded / 3 wound)
    gsms = sorted(set(gsm))
    n_wound = len({g for g, c in zip(gsm, cond) if c == "wound"})
    t_cond = bs - bd
    nulls = []
    for wound_set in all_labelings(gsms, n_wound):
        c2 = ["wound" if g in wound_set else "unwounded" for g in gsm]
        _, s2, d2, _ = class_means(gsm, c2)
        nulls.append(s2 - d2)
    nulls = np.asarray(nulls)
    p_cond = float(np.mean(nulls >= t_cond - 1e-12))
    s = sim.copy().astype(float)
    np.fill_diagonal(s, -np.inf)
    nn = s.argmax(axis=1)
    nn_acc = float(np.mean([gsm[i] == gsm[nn[i]] for i in range(n)]))
    return {"within": w, "between_same": bs, "between_diff": bd, "between_all": b,
            "donor_effect": t_donor, "p_donor_perm": float(p_donor),
            "condition_effect": t_cond, "p_condition_exact": p_cond, "n_relabelings": len(nulls),
            "nn_donor_id_acc": nn_acc}


def jaccard_matrix(pres):
    n = len(pres)
    cnt = np.array([p.sum() for p in pres], dtype=float)
    m = np.eye(n)
    for i, j in itertools.combinations(range(n), 2):
        inter = np.count_nonzero(pres[i] & pres[j])
        m[i, j] = m[j, i] = inter / (cnt[i] + cnt[j] - inter) if cnt[i] + cnt[j] - inter else 0.0
    return m


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache-dir", type=Path, required=True)
    ap.add_argument("--analysis-dir", type=Path, required=True, help="ijms_revision_analysis_2026-06-05")
    ap.add_argument("--bam-dirs", type=Path, nargs="+", required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--min-vaf", type=float, default=0.05)
    a = ap.parse_args()
    out = a.outdir
    (out / "figures").mkdir(parents=True, exist_ok=True)

    meta = pd.read_csv(a.analysis_dir / "metadata.cleaned.tsv", sep="\t")
    samples = meta.sample_id.tolist()
    gsm = meta.gsm.tolist()
    cond = meta.condition.tolist()
    title = meta.sample_title.tolist()
    n = len(samples)

    # ---- load caches, build union index
    caches = [np.load(a.cache_dir / f"{s}.npz") for s in samples]
    keys = [c["key"] for c in caches]
    union = np.unique(np.concatenate(keys))
    U = len(union)
    idx = [np.searchsorted(union, k) for k in keys]
    pres = []
    maxvaf = np.zeros(U, dtype=np.float32)
    support = np.zeros(U, dtype=np.int16)
    for i in range(n):
        p = np.zeros(U, dtype=bool); p[idx[i]] = True; pres.append(p)
        np.maximum.at(maxvaf, idx[i], caches[i]["vaf"])
        support[idx[i]] += 1
    is_snp_u = np.zeros(U, dtype=bool)
    for i in range(n):
        is_snp_u[idx[i]] = caches[i]["is_snp"]
    print(f"union PASS loci: {U}", flush=True)

    # gene mapping (for genes per threshold)
    vg = pd.read_csv(a.analysis_dir / "variant_to_gene" / "variant_gene_long.tsv", sep="\t",
                     usecols=["chrom", "pos", "ref", "alt", "gene_id"])
    vg_keys = np.array([enc(*r) for r in vg[["chrom", "pos", "ref", "alt"]].itertuples(index=False)], dtype=np.int64)
    pos_in_union = np.searchsorted(union, vg_keys)
    ok = (pos_in_union < U) & (union[np.minimum(pos_in_union, U - 1)] == vg_keys)
    vg_u = pd.DataFrame({"u": pos_in_union[ok], "gene": vg.gene_id.to_numpy()[ok]})
    print(f"variant_gene rows matched to union: {ok.sum()}/{len(vg)}", flush=True)

    classes = pair_classes(gsm, cond)
    results = {}

    # ================= A. donor structure =================
    sims = {}
    sims["PASS-locus Jaccard"] = jaccard_matrix(pres)
    # genotype concordance among shared loci (het vs hom-alt)
    gc = np.eye(n)
    homs = []
    for i in range(n):
        h = np.zeros(U, dtype=bool); h[idx[i]] = caches[i]["is_hom"]; homs.append(h)
    for i, j in itertools.combinations(range(n), 2):
        shared = pres[i] & pres[j]
        gc[i, j] = gc[j, i] = np.mean(homs[i][shared] == homs[j][shared])
    sims["Genotype concordance (shared loci)"] = gc
    gb = pd.read_csv(a.analysis_dir / "gene_burden" / "gene_burden_matrix.tsv", sep="\t")
    sims["Gene-burden Spearman (cohort filter)"] = spearmanr(gb[samples].to_numpy()).statistic
    ex = pd.read_csv(a.analysis_dir / "expression_baseline" / "expression_log1p_cpm_matrix.tsv", sep="\t")
    exm = ex[samples].to_numpy()
    exm = exm[(exm > 0).any(axis=1)]
    sims["Expression Pearson (log1p CPM)"] = np.corrcoef(exm.T)

    rows, pair_rows = [], []
    for name, m in sims.items():
        st = donor_stats(m, gsm, cond)
        rows.append({"measure": name, **st})
        for (i, j), cls in classes.items():
            pair_rows.append({"measure": name, "run_a": samples[i], "run_b": samples[j],
                              "title_a": title[i], "title_b": title[j], "pair_class": cls, "value": m[i, j]})
        print(name, {k: round(v, 4) if isinstance(v, float) else v for k, v in st.items()}, flush=True)
    donor_df = pd.DataFrame(rows)
    donor_df.to_csv(out / "A_donor_structure_summary.tsv", sep="\t", index=False)
    pairs_df = pd.DataFrame(pair_rows)
    pairs_df.to_csv(out / "A_pairwise_similarity.tsv", sep="\t", index=False)
    for name, m in sims.items():
        slug = name.split(" ")[0].lower().replace("-", "_")
        pd.DataFrame(m, index=samples, columns=samples).to_csv(out / f"A_matrix_{slug}.tsv", sep="\t")

    # figure A1: Jaccard heatmap
    labels = [f"{t} ({s[-3:]})" for t, s in zip(title, samples)]
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.5))
    for ax, name in zip(axes, ["PASS-locus Jaccard", "Expression Pearson (log1p CPM)"]):
        m = sims[name]
        off = m[~np.eye(n, dtype=bool)]
        im = ax.imshow(m, cmap="viridis", vmin=off.min(), vmax=off.max())
        ax.set_xticks(range(n), labels, rotation=90, fontsize=8); ax.set_yticks(range(n), labels, fontsize=8)
        for k in range(1, n // 2):
            ax.axhline(2 * k - 0.5, color="white", lw=0.6); ax.axvline(2 * k - 0.5, color="white", lw=0.6)
        ax.set_title(name); fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout(); fig.savefig(out / "figures" / "A1_similarity_heatmaps.png", dpi=300); plt.close(fig)
    # figure A2: class strip plots
    order = ["within donor", "between donors, same condition", "between donors, different condition"]
    colors = ["#d06b36", "#356da8", "#8a8a8a"]
    fig, axes = plt.subplots(1, 4, figsize=(18, 5))
    for ax, name in zip(axes, sims):
        part = pairs_df[pairs_df.measure == name]
        for k, (cls, col) in enumerate(zip(order, colors)):
            v = part[part.pair_class == cls].value.to_numpy()
            ax.scatter(k + RNG.uniform(-0.15, 0.15, len(v)), v, s=18, color=col, alpha=0.8)
            ax.hlines(v.mean(), k - 0.3, k + 0.3, color="black", lw=2)
        ax.set_xticks(range(3), ["within\ndonor", "between,\nsame cond.", "between,\ndiff. cond."])
        st = donor_df.set_index("measure").loc[name]
        ax.set_title(f"{name}\ndonor p={st.p_donor_perm:.4f}; condition p={st.p_condition_exact:.3f}", fontsize=9)
        ax.grid(axis="y", alpha=0.2)
    fig.tight_layout(); fig.savefig(out / "figures" / "A2_pair_classes.png", dpi=300); plt.close(fig)

    # ================= E. identity audit =================
    ident = []
    for g in sorted(set(gsm)):
        i, j = [k for k in range(n) if gsm[k] == g]
        shared = pres[i] & pres[j]
        dpi = np.zeros(U, dtype=np.int32); dpi[idx[i]] = caches[i]["dp"]
        dpj = np.zeros(U, dtype=np.int32); dpj[idx[j]] = caches[j]["dp"]
        vi = np.zeros(U, dtype=np.float32); vi[idx[i]] = caches[i]["vaf"]
        vj = np.zeros(U, dtype=np.float32); vj[idx[j]] = caches[j]["vaf"]
        ident.append({"gsm": g, "title": title[i], "run_a": samples[i], "run_b": samples[j],
                      "n_a": int(pres[i].sum()), "n_b": int(pres[j].sum()),
                      "jaccard": sims["PASS-locus Jaccard"][i, j],
                      "frac_shared_identical_DP_and_VAF": float(np.mean((dpi[shared] == dpj[shared]) & (vi[shared] == vj[shared]))),
                      "expr_total_counts_a": None, "expr_total_counts_b": None})
    qc = pd.read_csv(a.analysis_dir / "expression_baseline" / "expression_matrix_qc.tsv", sep="\t").set_index("sample_id")
    for r in ident:
        r["expr_total_counts_a"] = int(qc.loc[r["run_a"], "expression_total_counts"])
        r["expr_total_counts_b"] = int(qc.loc[r["run_b"], "expression_total_counts"])
    ident_df = pd.DataFrame(ident)
    ident_df.to_csv(out / "E_within_pair_identity_audit.tsv", sep="\t", index=False)
    # Sc_Skin1 vs Sc_W2 cross pairs
    jac = sims["PASS-locus Jaccard"]
    s1 = [k for k in range(n) if title[k] == "Sc_Skin1"]; w2 = [k for k in range(n) if title[k] == "Sc_W2"]
    cross = [jac[i, j] for i in s1 for j in w2]
    between = pairs_df[(pairs_df.measure == "PASS-locus Jaccard") & (pairs_df.pair_class != "within donor")].value.to_numpy()
    within = pairs_df[(pairs_df.measure == "PASS-locus Jaccard") & (pairs_df.pair_class == "within donor")].value.to_numpy()
    gcm = sims["Genotype concordance (shared loci)"]
    cross_gc = [gcm[i, j] for i in s1 for j in w2]
    between_gc = pairs_df[(pairs_df.measure.str.startswith("Genotype")) & (pairs_df.pair_class != "within donor")].value.to_numpy()
    within_gc = pairs_df[(pairs_df.measure.str.startswith("Genotype")) & (pairs_df.pair_class == "within donor")].value.to_numpy()
    results["identity_Skin1_vs_W2"] = {
        "cross_jaccard": cross, "between_donor_jaccard_range": [float(between.min()), float(between.max())],
        "between_donor_jaccard_mean": float(between.mean()), "within_donor_jaccard_range": [float(within.min()), float(within.max())],
        "cross_jaccard_percentile_among_between": float(np.mean(between <= np.mean(cross))),
        "cross_genotype_concordance": cross_gc, "between_gc_range": [float(between_gc.min()), float(between_gc.max())],
        "within_gc_range": [float(within_gc.min()), float(within_gc.max())]}

    # ================= B. threshold sweep =================
    sweep = []
    vaf_ok = maxvaf >= a.min_vaf
    gene_sets = vg_u.groupby("u").gene.apply(set) if len(vg_u) else None
    u_with_gene = np.zeros(U, dtype=bool); u_with_gene[vg_u.u.unique()] = True
    for k in range(1, n + 1):
        sel = (support >= k) & vaf_ok
        sub = [p & sel for p in pres]
        jm = jaccard_matrix(sub)
        st = donor_stats(jm, gsm, cond, n_perm=2000)
        n_genes = vg_u[np.isin(vg_u.u.to_numpy(), np.flatnonzero(sel))].gene.nunique()
        sweep.append({"min_support_runs": k, "n_loci": int(sel.sum()), "pct_snp": float(100 * is_snp_u[sel].mean()) if sel.any() else np.nan,
                      "n_loci_mapped_to_genes": int((sel & u_with_gene).sum()), "n_genes": int(n_genes),
                      "median_loci_per_run": float(np.median([s.sum() for s in sub])), **st})
        print(f"k={k}: {sel.sum()} loci, within={st['within']:.3f} between={st['between_all']:.3f} nn={st['nn_donor_id_acc']:.2f} condP={st['p_condition_exact']:.3f}", flush=True)
    sweep_df = pd.DataFrame(sweep)
    sweep_df.to_csv(out / "B_cohort_filter_sweep.tsv", sep="\t", index=False)
    fig, axes = plt.subplots(1, 3, figsize=(17, 4.8))
    ax = axes[0]; ax.plot(sweep_df.min_support_runs, sweep_df.n_loci, "o-", color="#356da8", label="loci")
    ax.plot(sweep_df.min_support_runs, sweep_df.n_genes, "s-", color="#2a9d8f", label="genes")
    ax.set_yscale("log"); ax.axvline(4, ls="--", color="#8b1e1e"); ax.set_xlabel("min. supporting runs (k)"); ax.set_title("Feature space size"); ax.legend(); ax.grid(alpha=0.2)
    ax = axes[1]
    for col, lab, c in [("within", "within donor", "#d06b36"), ("between_same", "between, same cond.", "#356da8"), ("between_diff", "between, diff. cond.", "#8a8a8a")]:
        ax.plot(sweep_df.min_support_runs, sweep_df[col], "o-", color=c, label=lab)
    ax.axvline(4, ls="--", color="#8b1e1e"); ax.set_xlabel("min. supporting runs (k)"); ax.set_ylabel("mean Jaccard"); ax.set_title("Run similarity by pair class"); ax.legend(fontsize=8); ax.grid(alpha=0.2)
    ax = axes[2]; ax.plot(sweep_df.min_support_runs, sweep_df.nn_donor_id_acc, "o-", color="#d06b36", label="1-NN donor identification")
    ax.plot(sweep_df.min_support_runs, sweep_df.p_condition_exact, "s-", color="#356da8", label="condition effect, exact p")
    ax.axhline(0.05, ls=":", color="black"); ax.axvline(4, ls="--", color="#8b1e1e"); ax.set_ylim(0, 1.05); ax.set_xlabel("min. supporting runs (k)"); ax.set_title("Donor vs condition signal"); ax.legend(fontsize=8); ax.grid(alpha=0.2)
    fig.tight_layout(); fig.savefig(out / "figures" / "B_cohort_filter_sweep.png", dpi=300); plt.close(fig)

    # ================= C. coverage confounding =================
    bam = {}
    for d in a.bam_dirs:
        for f in d.glob("SRR*.bam"):
            bam.setdefault(f.stem, f.stat().st_size / 1e9)
    per = []
    for i, s in enumerate(samples):
        c = caches[i]
        per.append({"sample_id": s, "title": title[i], "gsm": gsm[i], "condition": cond[i],
                    "n_pass": int(len(c["key"])), "n_snp": int(c["is_snp"].sum()), "n_indel": int((~c["is_snp"]).sum()),
                    "pct_hom_alt": float(100 * c["is_hom"].mean()), "median_dp": float(np.median(c["dp"])), "mean_dp": float(c["dp"].mean()),
                    "pct_dp_ge10": float(100 * np.mean(c["dp"] >= 10)),
                    "bam_gb": bam.get(s, np.nan), "expr_total_counts": int(qc.loc[s, "expression_total_counts"]),
                    "detected_genes": int(qc.loc[s, "detected_genes_count_gt0"])})
    per_df = pd.DataFrame(per)
    per_df.to_csv(out / "C_per_run_calls_vs_coverage.tsv", sep="\t", index=False)
    cor = []
    for col in ["bam_gb", "expr_total_counts", "detected_genes", "mean_dp", "median_dp"]:
        d = per_df.dropna(subset=[col])
        r = spearmanr(d.n_pass, d[col])
        cor.append({"level": "run (n=%d)" % len(d), "x": col, "y": "n_pass", "spearman_rho": r.statistic, "p": r.pvalue})
        g = d.groupby("gsm")[["n_pass", col]].mean()
        r2 = spearmanr(g.n_pass, g[col])
        cor.append({"level": "GSM mean (n=%d)" % len(g), "x": col, "y": "n_pass", "spearman_rho": r2.statistic, "p": r2.pvalue})
    # condition test at GSM level, exact over 35 relabelings
    g = per_df.groupby("gsm").agg(n_pass=("n_pass", "mean"), bam_gb=("bam_gb", "mean"), cond=("condition", "first"))
    g["calls_per_gb"] = g.n_pass / g.bam_gb
    exact = {}
    for col in ["n_pass", "calls_per_gb"]:
        obs = g[g.cond == "wound"][col].mean() - g[g.cond != "wound"][col].mean()
        nulls = []
        for ws in all_labelings(list(g.index), 3):
            m = g.index.isin(list(ws))
            nulls.append(g[col][m].mean() - g[col][~m].mean())
        nulls = np.asarray(nulls)
        exact[col] = {"wound_minus_unwounded": float(obs), "p_two_sided_exact": float(np.mean(np.abs(nulls) >= abs(obs) - 1e-9))}
    pd.DataFrame(cor).to_csv(out / "C_coverage_correlations.tsv", sep="\t", index=False)
    results["coverage_condition_exact"] = exact
    print(pd.DataFrame(cor).to_string(index=False), flush=True)
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))
    for ax, col, lab in zip(axes, ["bam_gb", "detected_genes", "mean_dp"], ["BAM size, GB", "detected genes (expression)", "mean FORMAT DP at PASS calls"]):
        for cnd, mk, c in [("unwounded", "o", "#356da8"), ("wound", "s", "#d06b36")]:
            d = per_df[per_df.condition == cnd]
            ax.scatter(d[col], d.n_pass / 1e6, marker=mk, color=c, label=cnd, s=40)
        for _, r in per_df.iterrows():
            ax.annotate(r.title.replace("Sc_", ""), (r[col], r.n_pass / 1e6), fontsize=7, xytext=(3, 3), textcoords="offset points")
        rr = [x for x in cor if x["x"] == col and x["level"].startswith("run")][0]
        ax.set_xlabel(lab); ax.set_ylabel("PASS calls, millions"); ax.set_title(f"Spearman rho={rr['spearman_rho']:.2f} (p={rr['p']:.3g})"); ax.grid(alpha=0.2)
    axes[0].legend(); fig.tight_layout(); fig.savefig(out / "figures" / "C_calls_vs_coverage.png", dpi=300); plt.close(fig)

    # ================= D. compute profile =================
    au = pd.read_csv(a.analysis_dir / "audit" / "gatk_completion_audit.tsv", sep="\t")
    steps = ["AddOrReplaceReadGroups", "SplitNCigarReads", "HaplotypeCaller", "VariantFiltration", "SelectVariants"]
    comp = []
    for st in steps:
        v = au[f"{st}_elapsed_min"].dropna()
        comp.append({"step": st, "n_runs_logged": len(v), "median_min": v.median(), "min_min": v.min(), "max_min": v.max(), "total_hours": v.sum() / 60})
    comp_df = pd.DataFrame(comp)
    comp_df.to_csv(out / "D_gatk_compute_profile.tsv", sep="\t", index=False)
    au["total_min"] = au[[f"{s}_elapsed_min" for s in steps]].sum(axis=1, min_count=1)
    au = au.merge(per_df[["sample_id", "bam_gb", "n_pass"]], on="sample_id")
    au[["sample_id", "total_min", "bam_gb", "n_pass", "resume_used"] + [f"{s}_elapsed_min" for s in steps]].to_csv(out / "D_gatk_runtime_per_run.tsv", sep="\t", index=False)
    r = spearmanr(au.dropna(subset=["bam_gb"]).bam_gb, au.dropna(subset=["bam_gb"])["HaplotypeCaller_elapsed_min"])
    results["runtime_vs_bam"] = {"spearman_rho_HC_vs_bam": r.statistic, "p": r.pvalue}
    sizes = {}
    vdir = a.analysis_dir / "input_pass_vcfs"
    sizes["pass_vcf_total_gb"] = sum(f.stat().st_size for f in vdir.glob("*.vcf")) / 1e9
    sizes["bam_total_gb_unique_runs"] = float(np.nansum(list(bam.values())))
    sizes["cohort_vcf_gb"] = (a.analysis_dir / "cohort_filter" / "cohort.common.vcf").stat().st_size / 1e9
    results["storage"] = sizes
    fig, ax = plt.subplots(figsize=(9, 4.5))
    bottom = np.zeros(len(au))
    for st, c in zip(steps, ["#bbbbbb", "#356da8", "#d06b36", "#2a9d8f", "#6b78b4"]):
        v = au[f"{st}_elapsed_min"].fillna(0).to_numpy() / 60
        ax.bar(au.sample_id.str[-5:], v, bottom=bottom, color=c, label=st); bottom += v
    ax.set_ylabel("wall-clock hours"); ax.set_title("GATK RNA-seq calling: wall-clock time per run"); ax.legend(fontsize=8); ax.tick_params(axis="x", rotation=60)
    fig.tight_layout(); fig.savefig(out / "figures" / "D_gatk_runtime.png", dpi=300); plt.close(fig)

    results["union_pass_loci"] = int(U)
    results["donor_structure"] = donor_df.to_dict(orient="records")
    (out / "light_01_results.json").write_text(json.dumps(results, indent=2, default=float), encoding="utf-8")
    print(json.dumps({k: v for k, v in results.items() if k != "donor_structure"}, indent=1, default=float))
    print(ident_df.to_string(index=False))
    print(comp_df.to_string(index=False))
    print(per_df.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
