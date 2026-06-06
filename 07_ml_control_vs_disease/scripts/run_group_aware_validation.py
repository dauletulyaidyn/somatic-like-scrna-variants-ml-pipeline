#!/usr/bin/env python3
from __future__ import annotations

import argparse
import itertools
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.feature_selection import VarianceThreshold
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import LeaveOneGroupOut, RepeatedStratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


LABEL_NAMES = np.array(["negative", "positive"])


def read_inputs(
    matrix_path: Path,
    metadata_path: Path,
    label_col: str,
    positive_label: str,
    group_col: str,
    group_title_col: str | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str], pd.DataFrame]:
    matrix = pd.read_csv(matrix_path, sep="\t")
    metadata = pd.read_csv(metadata_path, sep="\t")

    required_matrix_cols = {"gene_id", "gene_name"}
    if not required_matrix_cols.issubset(matrix.columns):
        missing = sorted(required_matrix_cols - set(matrix.columns))
        raise ValueError(f"feature matrix missing required columns: {', '.join(missing)}")
    required_meta_cols = {"sample_id", label_col, group_col}
    if not required_meta_cols.issubset(metadata.columns):
        missing = sorted(required_meta_cols - set(metadata.columns))
        raise ValueError(f"metadata missing required columns: {', '.join(missing)}")

    sample_cols = [c for c in matrix.columns if c not in ("gene_id", "gene_name")]
    if not sample_cols:
        raise ValueError("feature matrix has no sample columns")

    metadata["sample_id"] = metadata["sample_id"].astype(str)
    missing_samples = [s for s in metadata["sample_id"].tolist() if s not in sample_cols]
    if missing_samples:
        raise ValueError("samples missing in feature matrix: " + ", ".join(missing_samples))

    metadata = metadata.set_index("sample_id").loc[sample_cols].reset_index()
    x_df = matrix[sample_cols].T
    x_df.index = sample_cols

    x = x_df.values.astype(float)
    y = (metadata[label_col].astype(str).values == positive_label).astype(int)
    groups = metadata[group_col].astype(str).values
    if group_title_col and group_title_col in metadata.columns:
        group_titles = metadata[group_title_col].astype(str).values
    else:
        group_titles = groups.copy()

    validate_groups_have_single_label(groups, y)
    return x, y, groups, group_titles, sample_cols, metadata


def validate_groups_have_single_label(groups: np.ndarray, y: np.ndarray) -> None:
    bad_groups: list[str] = []
    for group in sorted(set(groups)):
        labels = set(y[groups == group].tolist())
        if len(labels) > 1:
            bad_groups.append(group)
    if bad_groups:
        raise ValueError(
            "each group must have one condition label; mixed-label groups: "
            + ", ".join(bad_groups)
        )


def build_model(random_state: int) -> Pipeline:
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


def safe_auc(y_true: np.ndarray, scores: np.ndarray) -> float:
    if len(np.unique(y_true)) < 2:
        return float("nan")
    return float(roc_auc_score(y_true, scores))


def safe_f1(y_true: np.ndarray, pred: np.ndarray) -> float:
    if len(np.unique(y_true)) < 2 and len(np.unique(pred)) < 2:
        return 1.0 if np.array_equal(y_true, pred) else 0.0
    return float(f1_score(y_true, pred, zero_division=0))


def metric_row(y_true: np.ndarray, pred: np.ndarray, scores: np.ndarray | None = None) -> dict[str, float]:
    row = {
        "accuracy": float(accuracy_score(y_true, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, pred)),
        "f1_positive": safe_f1(y_true, pred),
    }
    if scores is not None:
        row["roc_auc"] = safe_auc(y_true, scores)
    return row


