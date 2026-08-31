#!/usr/bin/env python3
"""Compare classifiers on one combined input under three validation designs."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import VarianceThreshold
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import LeaveOneGroupOut, RepeatedStratifiedKFold
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

warnings.filterwarnings("ignore", category=UserWarning)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def model_templates(seed: int, jobs: int) -> dict[str, Pipeline]:
    scaled = lambda clf: Pipeline([("var", VarianceThreshold()), ("scale", StandardScaler()), ("clf", clf)])
    trees = lambda clf: Pipeline([("var", VarianceThreshold()), ("clf", clf)])
    models: dict[str, Pipeline] = {
        "Logistic regression (L2)": scaled(LogisticRegression(max_iter=5000, solver="liblinear", class_weight="balanced", random_state=seed)),
        "Neural network (MLP)": scaled(MLPClassifier(hidden_layer_sizes=(16,), alpha=1.0, max_iter=3000, random_state=seed)),
        "Random forest": trees(RandomForestClassifier(n_estimators=500, max_features="sqrt", class_weight="balanced", random_state=seed, n_jobs=jobs)),
        "SVM (RBF)": scaled(SVC(kernel="rbf", C=1.0, gamma="scale", probability=True, class_weight="balanced", random_state=seed)),
        "k-nearest neighbours": scaled(KNeighborsClassifier(n_neighbors=3, weights="distance")),
        "Decision tree": trees(DecisionTreeClassifier(max_depth=3, min_samples_leaf=2, class_weight="balanced", random_state=seed)),
    }
    try:
        import xgboost as xgb

        models["XGBoost"] = trees(xgb.XGBClassifier(n_estimators=150, max_depth=2, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8, eval_metric="logloss", random_state=seed, n_jobs=jobs))
    except ImportError:
        print("WARNING: xgboost is unavailable; XGBoost will be omitted", file=sys.stderr)
    return models


def read_inputs(matrix_path: Path, metadata_path: Path, positive_label: str):
    matrix = pd.read_csv(matrix_path, sep="\t")
    metadata = pd.read_csv(metadata_path, sep="\t")
    samples = [column for column in matrix.columns if column not in {"gene_id", "gene_name"}]
    metadata = metadata.set_index("sample_id").loc[samples].reset_index()
    feature_ids = matrix["gene_id"].astype(str).to_numpy()
    variant_mask = np.char.startswith(feature_ids.astype(str), "gatk_variant__")
    expression_mask = np.char.startswith(feature_ids.astype(str), "expression__")
    if not variant_mask.any() or not expression_mask.any() or int(variant_mask.sum() + expression_mask.sum()) != len(feature_ids):
        raise ValueError("combined matrix must contain only gatk_variant__ and expression__ rows")
    x = matrix[samples].T.to_numpy(dtype=np.float32)
    y = (metadata["condition"].astype(str) == positive_label).astype(int).to_numpy()
    groups = metadata["gsm"].astype(str).to_numpy()
    return x, x[:, expression_mask], y, groups, samples, metadata, int(variant_mask.sum()), int(expression_mask.sum())


def parse_af(parts: list[str]) -> float:
    if len(parts) < 10:
        return 1.0
    values = dict(zip(parts[8].split(":"), parts[9].split(":")))
    try:
        if values.get("AF") not in {None, ".", ""}:
            return float(values["AF"].split(",")[0])
        if values.get("AD") not in {None, ".", ""}:
            ref, alt = (float(v) for v in values["AD"].split(",")[:2])
            return alt / (ref + alt) if ref + alt else 0.0
    except (ValueError, IndexError):
        return 0.0
    return 1.0


def load_run_loci(vcf_dir: Path, samples: list[str]) -> tuple[dict[str, set[str]], dict[str, dict[str, float]]]:
    run_sets: dict[str, set[str]] = {}
    run_af: dict[str, dict[str, float]] = {}
    for sample in samples:
        path = vcf_dir / f"{sample}.filtered.vcf"
        if not path.exists():
            raise FileNotFoundError(path)
        loci: set[str] = set()
        afs: dict[str, float] = {}
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("#"):
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 5:
                    continue
                key = f"{parts[0]}:{parts[1]}:{parts[3]}:{parts[4].split(',')[0]}"
                loci.add(key)
                afs[key] = max(afs.get(key, 0.0), parse_af(parts))
        run_sets[sample] = loci
        run_af[sample] = afs
    return run_sets, run_af


def load_variant_gene(path: Path) -> dict[str, list[tuple[str, str]]]:
    frame = pd.read_csv(path, sep="\t")
    mapping: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for row in frame.itertuples(index=False):
        key = f"{row.chrom}:{row.pos}:{row.ref}:{row.alt}"
        pair = (str(row.gene_id), str(row.gene_name))
        if pair not in mapping[key]:
            mapping[key].append(pair)
    return mapping


def training_only_mutation_matrix(train_samples: list[str], all_samples: list[str], run_sets, run_af, variant_gene, min_samples: int, min_vaf: float):
    support: dict[str, int] = defaultdict(int)
    max_af: dict[str, float] = defaultdict(float)
    for sample in train_samples:
        for locus in run_sets[sample]:
            support[locus] += 1
            max_af[locus] = max(max_af[locus], run_af[sample].get(locus, 0.0))
    selected = {locus for locus, count in support.items() if count >= min_samples and max_af[locus] >= min_vaf}
    genes = sorted({gene for locus in selected for gene in variant_gene.get(locus, [])})
    if not genes:
        raise ValueError("training fold produced no recurrent loci mapped to genes")
    gene_index = {gene: idx for idx, gene in enumerate(genes)}
    matrix = np.zeros((len(all_samples), len(genes)), dtype=np.float32)
    for sample_idx, sample in enumerate(all_samples):
        for locus in run_sets[sample] & selected:
            for gene in variant_gene.get(locus, []):
                matrix[sample_idx, gene_index[gene]] += 1.0
    return matrix, len(selected), len(genes)


def metrics(y_true, pred, prob) -> dict[str, float]:
    return {
        "accuracy": float(accuracy_score(y_true, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, pred)),
        "roc_auc": float(roc_auc_score(y_true, prob)),
        "f1_positive": float(f1_score(y_true, pred, zero_division=0)),
    }


def run_srr_cv(x, y, groups, samples, templates, folds: int, repeats: int, seed: int):
    splitter = RepeatedStratifiedKFold(n_splits=folds, n_repeats=repeats, random_state=seed)
    summaries, fold_rows, prediction_rows = [], [], []
    for model_name, template in templates.items():
        print(f"SRR CV: {model_name}", flush=True)
        model_metrics = []
        for fold, (train, test) in enumerate(splitter.split(x, y), 1):
            model = clone(template).fit(x[train], y[train])
            pred, prob = model.predict(x[test]), model.predict_proba(x[test])[:, 1]
            row_metrics = metrics(y[test], pred, prob)
            model_metrics.append(row_metrics)
            fold_rows.append({"design": "SRR-level repeated CV", "model": model_name, "fold": fold, **row_metrics})
            for idx, p, pr in zip(test, pred, prob):
                prediction_rows.append({"design": "SRR-level repeated CV", "model": model_name, "fold": fold, "sample_id": samples[idx], "gsm": groups[idx], "true_label": int(y[idx]), "predicted_label": int(p), "prob_positive": float(pr)})
        summaries.append({"design": "SRR-level repeated CV", "model": model_name, **{f"{key}_mean": float(np.mean([m[key] for m in model_metrics])) for key in model_metrics[0]}, **{f"{key}_sd": float(np.std([m[key] for m in model_metrics], ddof=1)) for key in model_metrics[0]}, "n_folds": folds * repeats})
    return summaries, fold_rows, prediction_rows


def run_logo(x_global, x_expression, y, groups, samples, metadata, templates, training_only, run_sets=None, run_af=None, variant_gene=None, min_samples=4, min_vaf=0.05):
    design = "GSM-LOGO training-only loci" if training_only else "GSM-LOGO global loci"
    summaries, fold_rows, prediction_rows, feature_rows = [], [], [], []
    splits = list(LeaveOneGroupOut().split(x_global, y, groups))
    fold_matrices = []
    for fold, (train, test) in enumerate(splits, 1):
        if training_only:
            train_samples = [samples[idx] for idx in train]
            x_mutation, n_loci, n_genes = training_only_mutation_matrix(train_samples, samples, run_sets, run_af, variant_gene, min_samples, min_vaf)
            x_fold = np.hstack([x_mutation, x_expression])
            feature_rows.append({"fold": fold, "heldout_gsm": str(groups[test][0]), "n_training_runs": len(train), "n_recurrent_loci": n_loci, "n_mutation_genes": n_genes, "n_expression_features": x_expression.shape[1], "n_combined_features": x_fold.shape[1]})
        else:
            x_fold = x_global
        fold_matrices.append(x_fold)
    for model_name, template in templates.items():
        print(f"{design}: {model_name}", flush=True)
        truth, predictions, probabilities = [], [], []
        for fold, ((train, test), x_fold) in enumerate(zip(splits, fold_matrices), 1):
            heldout = str(groups[test][0])
            model = clone(template).fit(x_fold[train], y[train])
            run_prob = model.predict_proba(x_fold[test])[:, 1]
            group_prob = float(run_prob.mean())
            group_pred = int(group_prob >= 0.5)
            group_true = int(y[test][0])
            truth.append(group_true); predictions.append(group_pred); probabilities.append(group_prob)
            fold_rows.append({"design": design, "model": model_name, "fold": fold, "heldout_gsm": heldout, "true_label": group_true, "predicted_label": group_pred, "prob_positive": group_prob, "correct": group_pred == group_true})
            for idx, prob in zip(test, run_prob):
                prediction_rows.append({"design": design, "model": model_name, "fold": fold, "sample_id": samples[idx], "gsm": heldout, "true_label": int(y[idx]), "prob_positive": float(prob)})
        result = metrics(np.asarray(truth), np.asarray(predictions), np.asarray(probabilities))
        summaries.append({"design": design, "model": model_name, **{f"{key}_mean": value for key, value in result.items()}, **{f"{key}_sd": np.nan for key in result}, "n_folds": len(splits)})
    return summaries, fold_rows, prediction_rows, feature_rows


def plot_results(summary: pd.DataFrame, outdir: Path):
    order = summary[summary.design == "SRR-level repeated CV"].sort_values("balanced_accuracy_mean", ascending=False).model.tolist()
    colors = ["#356da8", "#2a9d8f", "#d06b36"]
    designs = ["SRR-level repeated CV", "GSM-LOGO global loci", "GSM-LOGO training-only loci"]
    labels = ["A. SRR-level repeated CV", "B. GSM-LOGO, global loci", "C. GSM-LOGO, training-only loci"]
    fig, axes = plt.subplots(1, 3, figsize=(18, 6.5), sharey=True)
    for ax, design, label, color in zip(axes, designs, labels, colors):
        part = summary[summary.design == design].set_index("model").loc[order].iloc[::-1]
        errors = part["balanced_accuracy_sd"].to_numpy() if design.startswith("SRR") else None
        ax.barh(part.index, part["balanced_accuracy_mean"], xerr=errors, color=color, alpha=0.9)
        ax.axvline(0.5, color="#8b1e1e", linestyle="--", linewidth=1.5)
        ax.set_xlim(0, 1.05); ax.set_title(label); ax.set_xlabel("Balanced accuracy" + (" (mean +/- SD)" if errors is not None else " (7 held-out GSM groups)")); ax.grid(axis="x", alpha=0.2)
    fig.suptitle("Classifier comparison using combined expression + mutation-derived input", fontsize=16)
    fig.tight_layout(); fig.savefig(outdir / "combined_classifier_comparison_three_designs.png", dpi=300, bbox_inches="tight"); plt.close(fig)
    for design, label, color in zip(designs, labels, colors):
        part = summary[summary.design == design].set_index("model").loc[order].iloc[::-1]
        errors = part["balanced_accuracy_sd"].to_numpy() if design.startswith("SRR") else None
        fig, ax = plt.subplots(figsize=(10, 6)); ax.barh(part.index, part["balanced_accuracy_mean"], xerr=errors, color=color); ax.axvline(0.5, color="#8b1e1e", linestyle="--"); ax.set_xlim(0, 1.05); ax.set_title(label + " — combined input"); ax.set_xlabel("Balanced accuracy" + (" (mean +/- SD)" if errors is not None else " (7 held-out GSM groups)")); ax.grid(axis="x", alpha=0.2); fig.tight_layout()
        slug = {designs[0]: "srr_cv", designs[1]: "gsm_logo_global", designs[2]: "gsm_logo_training_only"}[design]
        fig.savefig(outdir / f"combined_classifier_{slug}.png", dpi=300, bbox_inches="tight"); plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--combined-matrix", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--vcf-dir", type=Path, required=True)
    parser.add_argument("--variant-gene-tsv", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--positive-label", default="wound")
    parser.add_argument("--min-samples", type=int, default=4)
    parser.add_argument("--min-vaf", type=float, default=0.05)
    parser.add_argument("--cv-folds", type=int, default=5)
    parser.add_argument("--cv-repeats", type=int, default=30)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args(); args.outdir.mkdir(parents=True, exist_ok=True)
    x, x_expression, y, groups, samples, metadata, n_variant, n_expression = read_inputs(args.combined_matrix, args.metadata, args.positive_label)
    run_sets, run_af = load_run_loci(args.vcf_dir, samples)
    variant_gene = load_variant_gene(args.variant_gene_tsv)
    templates = model_templates(args.random_state, args.jobs)
    summaries, folds, predictions = [], [], []
    s, f, p = run_srr_cv(x, y, groups, samples, templates, args.cv_folds, args.cv_repeats, args.random_state); summaries += s; folds += f; predictions += p
    s, f, p, _ = run_logo(x, x_expression, y, groups, samples, metadata, templates, False); summaries += s; folds += f; predictions += p
    s, f, p, feature_rows = run_logo(x, x_expression, y, groups, samples, metadata, templates, True, run_sets, run_af, variant_gene, args.min_samples, args.min_vaf); summaries += s; folds += f; predictions += p
    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(args.outdir / "combined_three_design_model_comparison.tsv", sep="\t", index=False)
    summary_df.to_csv(args.outdir / "combined_three_design_model_comparison.csv", index=False)
    pd.DataFrame(folds).to_csv(args.outdir / "fold_and_group_metrics.tsv", sep="\t", index=False)
    pd.DataFrame(predictions).to_csv(args.outdir / "predictions.tsv", sep="\t", index=False)
    pd.DataFrame(feature_rows).to_csv(args.outdir / "training_only_feature_counts.tsv", sep="\t", index=False)
    manifest = {"analysis": "combined classifier comparison across three validation designs", "combined_input": "early concatenation of expression__ and gatk_variant__ features for every classifier and design", "n_runs": len(samples), "n_gsm_groups": len(set(groups)), "n_global_variant_features": n_variant, "n_expression_features": n_expression, "n_global_combined_features": x.shape[1], "training_only_rule": f"within each GSM-LOGO fold, recurrent loci are selected only from training SRRs with support >= {args.min_samples} and max VAF >= {args.min_vaf}; gene burden is rebuilt and concatenated with expression", "cv": f"RepeatedStratifiedKFold({args.cv_folds} folds x {args.cv_repeats} repeats, random_state={args.random_state})", "group_cv": "LeaveOneGroupOut(GSM), held-out run probabilities averaged to one GSM prediction", "models": list(templates), "inputs": {"combined_matrix": str(args.combined_matrix.resolve()), "combined_matrix_sha256": sha256(args.combined_matrix), "metadata": str(args.metadata.resolve()), "metadata_sha256": sha256(args.metadata), "vcf_dir": str(args.vcf_dir.resolve()), "variant_gene_tsv": str(args.variant_gene_tsv.resolve()), "variant_gene_tsv_sha256": sha256(args.variant_gene_tsv)}}
    (args.outdir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    plot_results(summary_df, args.outdir)
    print(summary_df[["design", "model", "balanced_accuracy_mean", "roc_auc_mean"]].to_string(index=False)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
