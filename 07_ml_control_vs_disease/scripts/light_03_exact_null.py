#!/usr/bin/env python3
"""Exact label-permutation null for grouped validation.

With 7 GSM groups (4 unwounded / 3 wound) there are C(7,3) = 35 possible group
labelings. Feature construction is label-free in every design used here
(global cohort loci; training-only recurrent loci selected by support/VAF only;
expression log1p CPM), so each fold's features are built once and every model is
refit under all 35 labelings. The observed GEO labeling is one of the 35, giving
an exact p-value with resolution 1/35.

Designs:
  GSM-LOGO / global loci        (7 folds, mutation features from the global cohort filter)
  GSM-LOGO / training-only loci (7 folds, loci re-selected from training runs only)
  Person-LOGO / training-only   (6 folds; GSM5364333 Sc_Skin1 + GSM5364338 Sc_W2 held out
                                 together because genotype concordance identifies one person)
  GSM-LOGO / expression-only    (7 folds)
Held-out run probabilities are averaged per GSM, as in the benchmark.
"""
from __future__ import annotations

import argparse
import itertools
import json
import warnings
import zlib
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy import sparse
from sklearn.base import clone
from sklearn.metrics import balanced_accuracy_score, roc_auc_score

import sys
sys.path.insert(0, str(Path(__file__).parent))
from run_combined_three_design_benchmark import model_templates  # noqa: E402

warnings.filterwarnings("ignore")
CHROMS = [f"chr{c}" for c in list(range(1, 23)) + ["X", "Y", "M"]]
CHROM_INDEX = {c: i + 1 for i, c in enumerate(CHROMS)}
SAME_PERSON = {"GSM5364333": "P_Skin1_W2", "GSM5364338": "P_Skin1_W2"}


def enc(chrom, pos, ref, alt):
    idx = CHROM_INDEX.get(chrom, 100 + (zlib.crc32(chrom.encode()) % 27))
    return (idx << 56) | (int(pos) << 24) | (zlib.crc32(f"{ref}>{alt}".encode()) & 0xFFFFFF)


def build_training_only(caches, union, L, train_idx, min_samples, min_vaf):
    U = len(union)
    support = np.zeros(U, dtype=np.int16)
    maxvaf = np.zeros(U, dtype=np.float32)
    pos = [np.searchsorted(union, c["key"]) for c in caches]
    for i in train_idx:
        support[pos[i]] += 1
        np.maximum.at(maxvaf, pos[i], caches[i]["vaf"])
    sel = (support >= min_samples) & (maxvaf >= min_vaf)
    rows = []
    for i in range(len(caches)):
        v = np.zeros(U, dtype=np.float32)
        p = pos[i][sel[pos[i]]]
        v[p] = 1.0
        rows.append(v)
    P = sparse.csr_matrix(np.vstack(rows))
    X = (P @ L).toarray()
    keep = np.asarray((L[np.flatnonzero(sel)].sum(axis=0) > 0)).ravel()
    return X[:, keep].astype(np.float32), int(sel.sum()), int(keep.sum())