def run_level_cv(
    x: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    group_titles: np.ndarray,
    sample_cols: list[str],
    labels: np.ndarray,
    cv_folds: int,
    cv_repeats: int,
    random_state: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    min_class_n = int(np.bincount(y).min())
    if cv_folds > min_class_n:
        raise ValueError(f"cv_folds={cv_folds} exceeds smallest class size={min_class_n}")

    rkf = RepeatedStratifiedKFold(
        n_splits=cv_folds,
        n_repeats=cv_repeats,
        random_state=random_state,
    )
    model_template = build_model(random_state)
    fold_rows: list[dict[str, object]] = []
    pred_rows: list[dict[str, object]] = []

    for fold_idx, (train_idx, test_idx) in enumerate(rkf.split(x, y), start=1):
        model = clone(model_template)
        model.fit(x[train_idx], y[train_idx])
        pred = model.predict(x[test_idx])
        prob = model.predict_proba(x[test_idx])[:, 1]
        score = model.decision_function(x[test_idx])

        train_groups = set(groups[train_idx])
        overlap_flags = [g in train_groups for g in groups[test_idx]]
        row: dict[str, object] = {
            "fold": fold_idx,
            "n_train": int(len(train_idx)),
            "n_test": int(len(test_idx)),
            "test_samples": ";".join(np.array(sample_cols)[test_idx]),
            "test_groups": ";".join(groups[test_idx]),
            "test_observations_with_group_seen_in_train": int(sum(overlap_flags)),
            "test_group_overlap_rate": float(np.mean(overlap_flags)),
        }
        row.update(metric_row(y[test_idx], pred, score))
        fold_rows.append(row)

        for i, p, pr, sc, overlap in zip(test_idx, pred, prob, score, overlap_flags):
            pred_rows.append(
                {
                    "fold": fold_idx,
                    "sample_id": sample_cols[i],
                    "group": groups[i],
                    "group_title": group_titles[i],
                    "true_condition": labels[y[i]],
                    "predicted_condition": labels[int(p)],
                    "prob_positive": float(pr),
                    "decision_score": float(sc),
                    "correct": bool(int(p) == int(y[i])),
                    "paired_group_seen_in_train": bool(overlap),
                }
            )

    fold_df = pd.DataFrame(fold_rows)
    pred_df = pd.DataFrame(pred_rows)
    summary = {
        "analysis": "Run-level repeated stratified CV",
        "grouping_used": "none",
        "evaluation_unit": "run/sample row",
        "design": f"{cv_folds}-fold x {cv_repeats} repeats",
        "n_runs": int(len(y)),
        "n_groups": int(len(np.unique(groups))),
        "n_folds": int(len(fold_df)),
        "accuracy_mean": float(fold_df["accuracy"].mean()),
        "accuracy_sd": float(fold_df["accuracy"].std(ddof=1)),
        "balanced_accuracy_mean": float(fold_df["balanced_accuracy"].mean()),
        "balanced_accuracy_sd": float(fold_df["balanced_accuracy"].std(ddof=1)),
        "roc_auc_mean": float(fold_df["roc_auc"].mean()),
        "roc_auc_sd": float(fold_df["roc_auc"].std(ddof=1)),
        "test_group_overlap_rate_mean": float(fold_df["test_group_overlap_rate"].mean()),
        "test_group_overlap_rate_median": float(fold_df["test_group_overlap_rate"].median()),
        "interpretation": "Optimistic run-level separability comparator; paired group observations can appear in both train and test.",
    }
    return fold_df, pred_df, summary


def logo_run_predictions(
    x: np.ndarray,
    y_eval: np.ndarray,
    groups: np.ndarray,
    group_titles: np.ndarray,
    sample_cols: list[str],
    labels: np.ndarray,
    random_state: int,
) -> pd.DataFrame:
    logo = LeaveOneGroupOut()
    model_template = build_model(random_state)
    rows: list[dict[str, object]] = []

    for fold_idx, (train_idx, test_idx) in enumerate(logo.split(x, y_eval, groups), start=1):
        if len(np.unique(y_eval[train_idx])) < 2:
            raise ValueError(
                "a leave-one-group-out training fold has only one class; grouped validation is not defined"
            )
        model = clone(model_template)
        model.fit(x[train_idx], y_eval[train_idx])
        pred = model.predict(x[test_idx])
        prob = model.predict_proba(x[test_idx])[:, 1]
        score = model.decision_function(x[test_idx])
        held_group = groups[test_idx][0]

        for i, p, pr, sc in zip(test_idx, pred, prob, score):
            rows.append(
                {
                    "fold": fold_idx,
                    "heldout_group": held_group,
                    "sample_id": sample_cols[i],
                    "group_title": group_titles[i],
                    "true_label": int(y_eval[i]),
                    "true_condition": labels[int(y_eval[i])],
                    "predicted_label": int(p),
                    "predicted_condition": labels[int(p)],
                    "prob_positive": float(pr),
                    "decision_score": float(sc),
                    "correct": bool(int(p) == int(y_eval[i])),
                }
            )
    return pd.DataFrame(rows)


def aggregate_group_predictions(run_df: pd.DataFrame, labels: np.ndarray) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for group, sub in run_df.groupby("heldout_group", sort=True):
        true_label = int(sub["true_label"].iloc[0])
        mean_prob = float(sub["prob_positive"].mean())
        mean_score = float(sub["decision_score"].mean())
        pred_label = int(mean_prob >= 0.5)
        rows.append(
            {
                "heldout_group": group,
                "group_title": ";".join(sorted(set(sub["group_title"]))),
                "n_runs": int(len(sub)),
                "run_ids": ";".join(sub["sample_id"]),
                "true_label": true_label,
                "true_condition": labels[true_label],
                "run_predicted_conditions": ";".join(sub["predicted_condition"]),
                "run_prob_positive": ";".join(f"{v:.6f}" for v in sub["prob_positive"]),
                "mean_prob_positive": mean_prob,
                "mean_decision_score": mean_score,
                "predicted_label": pred_label,
                "predicted_condition": labels[pred_label],
                "correct": bool(pred_label == true_label),
            }
        )
    return pd.DataFrame(rows)


def grouped_validation(
    x: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    group_titles: np.ndarray,
    sample_cols: list[str],
    labels: np.ndarray,
    random_state: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object], dict[str, object], pd.DataFrame]:
    run_df = logo_run_predictions(x, y, groups, group_titles, sample_cols, labels, random_state)
    group_df = aggregate_group_predictions(run_df, labels)
    run_metrics = metric_row(
        run_df["true_label"].to_numpy(),
        run_df["predicted_label"].to_numpy(),
        run_df["decision_score"].to_numpy(),
    )
    group_metrics = metric_row(
        group_df["true_label"].to_numpy(),
        group_df["predicted_label"].to_numpy(),
        group_df["mean_decision_score"].to_numpy(),
    )
    cm_run = confusion_matrix(
        run_df["true_label"].to_numpy(),
        run_df["predicted_label"].to_numpy(),
        labels=[0, 1],
    )
    cm_group = confusion_matrix(
        group_df["true_label"].to_numpy(),
        group_df["predicted_label"].to_numpy(),
        labels=[0, 1],
    )

    run_summary = {
        "analysis": "Group-aware leave-one-group-out validation",
        "grouping_used": "group_col",
        "evaluation_unit": "run/sample rows pooled across held-out group folds",
        "design": "Leave one group out; all rows from held-out group are test only",
        "n_runs": int(len(y)),
        "n_groups": int(len(np.unique(groups))),
        "n_folds": int(len(np.unique(groups))),
        "accuracy_mean": run_metrics["accuracy"],
        "accuracy_sd": math.nan,
        "balanced_accuracy_mean": run_metrics["balanced_accuracy"],
        "balanced_accuracy_sd": math.nan,
        "roc_auc_mean": run_metrics["roc_auc"],
        "roc_auc_sd": math.nan,
        "test_group_overlap_rate_mean": 0.0,
        "test_group_overlap_rate_median": 0.0,
        "interpretation": "Leakage-controlled grouped validation at run level; held-out group rows are never in training.",
    }
    group_summary = {
        "analysis": "Group-aware leave-one-group-out validation",
        "grouping_used": "group_col",
        "evaluation_unit": "independent group, rows aggregated by mean probability",
        "design": "Leave one group out; group prediction aggregates held-out rows",
        "n_runs": int(len(y)),
        "n_groups": int(len(np.unique(groups))),
        "n_folds": int(len(np.unique(groups))),
        "accuracy_mean": group_metrics["accuracy"],
        "accuracy_sd": math.nan,
        "balanced_accuracy_mean": group_metrics["balanced_accuracy"],
        "balanced_accuracy_sd": math.nan,
        "roc_auc_mean": group_metrics["roc_auc"],
        "roc_auc_sd": math.nan,
        "test_group_overlap_rate_mean": 0.0,
        "test_group_overlap_rate_median": 0.0,
        "interpretation": "Primary independence-aware validation; independent unit is the metadata group.",
    }
    cm_df = pd.DataFrame(
        [
            {
                "analysis": "grouped_logo_run_pooled",
                "true_condition": labels[0],
                f"pred_{labels[0]}": int(cm_run[0, 0]),
                f"pred_{labels[1]}": int(cm_run[0, 1]),
            },
            {
                "analysis": "grouped_logo_run_pooled",
                "true_condition": labels[1],
                f"pred_{labels[0]}": int(cm_run[1, 0]),
                f"pred_{labels[1]}": int(cm_run[1, 1]),
            },
            {
                "analysis": "grouped_logo_group_aggregated",
                "true_condition": labels[0],
                f"pred_{labels[0]}": int(cm_group[0, 0]),
                f"pred_{labels[1]}": int(cm_group[0, 1]),
            },
            {
                "analysis": "grouped_logo_group_aggregated",
                "true_condition": labels[1],
                f"pred_{labels[0]}": int(cm_group[1, 0]),
                f"pred_{labels[1]}": int(cm_group[1, 1]),
            },
        ]
    )
    return run_df, group_df, run_summary, group_summary, cm_df


