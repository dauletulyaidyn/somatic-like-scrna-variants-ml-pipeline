#!/usr/bin/env python3
"""Per-run and per-sample held-out predictions under the observed (GEO) labeling for the four
grouped designs of light_03 (same folds, same models). Run in the benchmark environment."""
from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone

import sys
sys.path.insert(0, str(Path(__file__).parent))
from run_combined_three_design_benchmark import model_templates  # noqa: E402
import light_03_exact_null as L3  # noqa: E402

warnings.filterwarnings("ignore")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache-dir", type=Path, required=True)
    ap.add_argument("--analysis-dir", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    a = ap.parse_args()
    meta = pd.read_csv(a.analysis_dir / "metadata.cleaned.tsv", sep="\t")
    samples, gsm = meta.sample_id.tolist(), meta.gsm.tolist()
    y = (meta.condition == "wound").astype(int).to_numpy()
    caches = [dict(np.load(a.cache_dir / f"{s}.npz")) for s in samples]
    union = np.unique(np.concatenate([c["key"] for c in caches]))
    vg = pd.read_csv(a.analysis_dir / "variant_to_gene" / "variant_gene_long.tsv", sep="\t", usecols=["chrom", "pos", "ref", "alt", "gene_id"]).drop_duplicates()
    vk = np.array([L3.enc(*r) for r in vg[["chrom", "pos", "ref", "alt"]].itertuples(index=False)], dtype=np.int64)
    from scipy import sparse
    ui = np.searchsorted(union, vk)
    genes, gi = np.unique(vg.gene_id.to_numpy(), return_inverse=True)
    Lm = sparse.csr_matrix((np.ones(len(ui), dtype=np.float32), (ui, gi)), shape=(len(union), len(genes))); Lm.data[:] = 1.0
    comb = pd.read_csv(a.analysis_dir / "feature_set_comparison" / "combined_gatk_variant_plus_expression_matrix.tsv", sep="\t")
    ids = comb.gene_id.astype(str)
    Xglob = comb[ids.str.startswith("gatk_variant__")][samples].T.to_numpy(np.float32)
    Xexpr = comb[ids.str.startswith("expression__")][samples].T.to_numpy(np.float32)

    def logo(groups):
        return [(np.array([i for i, g in enumerate(groups) if g != h]), np.array([i for i, g in enumerate(groups) if g == h])) for h in sorted(set(groups))]
    gsm_folds = logo(gsm)
    person = [L3.SAME_PERSON.get(g, g) for g in gsm]
    person_folds = logo(person)
    gsm_mats = [L3.build_training_only(caches, union, Lm, tr, 4, 0.05)[0] for tr, _ in gsm_folds]
    person_mats = [L3.build_training_only(caches, union, Lm, tr, 4, 0.05)[0] for tr, _ in person_folds]
    designs = {
        "GSM-LOGO, global loci (mutation)": (gsm_folds, [Xglob] * 7),
        "GSM-LOGO, training-only loci (mutation)": (gsm_folds, gsm_mats),
        "Person-LOGO, training-only loci (mutation)": (person_folds, person_mats),
        "GSM-LOGO, expression only": (gsm_folds, [Xexpr] * 7),
    }
    rows = []
    for dname, (folds, mats) in designs.items():
        for mname, tmpl in model_templates(42, 1).items():
            for k, ((tr, te), X) in enumerate(zip(folds, mats), 1):
                prob = clone(tmpl).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
                for idx, p in zip(te, prob):
                    rows.append({"design": dname, "model": mname, "fold": k, "sample_id": samples[idx], "gsm": gsm[idx],
                                 "true_label": int(y[idx]), "prob_wound_run": float(p)})
    df = pd.DataFrame(rows)
    g = df.groupby(["design", "model", "gsm"], sort=False).agg(true_label=("true_label", "first"), prob_wound_sample=("prob_wound_run", "mean")).reset_index()
    g["predicted_label"] = (g.prob_wound_sample >= 0.5).astype(int)
    df.to_csv(a.outdir / "F_observed_run_predictions.tsv", sep="\t", index=False)
    g.to_csv(a.outdir / "F_observed_sample_predictions.tsv", sep="\t", index=False)
    print(g.groupby(["design", "model"], sort=False).apply(lambda x: (x.predicted_label == x.true_label).mean()).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
