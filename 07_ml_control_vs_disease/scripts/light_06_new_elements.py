#!/usr/bin/env python3
"""One new pipeline element per article, each absent from the IJMS design (LR, BA/ROC-AUC, GSM-LOGO, exact 35-labeling test).

  norm   (NAN RK) coverage-normalised gene burden: burden / PASS calls of the run x 1e5; logistic regression as in IJMS.
  brier  (KBTU)   Brier score of sample-level probabilities with an exact 35-labeling null, for the six benchmark models;
                  also scores the elastic-net model used by ARU.
  human-en (ARU)  elastic-net logistic regression in the three-design benchmark (human, three feature sets).
  mouse-en (ARU)  the same model in the GSE243129 benchmark.

Run in the benchmark environment (.envs/ml-benchmark: scikit-learn 1.9.0, xgboost 3.2.0)."""
from __future__ import annotations

import argparse
import itertools
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy import sparse, stats
from sklearn.base import clone
from sklearn.feature_selection import VarianceThreshold
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).parent))
import light_03_exact_null as L3  # noqa: E402
from run_combined_three_design_benchmark import model_templates  # noqa: E402

warnings.filterwarnings("ignore")
EN_NAME = "Elastic-net logistic regression"


def elastic_net(seed: int, with_mean: bool = True) -> Pipeline:
    return Pipeline([("var", VarianceThreshold()), ("scale", StandardScaler(with_mean=with_mean)),
                     ("clf", LogisticRegression(l1_ratio=0.5, solver="saga", C=0.1, tol=1e-4, class_weight="balanced", max_iter=20000, random_state=seed))])
# C = 0.1 was fixed before any validation (convergence check on the full human matrix: 39 of 27,230 genes non-zero, converged);
# C = 1.0 did not converge within 5,000 saga iterations, C <= 0.05 removed every feature.


def lr_ijms(seed: int) -> Pipeline:
    return model_templates(seed, 1)["Logistic regression (L2)"]


# ---------------------------------------------------------------- shared human inputs
def load_human(cache_dir: Path, analysis_dir: Path, min_samples=4, min_vaf=0.05):
    meta = pd.read_csv(analysis_dir / "metadata.cleaned.tsv", sep="\t")
    samples, gsm = meta.sample_id.tolist(), meta.gsm.tolist()
    obs_wound = frozenset(meta[meta.condition == "wound"].gsm)
    caches = [dict(np.load(cache_dir / f"{s}.npz")) for s in samples]
    union = np.unique(np.concatenate([c["key"] for c in caches]))
    vg = pd.read_csv(analysis_dir / "variant_to_gene" / "variant_gene_long.tsv", sep="\t", usecols=["chrom", "pos", "ref", "alt", "gene_id"]).drop_duplicates()
    vk = np.array([L3.enc(*r) for r in vg[["chrom", "pos", "ref", "alt"]].itertuples(index=False)], dtype=np.int64)
    ui = np.searchsorted(union, vk)
    genes, gi = np.unique(vg.gene_id.to_numpy(), return_inverse=True)
    Lm = sparse.csr_matrix((np.ones(len(ui), dtype=np.float32), (ui, gi)), shape=(len(union), len(genes))); Lm.data[:] = 1.0
    comb = pd.read_csv(analysis_dir / "feature_set_comparison" / "combined_gatk_variant_plus_expression_matrix.tsv", sep="\t")
    ids = comb.gene_id.astype(str)
    Xglob = comb[ids.str.startswith("gatk_variant__")][samples].T.to_numpy(np.float32)
    Xexpr = comb[ids.str.startswith("expression__")][samples].T.to_numpy(np.float32)

    def logo(groups):
        return [(np.array([i for i, g in enumerate(groups) if g != h]), np.array([i for i, g in enumerate(groups) if g == h])) for h in sorted(set(groups))]
    gsm_folds = logo(gsm)
    person = [L3.SAME_PERSON.get(g, g) for g in gsm]
    person_folds = logo(person)
    gsm_mats = [L3.build_training_only(caches, union, Lm, tr, min_samples, min_vaf)[0] for tr, _ in gsm_folds]
    person_mats = [L3.build_training_only(caches, union, Lm, tr, min_samples, min_vaf)[0] for tr, _ in person_folds]
    return dict(meta=meta, samples=samples, gsm=gsm, obs_wound=obs_wound, Xglob=Xglob, Xexpr=Xexpr,
                gsm_folds=gsm_folds, person_folds=person_folds, gsm_mats=gsm_mats, person_mats=person_mats)


