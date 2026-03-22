#!/usr/bin/env python3
import argparse
import json
import sys
import gzip
from pathlib import Path

import pandas as pd


def parse_gtf(gtf_path: Path):
    genes = []
    with gtf_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 9:
                continue
            chrom, source, feature, start, end, score, strand, frame, attrs = parts
            if feature != "gene":
                continue
            attrs_dict = {}
            for item in attrs.split(";"):
                item = item.strip()
                if not item:
                    continue
                if " " in item:
                    k, v = item.split(" ", 1)
                    attrs_dict[k] = v.strip("\"")
            gene_id = attrs_dict.get("gene_id", "")
            gene_name = attrs_dict.get("gene_name", gene_id)
            genes.append((chrom, int(start), int(end), strand, gene_id, gene_name))
    df = pd.DataFrame(genes, columns=["chrom", "start", "end", "strand", "gene_id", "gene_name"])
    return df


def parse_vcf(vcf_path: Path):
    rows = []
    opener = gzip.open if vcf_path.suffix == ".gz" else open
    with opener(vcf_path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 5:
                continue
            chrom, pos, _id, ref, alt = parts[:5]
            alt1 = alt.split(",")[0]
            rows.append((chrom, int(pos), ref, alt1))
    return pd.DataFrame(rows, columns=["chrom", "pos", "ref", "alt"])


def main():
    ap = argparse.ArgumentParser(description="Annotate cohort VCF with gene context.")
    ap.add_argument("--config", required=True, help="config JSON")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    vcf_path = Path(cfg.get("cohort_vcf", ""))
    gtf_path = Path(cfg.get("gtf", ""))
    out_tsv = Path(cfg.get("out_tsv", ""))

    if not vcf_path.exists():
        print(f"Missing VCF: {vcf_path}", file=sys.stderr)
        return 2
    if not gtf_path.exists():
        print(f"Missing GTF: {gtf_path}", file=sys.stderr)
        return 2

    genes = parse_gtf(gtf_path)
    if genes.empty:
        print("No genes parsed from GTF", file=sys.stderr)
        return 2

    vcf = parse_vcf(vcf_path)
    if vcf.empty:
        print("VCF has no variants", file=sys.stderr)
        return 2

    # Simple overlap join (chrom + position within gene bounds)
    vcf["key"] = 1
    genes["key"] = 1
    merged = vcf.merge(genes, on=["key"], suffixes=("", "_g"))
    merged = merged[(merged["chrom"] == merged["chrom_g"]) & (merged["pos"] >= merged["start"]) & (merged["pos"] <= merged["end"])]

    if merged.empty:
        print("No variant-gene overlaps found", file=sys.stderr)
        return 2

    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    merged[["chrom", "pos", "ref", "alt", "gene_id", "gene_name", "strand"]].to_csv(out_tsv, sep="\t", index=False)
    print(f"Wrote: {out_tsv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
