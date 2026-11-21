#!/usr/bin/env python3
"""Genotype-based sample identity check on high-confidence shared calls.
For each run pair: among loci called in both runs with FORMAT DP >= min_dp in both,
fraction with identical genotype class (het vs hom-alt); plus Jaccard of DP>=min_dp calls.
Ranks all between-GSM pairs to see whether any pair of different GSMs behaves like one person."""
import argparse, itertools, sys
from pathlib import Path
import numpy as np, pandas as pd

ap = argparse.ArgumentParser(); ap.add_argument("--cache-dir", type=Path); ap.add_argument("--metadata", type=Path)
ap.add_argument("--outdir", type=Path); ap.add_argument("--min-dp", type=int, nargs="+", default=[10, 20])
a = ap.parse_args()
meta = pd.read_csv(a.metadata, sep="\t"); S = meta.sample_id.tolist(); T = meta.sample_title.tolist(); G = meta.gsm.tolist()
C = {s: np.load(a.cache_dir / f"{s}.npz") for s in S}
rows = []
for md in a.min_dp:
    hc = {}
    for s in S:
        c = C[s]; m = c["dp"] >= md
        hc[s] = (c["key"][m], c["is_hom"][m])
    for i, j in itertools.combinations(range(len(S)), 2):
        ki, hi = hc[S[i]]; kj, hj = hc[S[j]]
        common, ii, jj = np.intersect1d(ki, kj, assume_unique=True, return_indices=True)
        conc = float(np.mean(hi[ii] == hj[jj])) if len(common) else np.nan
        hom_both = float(np.mean(hi[ii] & hj[jj]))
        # discordant hom-alt: hom in one, het in other
        rows.append({"min_dp": md, "run_a": S[i], "run_b": S[j], "title_a": T[i], "title_b": T[j],
                     "same_gsm": G[i] == G[j], "n_shared_hc": len(common),
                     "jaccard_hc": len(common) / (len(ki) + len(kj) - len(common)),
                     "gt_concordance_hc": conc, "frac_both_hom": hom_both})
df = pd.DataFrame(rows)
df["donor_pair"] = df.apply(lambda r: " vs ".join(sorted([r.title_a, r.title_b])), axis=1)
df.to_csv(a.outdir / "E_identity_check_pairs.tsv", sep="\t", index=False)
summ = df.groupby(["min_dp", "donor_pair", "same_gsm"])[["jaccard_hc", "gt_concordance_hc", "n_shared_hc"]].mean().reset_index()
summ = summ.sort_values(["min_dp", "gt_concordance_hc"], ascending=[True, False])
summ.to_csv(a.outdir / "E_identity_check_donor_pairs.tsv", sep="\t", index=False)
pd.set_option("display.width", 200)
for md in a.min_dp:
    print(f"--- DP >= {md}: top donor pairs by genotype concordance")
    print(summ[summ.min_dp == md].head(12).to_string(index=False))
