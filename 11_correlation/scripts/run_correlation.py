#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import sys
from itertools import combinations
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr


def open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def normalize_sample_id(value: str) -> str:
    name = str(value)
    suffixes = [
        ".filtered.annotated.vcf.gz",
        ".filtered.annotated.vcf",
        ".filtered.with_filters.vcf.gz",
        ".filtered.with_filters.vcf",
        ".filtered.vcf.gz",
        ".filtered.vcf",
        ".raw.vcf.gz",
        ".raw.vcf",
        ".vcf.gz",
        ".vcf",
        ".bam",
    ]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name.replace("Aligned.sortedByCoord.out", "")


def load_gene_burden(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t")
    if "gene_id" not in df.columns:
        raise ValueError("gene_burden missing gene_id")
    sample_cols = [column for column in df.columns if column not in ("gene_id", "gene_name")]
    rows = []
    for sample_id in sample_cols:
        rows.append(
            {
                "sample_id": normalize_sample_id(sample_id),
                "gene_burden_total": float(df[sample_id].sum()),
                "burdened_gene_count": int((df[sample_id] > 0).sum()),
            }
        )
    return pd.DataFrame(rows).groupby("sample_id", as_index=False).sum(numeric_only=True)


def load_mut_burden(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t")
    if "sample_id" not in df.columns:
        raise ValueError("mut_burden missing sample_id")
    df = df.copy()
    df["sample_id"] = df["sample_id"].astype(str).map(normalize_sample_id)
    numeric_cols = [column for column in df.columns if column != "sample_id"]
    grouped = df.groupby("sample_id", as_index=False)[numeric_cols].sum()
    return grouped.rename(columns={column: f"mutation_{column}" for column in numeric_cols})


def load_mut_signatures(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t")
    if "sample_id" not in df.columns:
        raise ValueError("mut_signatures missing sample_id")
    df = df.copy()
    df["sample_id"] = df["sample_id"].astype(str).map(normalize_sample_id)
    numeric_cols = [column for column in df.columns if column != "sample_id"]
    if not numeric_cols:
        return pd.DataFrame(columns=["sample_id", "signature_total", "signature_channels_nonzero"])
    grouped = df.groupby("sample_id", as_index=False)[numeric_cols].sum()
    grouped["signature_total"] = grouped[numeric_cols].sum(axis=1)
    grouped["signature_channels_nonzero"] = (grouped[numeric_cols] > 0).sum(axis=1)
    return grouped[["sample_id", "signature_total", "signature_channels_nonzero"]]


def load_cluster_metrics(cluster_dir: Path) -> pd.DataFrame:
    files = sorted(cluster_dir.glob("*.cellsnp.cluster_counts.tsv")) + sorted(cluster_dir.glob("*.cellsnp.cluster_counts.tsv.gz"))
    rows = []
    for path in files:
        sample_name = path.name.replace(".cellsnp.cluster_counts.tsv.gz", "").replace(".cellsnp.cluster_counts.tsv", "")
        sample_id = normalize_sample_id(sample_name)
        df = pd.read_csv(path, sep="\t")
        if df.empty:
            rows.append(
                {
                    "sample_id": sample_id,
                    "cluster_variant_rows": 0,
                    "cluster_alt_sum_total": 0.0,
                    "cluster_depth_sum_total": 0.0,
                    "cluster_mean_vaf": 0.0,
                    "cluster_count": 0,
                }
            )
            continue
        alt_sum_total = float(df["alt_sum"].sum()) if "alt_sum" in df.columns else 0.0
        depth_sum_total = float(df["depth_sum"].sum()) if "depth_sum" in df.columns else 0.0
        cluster_count = int(df["cluster"].nunique()) if "cluster" in df.columns else 0
        mean_vaf = (alt_sum_total / depth_sum_total) if depth_sum_total > 0 else float(df["vaf"].mean()) if "vaf" in df.columns else 0.0
        rows.append(
            {
                "sample_id": sample_id,
                "cluster_variant_rows": int(len(df)),
                "cluster_alt_sum_total": alt_sum_total,
                "cluster_depth_sum_total": depth_sum_total,
                "cluster_mean_vaf": mean_vaf,
                "cluster_count": cluster_count,
            }
        )
    return pd.DataFrame(rows)


def infer_starsolo_sample_id(root: Path, barcode_path: Path) -> str:
    rel = barcode_path.relative_to(root)
    return normalize_sample_id(rel.parts[0]) if rel.parts else normalize_sample_id(barcode_path.stem)


def count_lines(path: Path) -> int:
    with open_text(path) as handle:
        return sum(1 for _ in handle)


def load_starsolo_metrics(starsolo_dir: Path) -> pd.DataFrame:
    barcode_files = sorted(starsolo_dir.glob("**/Gene/filtered/barcodes.tsv")) + sorted(starsolo_dir.glob("**/Gene/filtered/barcodes.tsv.gz"))
    rows = []
    seen: set[str] = set()
    for barcode_path in barcode_files:
        sample_id = infer_starsolo_sample_id(starsolo_dir, barcode_path)
        if sample_id in seen:
            continue
        seen.add(sample_id)
        rows.append({"sample_id": sample_id, "starsolo_detected_cells": count_lines(barcode_path)})
    return pd.DataFrame(rows)


def load_metadata(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t")
    if "sample_id" not in df.columns:
        raise ValueError("metadata missing sample_id")
    df = df.copy()
    df["sample_id"] = df["sample_id"].astype(str).map(normalize_sample_id)
    keep_cols = ["sample_id"]
    for column in ("condition", "run_id", "sample_title", "gsm"):
        if column in df.columns:
            keep_cols.append(column)
    return df[keep_cols].drop_duplicates(subset=["sample_id"])


def bh_fdr(p_values: list[float]) -> list[float]:
    if not p_values:
        return []
    ordered = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [0.0] * len(p_values)
    running = 1.0
    total = len(p_values)
    for reverse_rank, (idx, p_value) in enumerate(reversed(ordered), start=1):
        denom = total - reverse_rank + 1
        value = min(running, (p_value * total) / denom)
        running = value
        adjusted[idx] = value
    return adjusted


def main():
    ap = argparse.ArgumentParser(description="Integrated sample-level expression-mutation correlation analysis.")
    ap.add_argument("--config", required=True, help="config JSON")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    repo_root = Path(__file__).resolve().parents[2]

    def resolve_cfg_path(value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else (repo_root / path)

    metadata_path = resolve_cfg_path(cfg.get("metadata", ""))
    starsolo_dir = resolve_cfg_path(cfg.get("starsolo_dir", ""))
    gene_burden_path = resolve_cfg_path(cfg.get("gene_burden", ""))
    cluster_counts_dir = resolve_cfg_path(cfg.get("cluster_counts_dir", ""))
    mut_burden_path = resolve_cfg_path(cfg.get("mut_burden", ""))
    mut_signatures_path = resolve_cfg_path(cfg.get("mut_signatures", ""))

    if not gene_burden_path.exists() or not mut_burden_path.exists():
        print("Missing required inputs", file=sys.stderr)
        return 2

    notes = [f"Loaded gene burden from {gene_burden_path}", f"Loaded mutational burden from {mut_burden_path}"]
    merged = load_gene_burden(gene_burden_path).merge(load_mut_burden(mut_burden_path), on="sample_id", how="outer")

    if mut_signatures_path.exists():
        merged = merged.merge(load_mut_signatures(mut_signatures_path), on="sample_id", how="left")
        notes.append(f"Loaded mutational signatures from {mut_signatures_path}")
    else:
        notes.append("Mutational signature table was not available")

    if cluster_counts_dir.exists():
        cluster_df = load_cluster_metrics(cluster_counts_dir)
        if not cluster_df.empty:
            merged = merged.merge(cluster_df, on="sample_id", how="left")
            notes.append(f"Loaded cluster-level mutation metrics from {cluster_counts_dir}")
    else:
        notes.append("Cluster aggregation outputs were not available")

    if starsolo_dir.exists():
        starsolo_df = load_starsolo_metrics(starsolo_dir)
        if not starsolo_df.empty:
            merged = merged.merge(starsolo_df, on="sample_id", how="left")
            notes.append(f"Loaded STARsolo-derived cell counts from {starsolo_dir}")
    else:
        notes.append("STARsolo outputs were not available")

    if metadata_path.exists():
        merged = merged.merge(load_metadata(metadata_path), on="sample_id", how="left")
        notes.append(f"Loaded metadata from {metadata_path}")
    else:
        notes.append("Metadata table was not available")

    if merged.empty:
        print("No overlap between gene burden and mutational burden samples", file=sys.stderr)
        return 2

    merged = merged.sort_values("sample_id").reset_index(drop=True)
    numeric_cols = [
        column
        for column in merged.columns
        if column != "sample_id" and pd.api.types.is_numeric_dtype(merged[column]) and merged[column].notna().any()
    ]
    if len(numeric_cols) < 2:
        print("Not enough numeric metrics for integrated correlation analysis", file=sys.stderr)
        return 2

    pair_rows = []
    p_values = []
    for metric_x, metric_y in combinations(numeric_cols, 2):
        pair = merged[["sample_id", metric_x, metric_y]].dropna()
        if len(pair) < 3:
            continue
        if pair[metric_x].nunique() < 2 or pair[metric_y].nunique() < 2:
            continue
        rho, p_value = spearmanr(pair[metric_x], pair[metric_y])
        if pd.isna(rho) or pd.isna(p_value):
            continue
        pair_rows.append(
            {
                "metric_x": metric_x,
                "metric_y": metric_y,
                "n_samples": int(len(pair)),
                "spearman_rho": float(rho),
                "p_value": float(p_value),
            }
        )
        p_values.append(float(p_value))

    if not pair_rows:
        print("No metric pairs had enough overlapping samples", file=sys.stderr)
        return 2

    fdr_values = bh_fdr(p_values)
    for row, fdr in zip(pair_rows, fdr_values):
        row["fdr_bh"] = float(fdr)
    pairwise = pd.DataFrame(pair_rows)

    corr_matrix = pd.DataFrame(1.0, index=numeric_cols, columns=numeric_cols)
    for row in pair_rows:
        corr_matrix.loc[row["metric_x"], row["metric_y"]] = row["spearman_rho"]
        corr_matrix.loc[row["metric_y"], row["metric_x"]] = row["spearman_rho"]

    sample_out = resolve_cfg_path(cfg.get("out_sample_integration", "11_correlation/outputs/metrics/sample_integration.tsv"))
    corr_out = resolve_cfg_path(cfg.get("out_corr", "11_correlation/outputs/metrics/correlation_matrix.tsv"))
    pairs_out = resolve_cfg_path(cfg.get("out_pairs", "11_correlation/outputs/metrics/correlation_pairs.tsv"))
    cond_out = resolve_cfg_path(cfg.get("out_condition_summary", "11_correlation/outputs/metrics/condition_summary.tsv"))
    notes_out = resolve_cfg_path(cfg.get("out_notes", "11_correlation/outputs/metrics/integration_notes.md"))
    sample_out.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(sample_out, sep="\t", index=False)
    corr_matrix.to_csv(corr_out, sep="\t")
    pairwise.to_csv(pairs_out, sep="\t", index=False)

    if "condition" in merged.columns and merged["condition"].notna().any():
        summary = merged.groupby("condition", dropna=False)[numeric_cols].mean().reset_index()
        sample_count = merged.groupby("condition", dropna=False).size().rename("sample_count").reset_index()
        summary = sample_count.merge(summary, on="condition", how="left")
        summary.to_csv(cond_out, sep="\t", index=False)
    else:
        pd.DataFrame([{"note": "condition column not available"}]).to_csv(cond_out, sep="\t", index=False)

    notes_out.parent.mkdir(parents=True, exist_ok=True)
    notes_out.write_text(
        "\n".join(
            [
                "# Integrated Correlation Notes",
                "",
                *[f"- {note}" for note in notes],
                f"- Samples in integrated table: {len(merged)}",
                f"- Numeric metrics used: {', '.join(numeric_cols)}",
                f"- Pairwise correlations computed: {len(pairwise)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    try:
        import matplotlib.pyplot as plt  # type: ignore

        heatmap_path = resolve_cfg_path(cfg.get("out_heatmap", "11_correlation/outputs/plots/correlation_heatmap.png"))
        scatter_path = resolve_cfg_path(cfg.get("out_scatter", "11_correlation/outputs/plots/mutational_vs_gene_burden.png"))
        heatmap_path.parent.mkdir(parents=True, exist_ok=True)

        fig, ax = plt.subplots(figsize=(1.2 * len(numeric_cols) + 2, 1.0 * len(numeric_cols) + 2))
        im = ax.imshow(corr_matrix.values.astype(float), vmin=-1, vmax=1, cmap="coolwarm")
        ax.set_xticks(range(len(numeric_cols)))
        ax.set_yticks(range(len(numeric_cols)))
        ax.set_xticklabels(numeric_cols, rotation=45, ha="right")
        ax.set_yticklabels(numeric_cols)
        ax.set_title("Integrated sample-level Spearman correlations")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        fig.tight_layout()
        fig.savefig(heatmap_path, dpi=200)
        plt.close(fig)

        if {"mutation_variant_count", "gene_burden_total"}.issubset(merged.columns):
            scatter = merged[["mutation_variant_count", "gene_burden_total"]].dropna()
            if len(scatter) >= 3:
                rho, p_value = spearmanr(scatter["mutation_variant_count"], scatter["gene_burden_total"])
                scatter_path.parent.mkdir(parents=True, exist_ok=True)
                plt.figure(figsize=(6, 5))
                plt.scatter(scatter["mutation_variant_count"], scatter["gene_burden_total"], s=30, alpha=0.8)
                plt.xlabel("Mutation variant count")
                plt.ylabel("Gene-burden total")
                plt.title(f"Integrated burden correlation (rho={rho:.3f}, p={p_value:.2e})")
                plt.tight_layout()
                plt.savefig(scatter_path, dpi=200)
                plt.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