def group_labelings(
    groups: np.ndarray,
    y: np.ndarray,
    max_exact: int,
    n_random: int,
    seed: int,
) -> tuple[list[tuple[str, ...]], bool]:
    unique_groups = sorted(np.unique(groups))
    positive_groups = sorted(set(groups[y == 1]))
    n_positive_groups = len(positive_groups)
    n_exact = math.comb(len(unique_groups), n_positive_groups)

    if n_exact <= max_exact:
        return list(itertools.combinations(unique_groups, n_positive_groups)), True

    rng = np.random.default_rng(seed)
    labelings: set[tuple[str, ...]] = {tuple(positive_groups)}
    while len(labelings) < min(n_random, n_exact):
        chosen = tuple(sorted(rng.choice(unique_groups, size=n_positive_groups, replace=False).tolist()))
        labelings.add(chosen)
    return sorted(labelings), False


def grouped_permutation(
    x: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    group_titles: np.ndarray,
    sample_cols: list[str],
    labels: np.ndarray,
    random_state: int,
    max_exact: int,
    n_random: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    labelings, exact = group_labelings(groups, y, max_exact, n_random, random_state)
    observed_positive_groups = tuple(sorted(set(groups[y == 1])))
    rows: list[dict[str, object]] = []

    for idx, positive_group_tuple in enumerate(labelings, start=1):
        positive_group_set = set(positive_group_tuple)
        y_perm = np.array([1 if g in positive_group_set else 0 for g in groups], dtype=int)
        run_df, group_df, _run_summary, _group_summary, _cm = grouped_validation(
            x, y_perm, groups, group_titles, sample_cols, labels, random_state
        )
        run_m = metric_row(
            run_df["true_label"].to_numpy(),
            run_df["predicted_label"].to_numpy(),
            run_df["decision_score"].to_numpy(),
        )
        group_m = metric_row(
            group_df["true_label"].to_numpy(),
            group_df["predicted_label"].to_numpy(),
            group_df["mean_decision_score"].to_numpy(),
        )
        rows.append(
            {
                "permutation_id": idx,
                "positive_groups": ";".join(positive_group_tuple),
                "is_observed_labeling": bool(tuple(positive_group_tuple) == observed_positive_groups),
                "run_accuracy": run_m["accuracy"],
                "run_balanced_accuracy": run_m["balanced_accuracy"],
                "run_roc_auc": run_m["roc_auc"],
                "group_accuracy": group_m["accuracy"],
                "group_balanced_accuracy": group_m["balanced_accuracy"],
                "group_roc_auc": group_m["roc_auc"],
            }
        )

    perm_df = pd.DataFrame(rows)
    observed = perm_df[perm_df["is_observed_labeling"]].iloc[0]
    method = "exact" if exact else "random"

    summary_rows = []
    for metric in ("group_balanced_accuracy", "group_roc_auc", "run_balanced_accuracy"):
        n_ge = int((perm_df[metric] >= observed[metric]).sum())
        p_value = n_ge / len(perm_df) if exact else (n_ge + 1) / (len(perm_df) + 1)
        summary_rows.append(
            {
                "analysis": f"{method.capitalize()} group-level permutation",
                "metric": metric,
                "observed_value": float(observed[metric]),
                "n_labelings_including_observed": int(len(perm_df)),
                "n_labelings_ge_observed": n_ge,
                "p_value": float(p_value),
                "label_permutation_unit": "metadata group",
                "class_balance_preserved": f"{len(observed_positive_groups)} positive groups / {len(np.unique(groups)) - len(observed_positive_groups)} negative groups",
            }
        )
    return perm_df, pd.DataFrame(summary_rows)


def format_mean_sd(mean: float, sd: float) -> str:
    if pd.isna(sd):
        return f"{mean:.3f}"
    return f"{mean:.3f} +/- {sd:.3f}"


def make_word_table(
    summaries: list[dict[str, object]],
    perm_summary: pd.DataFrame,
    group_col: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for summary in summaries:
        rows.append(
            {
                "Analysis": summary["analysis"],
                "Grouping": summary["grouping_used"],
                "Evaluation unit": summary["evaluation_unit"],
                "Design": summary["design"],
                "n runs": summary["n_runs"],
                "n groups": summary["n_groups"],
                "Accuracy": format_mean_sd(float(summary["accuracy_mean"]), float(summary["accuracy_sd"])),
                "Balanced accuracy": format_mean_sd(
                    float(summary["balanced_accuracy_mean"]),
                    float(summary["balanced_accuracy_sd"]),
                ),
                "ROC-AUC": format_mean_sd(float(summary["roc_auc_mean"]), float(summary["roc_auc_sd"])),
                "Group overlap in train/test": f"{float(summary['test_group_overlap_rate_mean']):.3f}",
                "Interpretation": summary["interpretation"],
            }
        )

    group_bal = perm_summary[perm_summary["metric"] == "group_balanced_accuracy"].iloc[0]
    group_auc = perm_summary[perm_summary["metric"] == "group_roc_auc"].iloc[0]
    rows.append(
        {
            "Analysis": perm_summary["analysis"].iloc[0],
            "Grouping": group_col,
            "Evaluation unit": "independent group",
            "Design": "Class-balanced group label permutations; observed labeling included",
            "n runs": summaries[0]["n_runs"],
            "n groups": summaries[0]["n_groups"],
            "Accuracy": "",
            "Balanced accuracy": f"observed {group_bal['observed_value']:.3f}; p={group_bal['p_value']:.3f}",
            "ROC-AUC": f"observed {group_auc['observed_value']:.3f}; p={group_auc['p_value']:.3f}",
            "Group overlap in train/test": "0.000",
            "Interpretation": "Permutation is performed at metadata-group level, so paired rows keep the same permuted label.",
        }
    )
    return pd.DataFrame(rows)


def write_method_note(
    outdir: Path,
    matrix_path: Path,
    metadata_path: Path,
    group_col: str,
    label_col: str,
    positive_label: str,
    run_summary: dict[str, object],
    group_run_summary: dict[str, object],
    group_summary: dict[str, object],
    perm_summary: pd.DataFrame,
) -> None:
    group_bal = perm_summary[perm_summary["metric"] == "group_balanced_accuracy"].iloc[0]
    lines = [
        "# Group-aware validation summary",
        "",
        f"Input matrix: {matrix_path}",
        f"Metadata: {metadata_path}",
        "",
        f"Label column: {label_col}; positive label: {positive_label}",
        f"Grouping unit: {group_col}. All rows sharing this group are kept in the same fold.",
        "Model: VarianceThreshold + StandardScaler + L2 logistic regression with class_weight='balanced'.",
        "All preprocessing is fit inside each cross-validation fold.",
        "",
        "Key result:",
        f"- Run-level repeated stratified CV balanced accuracy: {run_summary['balanced_accuracy_mean']:.3f} +/- {run_summary['balanced_accuracy_sd']:.3f}; mean group-overlap rate in test observations: {run_summary['test_group_overlap_rate_mean']:.3f}.",
        f"- Group-aware leave-one-group-out, run-pooled balanced accuracy: {group_run_summary['balanced_accuracy_mean']:.3f}; ROC-AUC: {group_run_summary['roc_auc_mean']:.3f}.",
        f"- Group-aware leave-one-group-out, group-aggregated balanced accuracy: {group_summary['balanced_accuracy_mean']:.3f}; ROC-AUC: {group_summary['roc_auc_mean']:.3f}.",
        f"- Group-level permutation for group balanced accuracy: observed {group_bal['observed_value']:.3f}, p={group_bal['p_value']:.3f} over {int(group_bal['n_labelings_including_observed'])} labelings.",
        "",
        "Interpretation:",
        "Run-level CV is a separability comparator when repeated observations from the same group can enter both train and test folds.",
        "Group-aware validation is the primary independence-aware validation check for non-independent run-level observations.",
    ]
    (outdir / "group_validation_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run run-level and group-aware validation for gene-burden matrices.",
    )
    parser.add_argument("--feature-matrix", required=True, help="TSV matrix with gene_id/gene_name and sample columns")
    parser.add_argument("--metadata", required=True, help="TSV metadata with sample_id, label, and group columns")
    parser.add_argument("--outdir", required=True, help="Directory for validation tables")
    parser.add_argument("--label-col", default="condition")
    parser.add_argument("--positive-label", default="wound")
    parser.add_argument("--negative-label", default=None)
    parser.add_argument("--group-col", default="gsm")
    parser.add_argument("--group-title-col", default="sample_title")
    parser.add_argument("--cv-folds", type=int, default=5)
    parser.add_argument("--cv-repeats", type=int, default=30)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--max-exact-permutations", type=int, default=10000)
    parser.add_argument("--random-permutations", type=int, default=1000)
    args = parser.parse_args()

    matrix_path = Path(args.feature_matrix)
    metadata_path = Path(args.metadata)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    x, y, groups, group_titles, sample_cols, _metadata = read_inputs(
        matrix_path,
        metadata_path,
        args.label_col,
        args.positive_label,
        args.group_col,
        args.group_title_col,
    )
    negative_label = args.negative_label
    if negative_label is None:
        meta_labels = pd.read_csv(metadata_path, sep="\t")[args.label_col].astype(str).unique().tolist()
        negative_candidates = [label for label in meta_labels if label != args.positive_label]
        negative_label = negative_candidates[0] if negative_candidates else "negative"
    labels = np.array([negative_label, args.positive_label])

    run_fold_df, run_pred_df, run_summary = run_level_cv(
        x,
        y,
        groups,
        group_titles,
        sample_cols,
        labels,
        args.cv_folds,
        args.cv_repeats,
        args.random_state,
    )
    group_run_df, group_df, group_run_summary, group_summary, cm_df = grouped_validation(
        x,
        y,
        groups,
        group_titles,
        sample_cols,
        labels,
        args.random_state,
    )
    group_run_summary["grouping_used"] = args.group_col
    group_summary["grouping_used"] = args.group_col
    perm_df, perm_summary = grouped_permutation(
        x,
        y,
        groups,
        group_titles,
        sample_cols,
        labels,
        args.random_state,
        args.max_exact_permutations,
        args.random_permutations,
    )
    validation_summary = pd.DataFrame([run_summary, group_run_summary, group_summary])
    word_table = make_word_table([run_summary, group_run_summary, group_summary], perm_summary, args.group_col)

    run_fold_df.to_csv(outdir / "run_level_cv_fold_metrics.tsv", sep="\t", index=False)
    run_pred_df.to_csv(outdir / "run_level_cv_predictions.tsv", sep="\t", index=False)
    pd.DataFrame([run_summary]).to_csv(outdir / "run_level_cv_summary.tsv", sep="\t", index=False)
    group_run_df.to_csv(outdir / "group_run_predictions.tsv", sep="\t", index=False)
    group_df.to_csv(outdir / "group_wise_predictions.tsv", sep="\t", index=False)
    pd.DataFrame([group_run_summary, group_summary]).to_csv(
        outdir / "group_validation_summary.tsv",
        sep="\t",
        index=False,
    )
    cm_df.to_csv(outdir / "group_confusion_matrices.tsv", sep="\t", index=False)
    perm_df.to_csv(outdir / "grouped_permutation.tsv", sep="\t", index=False)
    perm_summary.to_csv(outdir / "grouped_permutation_summary.tsv", sep="\t", index=False)
    validation_summary.to_csv(outdir / "validation_summary.tsv", sep="\t", index=False)
    word_table.to_csv(outdir / "table_validation_for_report.tsv", sep="\t", index=False)
    word_table.to_csv(outdir / "table_validation_for_report.csv", index=False)
    write_method_note(
        outdir,
        matrix_path,
        metadata_path,
        args.group_col,
        args.label_col,
        args.positive_label,
        run_summary,
        group_run_summary,
        group_summary,
        perm_summary,
    )

    print(f"Wrote group-aware validation outputs to: {outdir}")
    print(word_table.to_string(index=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
