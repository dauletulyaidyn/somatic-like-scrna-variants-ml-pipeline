#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr


def load_gene_burden(path: Path):
    df = pd.read_csv(path, sep="\t")
    if "gene_id" not in df.columns:
        raise ValueError("gene_burden missing gene_id")
    sample_cols = [c for c in df.columns if c not in ("gene_id", "gene_name")]
    return df, sample_cols


def load_mut_burden(path: Path):
    df = pd.read_csv(path, sep="\t")
    if "sample_id" not in df.columns:
        raise ValueError("mut_burden missing sample_id")
    return df


def main():
    ap = argparse.ArgumentParser(description="Correlation analysis.")
    ap.add_argument("--config", required=True, help="config JSON")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    gene_burden_path = Path(cfg.get("gene_burden", ""))
    mut_burden_path = Path(cfg.get("mut_burden", ""))

    if not gene_burden_path.exists() or not mut_burden_path.exists():
        print("Missing required inputs", file=sys.stderr)
        return 2

    gb, sample_cols = load_gene_burden(gene_burden_path)
    mut = load_mut_burden(mut_burden_path)

    # total burden per sample
    total_burden = gb[sample_cols].sum(axis=0)
    total_burden = total_burden.reset_index()
    total_burden.columns = ["sample_id", "gene_burden_total"]

    merged = mut.merge(total_burden, on="sample_id", how="inner")
    if merged.empty:
        print("No overlap between mut_burden and gene_burden samples", file=sys.stderr)
        return 2

    rho, p = spearmanr(merged["variant_count"], merged["gene_burden_total"])
    out = pd.DataFrame([{"metric": "spearman", "rho": rho, "p": p}])

    out_path = Path(cfg.get("out_corr", "11_correlation/outputs/metrics/correlation.tsv"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, sep="\t", index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
