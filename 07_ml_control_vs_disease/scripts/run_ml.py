#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score


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
    model = LogisticRegression(max_iter=1000)

    scores = []
    for train_idx, test_idx in rkf.split(X, y):
        model.fit(X[train_idx], y[train_idx])
        probs = model.predict_proba(X[test_idx])[:, 1]
        scores.append(roc_auc_score(y[test_idx], probs))

    metrics = pd.DataFrame({"metric": ["roc_auc_mean", "roc_auc_std"], "value": [np.mean(scores), np.std(scores)]})
    Path(out_metrics).parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(out_metrics, sep="\t", index=False)

    # permutation test
    perm_scores = []
    for i in range(cfg["permutations"]):
        y_perm = np.random.permutation(y)
        fold_scores = []
        for train_idx, test_idx in rkf.split(X, y_perm):
            model.fit(X[train_idx], y_perm[train_idx])
            probs = model.predict_proba(X[test_idx])[:, 1]
            fold_scores.append(roc_auc_score(y_perm[test_idx], probs))
        perm_scores.append(np.mean(fold_scores))

    perm = pd.DataFrame({"perm_score": perm_scores})
    perm.to_csv(out_perm, sep="\t", index=False)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
