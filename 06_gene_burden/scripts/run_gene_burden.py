#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

import pandas as pd


def main():
    ap = argparse.ArgumentParser(description="Build gene-burden matrix.")
    ap.add_argument("--config", required=True, help="config JSON")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    tsv_path = Path(cfg.get("variant_gene_tsv", ""))
    vcf_dir = Path(cfg.get("vcf_dir", ""))
    out_path = Path(cfg.get("out_matrix", ""))

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
    vcf_files = sorted(vcf_dir.glob("*.vcf"))
    if not vcf_files:
        print("No VCF files found", file=sys.stderr)
        return 2

    for vcf in vcf_files:
        sample_id = vcf.stem.replace(".filtered", "")
        sample_keys = set()
        with vcf.open("r", encoding="utf-8") as f:
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
