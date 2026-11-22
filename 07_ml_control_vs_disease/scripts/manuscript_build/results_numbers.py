"""Load all numbers used in the manuscripts from the result tables (single source of truth)."""
from pathlib import Path
import pandas as pd

RES = Path(r"V:\! ! ! PAD\Final version\repo\07_ml_control_vs_disease\results\light_additions_2026-11-21")
MODELS = ["Logistic regression (L2)", "Neural network (MLP)", "Random forest", "SVM (RBF)", "k-nearest neighbours", "XGBoost"]
SHORT = {"Logistic regression (L2)": "Logistic regression", "Neural network (MLP)": "Multilayer perceptron", "Random forest": "Random forest",
         "SVM (RBF)": "SVM (RBF)", "k-nearest neighbours": "k-nearest neighbours", "XGBoost": "XGBoost"}
D_GLOB = "GSM-LOGO, global loci (mutation)"
D_TRAIN = "GSM-LOGO, training-only loci (mutation)"
D_PERS = "Person-LOGO, training-only loci (mutation)"
D_EXPR = "GSM-LOGO, expression only"


def load():
    n = {}
    n["donor"] = pd.read_csv(RES / "A_donor_structure_summary.tsv", sep="\t").set_index("measure")
    n["ident"] = pd.read_csv(RES / "E_identity_check_donor_pairs.tsv", sep="\t")
    n["sweep"] = pd.read_csv(RES / "B_cohort_filter_sweep.tsv", sep="\t")
    n["cov"] = pd.read_csv(RES / "C_coverage_correlations.tsv", sep="\t")
    n["per"] = pd.read_csv(RES / "C_per_run_calls_vs_coverage.tsv", sep="\t")
    n["comp"] = pd.read_csv(RES / "D_gatk_compute_profile.tsv", sep="\t").set_index("step")
    n["rt"] = pd.read_csv(RES / "D_gatk_runtime_per_run.tsv", sep="\t")
    nul = pd.read_csv(RES / "F_exact_null_all_labelings.tsv", sep="\t")
    n["null_all"] = nul
    rows = []
    for (dsg, m), part in nul.groupby(["design", "model"], sort=False):
        o = part[part.is_observed].iloc[0]
        rows.append(dict(design=dsg, model=m, ba=o.balanced_accuracy, auc=o.roc_auc,
                         p_ba=(part.balanced_accuracy >= o.balanced_accuracy - 1e-12).mean(),
                         p_auc=(part.roc_auc >= o.roc_auc - 1e-12).mean(),
                         null_ba=part.balanced_accuracy.mean(), null_auc=part.roc_auc.mean()))
    n["null"] = pd.DataFrame(rows).set_index(["design", "model"])
    n["folds"] = pd.read_csv(RES / "F_training_only_fold_counts.tsv", sep="\t")
    # new elements (light_06)
    n["norm_dep"] = pd.read_csv(RES / "I_norm_coverage_dependence.tsv", sep="\t").set_index("features")
    n["norm"] = pd.read_csv(RES / "I_norm_exact_summary.tsv", sep="\t").set_index("design")
    n["brier"] = pd.read_csv(RES / "H_brier_exact_summary.tsv", sep="\t").set_index(["design", "model"])
    n["en_cv"] = pd.read_csv(RES / "J_elastic_net_human_srr_cv_summary.tsv", sep="\t").set_index("model")
    return n


def fmt(x, k=3):
    return f"{x:.{k}f}"


def fint(x):
    return f"{int(round(x)):,}"