def eval_labeling(lab_id, wound_set, designs, gsm, templates):
    y = np.array([1 if g in wound_set else 0 for g in gsm])
    out = []
    for dname, (folds, mats) in designs.items():
        for mname, tmpl in templates.items():
            gt, gp, gprob = [], [], []
            for (train, test), X in zip(folds, mats):
                if len(set(y[train])) < 2:
                    continue
                m = clone(tmpl).fit(X[train], y[train])
                prob = m.predict_proba(X[test])[:, 1]
                for g in sorted(set(np.asarray(gsm)[test])):
                    msk = np.asarray(gsm)[test] == g
                    pr = float(prob[msk].mean())
                    gt.append(int(g in wound_set)); gprob.append(pr); gp.append(int(pr >= 0.5))
            out.append({"labeling": lab_id, "wound_gsms": "|".join(sorted(wound_set)), "design": dname, "model": mname,
                        "balanced_accuracy": balanced_accuracy_score(gt, gp), "roc_auc": roc_auc_score(gt, gprob) if len(set(gt)) > 1 else np.nan,
                        "n_groups_scored": len(gt)})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache-dir", type=Path, required=True)
    ap.add_argument("--analysis-dir", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--min-samples", type=int, default=4)
    ap.add_argument("--min-vaf", type=float, default=0.05)
    ap.add_argument("--jobs", type=int, default=18)
    a = ap.parse_args()
    out = a.outdir; (out / "figures").mkdir(parents=True, exist_ok=True)

    meta = pd.read_csv(a.analysis_dir / "metadata.cleaned.tsv", sep="\t")
    samples = meta.sample_id.tolist(); gsm = meta.gsm.tolist(); title = meta.sample_title.tolist()
    obs_wound = frozenset(meta[meta.condition == "wound"].gsm)
    caches = [dict(np.load(a.cache_dir / f"{s}.npz")) for s in samples]
    union = np.unique(np.concatenate([c["key"] for c in caches]))

    vg = pd.read_csv(a.analysis_dir / "variant_to_gene" / "variant_gene_long.tsv", sep="\t", usecols=["chrom", "pos", "ref", "alt", "gene_id"]).drop_duplicates()
    vk = np.array([enc(*r) for r in vg[["chrom", "pos", "ref", "alt"]].itertuples(index=False)], dtype=np.int64)
    ui = np.searchsorted(union, vk)
    genes, gi = np.unique(vg.gene_id.to_numpy(), return_inverse=True)
    L = sparse.csr_matrix((np.ones(len(ui), dtype=np.float32), (ui, gi)), shape=(len(union), len(genes)))
    L.data[:] = 1.0  # one count per locus-gene pair

    comb = pd.read_csv(a.analysis_dir / "feature_set_comparison" / "combined_gatk_variant_plus_expression_matrix.tsv", sep="\t")
    ids = comb.gene_id.astype(str)
    Xglob = comb[ids.str.startswith("gatk_variant__")][samples].T.to_numpy(np.float32)
    Xexpr = comb[ids.str.startswith("expression__")][samples].T.to_numpy(np.float32)

    def logo(groups):
        gs = sorted(set(groups))
        return [(np.array([i for i, g in enumerate(groups) if g != h]), np.array([i for i, g in enumerate(groups) if g == h])) for h in gs]

    gsm_folds = logo(gsm)
    person = [SAME_PERSON.get(g, g) for g in gsm]
    person_folds = logo(person)

    counts = []
    gsm_mats = []
    for k, (tr, te) in enumerate(gsm_folds, 1):
        X, nl, ng = build_training_only(caches, union, L, tr, a.min_samples, a.min_vaf)
        gsm_mats.append(X); counts.append({"design": "GSM-LOGO", "fold": k, "heldout": gsm[te[0]], "n_recurrent_loci": nl, "n_genes": ng})
        print(f"GSM fold {k}: loci={nl} genes={ng}", flush=True)
    person_mats = []
    for k, (tr, te) in enumerate(person_folds, 1):
        X, nl, ng = build_training_only(caches, union, L, tr, a.min_samples, a.min_vaf)
        person_mats.append(X); counts.append({"design": "Person-LOGO", "fold": k, "heldout": person[te[0]], "n_recurrent_loci": nl, "n_genes": ng})
        print(f"Person fold {k}: loci={nl} genes={ng}", flush=True)
    pd.DataFrame(counts).to_csv(out / "F_training_only_fold_counts.tsv", sep="\t", index=False)

    designs = {
        "GSM-LOGO, global loci (mutation)": (gsm_folds, [Xglob] * len(gsm_folds)),
        "GSM-LOGO, training-only loci (mutation)": (gsm_folds, gsm_mats),
        "Person-LOGO, training-only loci (mutation)": (person_folds, person_mats),
        "GSM-LOGO, expression only": (gsm_folds, [Xexpr] * len(gsm_folds)),
    }
    templates = model_templates(42, 1)
    labelings = [frozenset(c) for c in itertools.combinations(sorted(set(gsm)), 3)]
    res = Parallel(n_jobs=a.jobs, verbose=5)(delayed(eval_labeling)(i, ws, designs, gsm, templates) for i, ws in enumerate(labelings))
    df = pd.DataFrame([r for chunk in res for r in chunk])
    df["is_observed"] = df.wound_gsms == "|".join(sorted(obs_wound))
    df.to_csv(out / "F_exact_null_all_labelings.tsv", sep="\t", index=False)

    summ = []
    for (d, m), part in df.groupby(["design", "model"], sort=False):
        o = part[part.is_observed].iloc[0]
        summ.append({"design": d, "model": m, "observed_BA": o.balanced_accuracy, "observed_AUC": o.roc_auc,
                     "exact_p_BA": float(np.mean(part.balanced_accuracy >= o.balanced_accuracy - 1e-12)),
                     "null_BA_mean": part.balanced_accuracy.mean(), "null_BA_q95": part.balanced_accuracy.quantile(0.95),
                     "null_frac_BA_ge_0.75": float(np.mean(part.balanced_accuracy >= 0.75)),
                     "null_frac_BA_eq_1": float(np.mean(part.balanced_accuracy >= 1 - 1e-12)),
                     "n_labelings": len(part)})
    summ_df = pd.DataFrame(summ)
    summ_df.to_csv(out / "F_exact_null_summary.tsv", sep="\t", index=False)
    pd.set_option("display.width", 220)
    print(summ_df.to_string(index=False))

    dn = list(designs)
    fig, axes = plt.subplots(1, len(dn), figsize=(20, 5.2), sharey=True)
    models = list(templates)
    for ax, d in zip(axes, dn):
        part = df[df.design == d]
        for k, m in enumerate(models):
            v = part[(part.model == m) & ~part.is_observed].balanced_accuracy.to_numpy()
            ax.scatter(np.full(len(v), k) + np.random.default_rng(k).uniform(-0.18, 0.18, len(v)), v, s=10, color="#9a9a9a", alpha=0.6)
            o = part[(part.model == m) & part.is_observed].balanced_accuracy.iloc[0]
            ax.scatter([k], [o], s=70, color="#d06b36", marker="D", zorder=3)
        ax.axhline(0.5, ls="--", color="#8b1e1e", lw=1)
        ax.set_xticks(range(len(models)), [m.split(" (")[0] for m in models], rotation=45, ha="right", fontsize=8)
        ax.set_title(d, fontsize=10); ax.grid(axis="y", alpha=0.2)
    axes[0].set_ylabel("Balanced accuracy (group level)")
    fig.suptitle("Exact null: all 35 group labelings (grey) vs GEO labeling (orange)")
    fig.tight_layout(); fig.savefig(out / "figures" / "F_exact_null.png", dpi=300); plt.close(fig)

    (out / "F_manifest.json").write_text(json.dumps({"n_labelings": len(labelings), "observed_wound_gsms": sorted(obs_wound),
        "same_person_grouping": SAME_PERSON, "min_samples": a.min_samples, "min_vaf": a.min_vaf, "models": models,
        "designs": dn, "min_attainable_p": 1 / len(labelings)}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
