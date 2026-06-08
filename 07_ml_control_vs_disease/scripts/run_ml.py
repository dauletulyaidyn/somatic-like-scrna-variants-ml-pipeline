#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.feature_selection import VarianceThreshold
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def load_data(feature_path, meta_path, label_col, positive_label):
    X = pd.read_csv(feature_path, sep="\t")
    meta = pd.read_csv(meta_path, sep="\t")

    if "sample_id" not in meta.columns:
        raise ValueError("metadata missing sample_id")
    if label_col not in meta.columns:
        raise ValueError(f"metadata missing {label_col}")

    # Expect matrix with gene_id/gene_name + sample columns
    required_cols = {"gene_id", "gene_name"}
    if not required_cols.issubset(X.columns):
        raise ValueError("feature matrix missing gene_id/gene_name")

    sample_cols = [c for c in X.columns if c not in ("gene_id", "gene_name")]
    if not sample_cols:
        raise ValueError("feature matrix has no sample columns")

    # Build sample-wise feature matrix
    X_mat = X[sample_cols].T
    X_mat.index = sample_cols

    # Align to metadata sample_id order
    sample_ids = meta["sample_id"].astype(str).tolist()
    missing = [s for s in sample_ids if s not in X_mat.index]
    if missing:
        raise ValueError(f"Samples missing in feature matrix: {', '.join(missing)}")

    feats = X_mat.loc[sample_ids].values
    y = (meta[label_col] == positive_label).astype(int).values
    return feats, y


def build_model(random_state=42):
    return Pipeline(
        [
            ("var", VarianceThreshold()),
            ("scale", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    max_iter=5000,
                    solver="liblinear",
                    class_weight="balanced",
                    random_state=random_state,
                ),
            ),
        ]
    )


def safe_roc_auc(y_true, probs):
    if len(np.unique(y_true)) < 2:
        return float("nan")
    return float(roc_auc_score(y_true, probs))


def main():
    ap = argparse.ArgumentParser(description="Run ML for control vs disease.")
    ap.add_argument("--config", required=True, help="config JSON")
    args = ap.parse_args()

    cfg_path = Path(args.config)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    repo_root = Path(__file__).resolve().parents[2]

    def resolve_cfg_path(p: str) -> str:
        p = Path(p)
        return str(p if p.is_absolute() else (repo_root / p))

    feature_path = resolve_cfg_path(cfg["feature_matrix"])
    meta_path = resolve_cfg_path(cfg["metadata"])
    out_metrics = resolve_cfg_path(cfg["out_metrics"])
    out_perm = resolve_cfg_path(cfg["out_permutation"])

    X, y = load_data(feature_path, meta_path, cfg["label_col"], cfg["positive_label"])

    rkf = RepeatedStratifiedKFold(n_splits=cfg["cv_folds"], n_repeats=cfg["cv_repeats"], random_state=42)
    model_template = build_model(random_state=42)

    auc_scores = []
    bal_acc_scores = []
    for train_idx, test_idx in rkf.split(X, y):
        model = clone(model_template)
        model.fit(X[train_idx], y[train_idx])
        preds = model.predict(X[test_idx])
        probs = model.predict_proba(X[test_idx])[:, 1]
        auc_scores.append(safe_roc_auc(y[test_idx], probs))
        bal_acc_scores.append(balanced_accuracy_score(y[test_idx], preds))

    metrics = pd.DataFrame(
        {
            "metric": [
                "roc_auc_mean",
                "roc_auc_std",
                "balanced_accuracy_mean",
                "balanced_accuracy_std",
                "model",
                "leakage_control",
            ],
            "value": [
                np.nanmean(auc_scores),
                np.nanstd(auc_scores),
                np.mean(bal_acc_scores),
                np.std(bal_acc_scores),
                "VarianceThreshold + StandardScaler + L2 logistic regression",
                "all preprocessing fit inside each CV training fold",
            ],
        }
    )
    Path(out_metrics).parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(out_metrics, sep="\t", index=False)

    # permutation test
    perm_scores = []
    for i in range(cfg["permutations"]):
        y_perm = np.random.permutation(y)
        fold_scores = []
        for train_idx, test_idx in rkf.split(X, y_perm):
            model = clone(model_template)
            model.fit(X[train_idx], y_perm[train_idx])
            probs = model.predict_proba(X[test_idx])[:, 1]
            fold_scores.append(safe_roc_auc(y_perm[test_idx], probs))
        perm_scores.append(np.nanmean(fold_scores))

    perm = pd.DataFrame({"perm_score": perm_scores})
    perm.to_csv(out_perm, sep="\t", index=False)

    # Optional plot for report bundle.
    try:
        import matplotlib.pyplot as plt  # type: ignore

        plot_dir = Path("outputs/plots")
        plot_dir.mkdir(parents=True, exist_ok=True)
        obs = float(metrics.loc[metrics["metric"] == "roc_auc_mean", "value"].iloc[0])
        plt.figure(figsize=(8, 5))
        plt.hist(perm_scores, bins=30, alpha=0.8, color="#4c78a8")
        plt.axvline(obs, color="#f58518", linewidth=2, label=f"Observed (mean CV) = {obs:.3f}")
        plt.xlabel("Permutation ROC-AUC (mean over CV folds)")
        plt.ylabel("Count")
        plt.title("Permutation test distribution")
        plt.legend()
        plt.tight_layout()
        plt.savefig(plot_dir / "ml_permutation_hist.png", dpi=200)
        plt.close()
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