def eval_labeling(lab_id, wound_set, designs, gsm, templates):
    """Like light_03.eval_labeling, but also keeps sample-level probabilities (for the Brier score)."""
    y = np.array([1 if g in wound_set else 0 for g in gsm])
    g_arr = np.asarray(gsm)
    out = []
    for dname, (folds, mats) in designs.items():
        for mname, tmpl in templates.items():
            gt, gp, gprob, gid = [], [], [], []
            for (train, test), X in zip(folds, mats):
                if len(set(y[train])) < 2:
                    continue
                prob = clone(tmpl).fit(X[train], y[train]).predict_proba(X[test])[:, 1]
                for g in sorted(set(g_arr[test])):
                    pr = float(prob[g_arr[test] == g].mean())
                    gt.append(int(g in wound_set)); gprob.append(pr); gp.append(int(pr >= 0.5)); gid.append(g)
            gt_a, pr_a = np.array(gt), np.array(gprob)
            out.append({"labeling": lab_id, "wound_gsms": "|".join(sorted(wound_set)), "design": dname, "model": mname,
                        "balanced_accuracy": balanced_accuracy_score(gt, gp),
                        "roc_auc": roc_auc_score(gt, gprob) if len(set(gt)) > 1 else np.nan,
                        "brier": float(np.mean((pr_a - gt_a) ** 2)),
                        "probs": "|".join(f"{g}:{p:.6f}" for g, p in zip(gid, gprob))})
    return out


