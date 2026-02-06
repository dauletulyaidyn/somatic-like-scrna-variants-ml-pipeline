#!/usr/bin/env python3
import argparse
import gzip
import json
import sys
from pathlib import Path

import pandas as pd


def main():
    ap = argparse.ArgumentParser(description="Build gene-burden matrix.")
    ap.add_argument("--config", required=True, help="config JSON")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    repo_root = Path(__file__).resolve().parents[2]

    def resolve_cfg_path(p: str) -> Path:
        p = Path(p)
        return p if p.is_absolute() else (repo_root / p)

    tsv_path = resolve_cfg_path(cfg.get("variant_gene_tsv", ""))
    vcf_dir = resolve_cfg_path(cfg.get("vcf_dir", ""))
    out_path = resolve_cfg_path(cfg.get("out_matrix", ""))

    if not tsv_path.exists():
        print(f"Missing variant-gene TSV: {tsv_path}", file=sys.stderr)
        return 2
    if not vcf_dir.exists():
        print(f"Missing VCF dir: {vcf_dir}", file=sys.stderr)
        return 2

    df = pd.read_csv(tsv_path, sep="\t")
    required = {"chrom", "pos", "ref", "alt", "gene_id", "gene_name"}
    if not required.issubset(df.columns):
        print("Missing required columns in variant-gene TSV", file=sys.stderr)
        return 2

    # Build variant->gene key map
    df["key"] = df["chrom"].astype(str) + ":" + df["pos"].astype(str) + ":" + df["ref"] + ":" + df["alt"]
    var_to_gene = df.groupby(["key", "gene_id", "gene_name"]).size().reset_index()[["key", "gene_id", "gene_name"]]

    # Initialize burden matrix with genes as rows
    genes = var_to_gene[["gene_id", "gene_name"]].drop_duplicates().reset_index(drop=True)

    # Parse per-sample VCFs and count variants per gene
    vcf_files = sorted(vcf_dir.glob("*.vcf.gz"))
    if not vcf_files:
        vcf_files = sorted(vcf_dir.glob("*.vcf"))
    if not vcf_files:
        print("No VCF files found", file=sys.stderr)
        return 2

    for vcf in vcf_files:
        sample_id = vcf.name.replace(".filtered.vcf.gz", "").replace(".filtered.vcf", "")
        if sample_id.endswith("Aligned.sortedByCoord.out"):
            sample_id = sample_id.replace("Aligned.sortedByCoord.out", "")
        sample_keys = set()
        opener = gzip.open if vcf.suffix == ".gz" else open
        with opener(vcf, "rt", encoding="utf-8") as f:
            for line in f:
                if line.startswith("#"):
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 5:
                    continue
                chrom, pos, _id, ref, alt = parts[:5]
                alt1 = alt.split(",")[0]
                sample_keys.add(f"{chrom}:{pos}:{ref}:{alt1}")

        hits = var_to_gene[var_to_gene["key"].isin(sample_keys)]
        counts = hits.groupby(["gene_id", "gene_name"]).size().reset_index(name=sample_id)
        genes = genes.merge(counts, on=["gene_id", "gene_name"], how="left")
        genes[sample_id] = genes[sample_id].fillna(0).astype(int)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    genes.to_csv(out_path, sep="\t", index=False)
    print(f"Wrote: {out_path}")

    # Metrics and optional plot for reporting.
    metrics_dir = Path("outputs/metrics")
    metrics_dir.mkdir(parents=True, exist_ok=True)

    sample_cols = [c for c in genes.columns if c not in ("gene_id", "gene_name")]
    total = genes[sample_cols].sum(axis=0).astype(int)
    total_path = metrics_dir / "gene_burden_total_per_sample.tsv"
    total.reset_index().rename(columns={"index": "sample_id", 0: "gene_burden_total"}).to_csv(
        total_path, sep="\t", index=False
    )

    summary_path = metrics_dir / "gene_burden_summary.tsv"
    with summary_path.open("w", encoding="utf-8") as f:
        f.write("metric\tvalue\n")
        f.write(f"n_genes\t{len(genes)}\n")
        f.write(f"n_samples\t{len(sample_cols)}\n")
        f.write(f"total_burden_sum\t{int(total.sum())}\n")
        if len(total) > 0:
            f.write(f"total_burden_min\t{int(total.min())}\n")
            f.write(f"total_burden_median\t{int(total.median())}\n")
            f.write(f"total_burden_max\t{int(total.max())}\n")

    try:
        import matplotlib.pyplot as plt  # type: ignore

        plot_dir = Path("outputs/plots")
        plot_dir.mkdir(parents=True, exist_ok=True)
        s = total.sort_values(ascending=True)
        plt.figure(figsize=(10, max(4, 0.25 * len(s) + 1)))
        plt.barh(s.index.astype(str), s.values)
        plt.xlabel("Gene-burden total (variants mapped to genes)")
        plt.title("Total gene-burden per sample")
        plt.tight_layout()
        plt.savefig(plot_dir / "gene_burden_total_per_sample.png", dpi=200)
        plt.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