def exact_summary(df: pd.DataFrame, obs_key: str) -> pd.DataFrame:
    df["is_observed"] = df.wound_gsms == obs_key
    rows = []
    for (d, m), part in df.groupby(["design", "model"], sort=False):
        o = part[part.is_observed].iloc[0]
        rows.append({"design": d, "model": m, "observed_BA": o.balanced_accuracy, "exact_p_BA": float(np.mean(part.balanced_accuracy >= o.balanced_accuracy - 1e-12)),
                     "observed_AUC": o.roc_auc, "exact_p_AUC": float(np.mean(part.roc_auc >= o.roc_auc - 1e-12)),
                     "observed_brier": o.brier, "exact_p_brier": float(np.mean(part.brier <= o.brier + 1e-12)),
                     "null_brier_mean": part.brier.mean(), "null_BA_mean": part.balanced_accuracy.mean(), "n_labelings": len(part)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- KBTU: Brier score (+ elastic net for ARU)
def cmd_brier(a):
    H = load_human(a.cache_dir, a.analysis_dir)
    designs = {
        "GSM-LOGO, global loci (mutation)": (H["gsm_folds"], [H["Xglob"]] * 7),
        "GSM-LOGO, training-only loci (mutation)": (H["gsm_folds"], H["gsm_mats"]),
        "Person-LOGO, training-only loci (mutation)": (H["person_folds"], H["person_mats"]),
        "GSM-LOGO, expression only": (H["gsm_folds"], [H["Xexpr"]] * 7),
    }
    templates = model_templates(42, 1)
    templates[EN_NAME] = elastic_net(42)
    labelings = [frozenset(c) for c in itertools.combinations(sorted(set(H["gsm"])), 3)]
    res = Parallel(n_jobs=a.jobs, verbose=5)(delayed(eval_labeling)(i, ws, designs, H["gsm"], templates) for i, ws in enumerate(labelings))
    df = pd.DataFrame([r for chunk in res for r in chunk])
    summ = exact_summary(df, "|".join(sorted(H["obs_wound"])))
    df.to_csv(a.outdir / "H_brier_all_labelings.tsv", sep="\t", index=False)
    summ.to_csv(a.outdir / "H_brier_exact_summary.tsv", sep="\t", index=False)
    # reproduction check against light_03 (balanced accuracy must be identical for the six benchmark models)
    ref = pd.read_csv(a.outdir / "F_exact_null_summary.tsv", sep="\t")
    chk = summ.merge(ref[["design", "model", "observed_BA", "exact_p_BA"]], on=["design", "model"], suffixes=("", "_light03"))
    bad = chk[(abs(chk.observed_BA - chk.observed_BA_light03) > 1e-9) | (abs(chk.exact_p_BA - chk.exact_p_BA_light03) > 1e-9)]
    print("reproduction of light_03:", "OK" if bad.empty else f"MISMATCH\n{bad}")
    pd.set_option("display.width", 250)
    print(summ.to_string(index=False))


# ---------------------------------------------------------------- NAN RK: coverage-normalised burden
def cmd_norm(a):
    H = load_human(a.cache_dir, a.analysis_dir)
    cov = pd.read_csv(a.outdir / "C_per_run_calls_vs_coverage.tsv", sep="\t").set_index("sample_id").loc[H["samples"]]
    scale = (1e5 / cov.n_pass.to_numpy(np.float64))[:, None].astype(np.float32)
    rows = []
    # (1) dependence of the features on coverage, raw vs normalised
    for label, X in [("raw", H["Xglob"]), ("normalised", H["Xglob"] * scale)]:
        tot = X.sum(axis=1)
        r_dp = stats.spearmanr(tot, cov.median_dp).correlation
        r_genes = stats.spearmanr(tot, cov.detected_genes).correlation
        # per-gene correlation with depth (genes non-constant across runs)
        keep = X.std(axis=0) > 0
        rg = np.array([stats.spearmanr(X[:, j], cov.median_dp).correlation for j in np.flatnonzero(keep)])
        # 1-NN sample identification on standardised features (Euclidean)
        Z = StandardScaler().fit_transform(X[:, keep])
        D = ((Z[:, None, :] - Z[None, :, :]) ** 2).sum(-1); np.fill_diagonal(D, np.inf)
        nn = np.argmin(D, axis=1)
        id_acc = float(np.mean([H["gsm"][i] == H["gsm"][nn[i]] for i in range(len(nn))]))
        rows.append({"features": label, "rho_total_vs_median_depth": r_dp, "rho_total_vs_detected_genes": r_genes,
                     "median_abs_rho_gene_vs_depth": float(np.nanmedian(np.abs(rg))), "share_genes_abs_rho_ge_0.5": float(np.nanmean(np.abs(rg) >= 0.5)),
                     "nn_sample_identification": id_acc})
    pd.DataFrame(rows).to_csv(a.outdir / "I_norm_coverage_dependence.tsv", sep="\t", index=False)
    print(pd.DataFrame(rows).to_string(index=False))
    # (2) the IJMS model (L2 logistic regression) on raw and normalised burden, exact 35-labeling test
    designs = {}
    for label, f in [("raw", lambda X: X), ("normalised", lambda X: X * scale)]:
        designs[f"GSM-LOGO, global loci, {label}"] = (H["gsm_folds"], [f(H["Xglob"])] * 7)
        designs[f"GSM-LOGO, training-only loci, {label}"] = (H["gsm_folds"], [f(X) for X in H["gsm_mats"]])
        designs[f"Person-LOGO, training-only loci, {label}"] = (H["person_folds"], [f(X) for X in H["person_mats"]])
    templates = {"Logistic regression (L2)": lr_ijms(42)}
    labelings = [frozenset(c) for c in itertools.combinations(sorted(set(H["gsm"])), 3)]
    res = Parallel(n_jobs=a.jobs, verbose=2)(delayed(eval_labeling)(i, ws, designs, H["gsm"], templates) for i, ws in enumerate(labelings))
    df = pd.DataFrame([r for chunk in res for r in chunk])
    summ = exact_summary(df, "|".join(sorted(H["obs_wound"])))
    df.to_csv(a.outdir / "I_norm_all_labelings.tsv", sep="\t", index=False)
    summ.to_csv(a.outdir / "I_norm_exact_summary.tsv", sep="\t", index=False)
    print(summ.to_string(index=False))


# ---------------------------------------------------------------- ARU: elastic net, human three-design benchmark
def cmd_human_en(a):
    import run_combined_three_design_benchmark as B
    B.model_templates = lambda seed, jobs: {EN_NAME: elastic_net(seed)}
    root = a.analysis_dir
    sys.argv = ["bench", "--combined-matrix", str(root / "feature_set_comparison" / "combined_gatk_variant_plus_expression_matrix.tsv"),
                "--metadata", str(root / "metadata.cleaned.tsv"), "--vcf-dir", str(root / "input_pass_vcfs"),
                "--variant-gene-tsv", str(root / "variant_to_gene" / "variant_gene_long.tsv"),
                "--outdir", str(a.outdir / "J_elastic_net_human"), "--jobs", str(a.jobs)]
    return B.main()


def cmd_human_en_cv(a):
    """Run-level repeated stratified CV (5 x 30, random_state 42, as in the benchmark) on mutation features, in parallel.
    The L2 logistic regression is run alongside as a reproduction check of the published 0.973."""
    from sklearn.model_selection import RepeatedStratifiedKFold
    from sklearn.metrics import accuracy_score
    root = a.analysis_dir
    meta = pd.read_csv(root / "metadata.cleaned.tsv", sep="\t"); samples = meta.sample_id.tolist()
    comb = pd.read_csv(root / "feature_set_comparison" / "combined_gatk_variant_plus_expression_matrix.tsv", sep="\t")
    X = comb[comb.gene_id.astype(str).str.startswith("gatk_variant__")][samples].T.to_numpy(np.float32)
    y = (meta.condition == "wound").astype(int).to_numpy()
    splits = list(RepeatedStratifiedKFold(n_splits=5, n_repeats=30, random_state=42).split(X, y))
    templates = {"Logistic regression (L2)": lr_ijms(42), EN_NAME: elastic_net(42)}

    def one(name, k, tr, te):
        m = clone(templates[name]).fit(X[tr], y[tr])
        prob = m.predict_proba(X[te])[:, 1]; pred = (prob >= 0.5).astype(int) if name == EN_NAME else m.predict(X[te])
        n_nonzero = int((m.named_steps["clf"].coef_ != 0).sum())
        return {"model": name, "fold": k, "balanced_accuracy": balanced_accuracy_score(y[te], pred),
                "roc_auc": roc_auc_score(y[te], prob) if len(set(y[te])) > 1 else np.nan, "n_nonzero_coef": n_nonzero,
                "n_iter": int(np.max(m.named_steps["clf"].n_iter_))}
    rows = Parallel(n_jobs=a.jobs, verbose=2)(delayed(one)(n, k, tr, te) for n in templates for k, (tr, te) in enumerate(splits, 1))
    df = pd.DataFrame(rows)
    df.to_csv(a.outdir / "J_elastic_net_human_srr_cv_folds.tsv", sep="\t", index=False)
    s = df.groupby("model").agg(ba_mean=("balanced_accuracy", "mean"), ba_sd=("balanced_accuracy", "std"), auc_mean=("roc_auc", "mean"),
                                nonzero_median=("n_nonzero_coef", "median"), max_iter_used=("n_iter", "max")).reset_index()
    s.to_csv(a.outdir / "J_elastic_net_human_srr_cv_summary.tsv", sep="\t", index=False)
    print(s.to_string(index=False))


def cmd_mouse_en_par(a):
    """GSE243129 benchmark for the elastic net, parallel over folds; same splits and data as
    run_full_hypotheses_all_models.py. L2 logistic regression is run alongside as a reproduction check."""
    from sklearn.model_selection import LeaveOneGroupOut, RepeatedStratifiedKFold
    mouse = Path(a.mouse_dir); sys.path.insert(0, str(mouse))
    from run_validation import matrix_for, read_variants, recurrent_loci
    from run_validation_all_models import models as mouse_models
    md = pd.read_csv(mouse / "metadata.tsv", sep="\t", dtype=str)
    run_ids = md.run_id.tolist(); groups = md.gsm.to_numpy(); y = (md.condition.to_numpy() == "hyperoxia").astype(int)
    expr = pd.read_csv(mouse / "outputs" / "full_hypotheses" / "features" / "expression_log1p_cpm.tsv", sep="\t", index_col="run_id")
    x_exp = expr.loc[run_ids].to_numpy(dtype=np.float32)
    run_sets = {r: read_variants(mouse / "outputs" / "vcf" / f"{r}.filtered.vcf.gz") for r in run_ids}
    x_var = matrix_for(run_ids, recurrent_loci(run_sets, md, set(groups), 2), run_sets)
    glob = {"EXP": x_exp, "VAR": x_var, "COMBINED": np.hstack([x_exp, x_var])}
    cv = list(RepeatedStratifiedKFold(n_splits=4, n_repeats=30, random_state=42).split(x_exp, y))
    logo = list(LeaveOneGroupOut().split(x_exp, y, groups))
    train_mats = []
    for tr, te in logo:
        fv = matrix_for(run_ids, recurrent_loci(run_sets, md, set(groups[tr]), 2), run_sets)
        train_mats.append({"VAR": fv, "COMBINED": np.hstack([x_exp, fv])})
    templates = {"Logistic regression (L2)": mouse_models(42, 1)["Logistic regression (L2)"], EN_NAME: elastic_net(42, with_mean=False)}
    jobs = []
    for name in templates:
        for fs in ["EXP", "VAR", "COMBINED"]:
            jobs += [(name, "SRR-level repeated CV", fs, k, tr, te, glob[fs]) for k, (tr, te) in enumerate(cv, 1)]
            jobs += [(name, "GSM-LOGO global loci", fs, k, tr, te, glob[fs]) for k, (tr, te) in enumerate(logo, 1)]
            if fs != "EXP":
                jobs += [(name, "GSM-LOGO training-only loci", fs, k, tr, te, train_mats[k - 1][fs]) for k, (tr, te) in enumerate(logo, 1)]

    def one(name, design, fs, k, tr, te, X):
        m = clone(templates[name]).fit(X[tr], y[tr])
        prob = m.predict_proba(X[te])[:, 1]
        return {"model": name, "design": design, "feature_space": fs, "fold": k, "test_idx": list(map(int, te)),
                "prob": list(map(float, prob)), "pred": list(map(int, m.predict(X[te]))), "n_iter": int(np.max(m.named_steps["clf"].n_iter_)),
                "n_nonzero": int((m.named_steps["clf"].coef_ != 0).sum())}
    res = Parallel(n_jobs=a.jobs, verbose=2)(delayed(one)(*j) for j in jobs)
    rows = []
    df = pd.DataFrame(res)
    for (name, design, fs), part in df.groupby(["model", "design", "feature_space"], sort=False):
        if design.startswith("SRR"):
            bas = [balanced_accuracy_score(y[t], p) for t, p in zip(part.test_idx, part.pred)]
            aucs = [roc_auc_score(y[t], pr) for t, pr in zip(part.test_idx, part.prob)]
            rows.append({"model": name, "design": design, "feature_space": fs, "balanced_accuracy": np.mean(bas), "ba_sd": np.std(bas, ddof=1), "roc_auc": np.mean(aucs)})
        else:
            gt = [int(y[t[0]]) for t in part.test_idx]; gp_ = [float(np.mean(p)) for p in part.prob]
            rows.append({"model": name, "design": design, "feature_space": fs, "balanced_accuracy": balanced_accuracy_score(gt, [int(p >= 0.5) for p in gp_]),
                         "ba_sd": np.nan, "roc_auc": roc_auc_score(gt, gp_)})
        rows[-1].update({"median_nonzero": float(part.n_nonzero.median()), "max_iter_used": int(part.n_iter.max())})
    out = pd.DataFrame(rows)
    out.to_csv(a.outdir / "J_elastic_net_mouse_summary.tsv", sep="\t", index=False)
    print(out.to_string(index=False))


def cmd_mouse_en(a):
    from sklearn.exceptions import ConvergenceWarning
    warnings.simplefilter("default", ConvergenceWarning)  # make non-convergence visible in the log
    mouse = Path(a.mouse_dir)
    sys.path.insert(0, str(mouse))
    import run_full_hypotheses_all_models as M
    from sklearn.feature_selection import VarianceThreshold as VT  # noqa: F401
    M.models = lambda seed, jobs: {EN_NAME: elastic_net(seed, with_mean=False)}
    sys.argv = ["mouse", "--metadata", str(mouse / "metadata.tsv"), "--vcf-dir", str(mouse / "outputs" / "vcf"),
                "--expression", str(mouse / "outputs" / "full_hypotheses" / "features" / "expression_log1p_cpm.tsv"),
                "--outdir", str(a.outdir / "J_elastic_net_mouse"), "--jobs", str(a.jobs)]
    return M.main()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["brier", "norm", "human-en", "human-en-cv", "mouse-en", "mouse-en-par"])
    ap.add_argument("--cache-dir", type=Path)
    ap.add_argument("--analysis-dir", type=Path)
    ap.add_argument("--mouse-dir", type=Path)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=18)
    a = ap.parse_args()
    {"brier": cmd_brier, "norm": cmd_norm, "human-en": cmd_human_en, "human-en-cv": cmd_human_en_cv, "mouse-en": cmd_mouse_en, "mouse-en-par": cmd_mouse_en_par}[a.command](a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
