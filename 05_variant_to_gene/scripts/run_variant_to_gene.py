#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path


def open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def parse_gtf_attrs(attrs: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in attrs.split(";"):
        item = item.strip()
        if not item or " " not in item:
            continue
        key, value = item.split(" ", 1)
        parsed[key] = value.strip().strip('"')
    return parsed


def load_gene_intervals(gtf_path: Path) -> dict[str, list[tuple[int, int, str, str, str]]]:
    genes_by_chrom: dict[str, list[tuple[int, int, str, str, str]]] = defaultdict(list)
    transcript_bounds: dict[tuple[str, str, str], list[object]] = {}
    saw_gene_feature = False

    with open_text(gtf_path) as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 9:
                continue
            chrom, _source, feature, start, end, _score, strand, _frame, attrs = parts
            attrs_dict = parse_gtf_attrs(attrs)
            gene_id = attrs_dict.get("gene_id", "")
            gene_name = attrs_dict.get("gene_name", gene_id)
            if not gene_id:
                continue

            start_i = int(start)
            end_i = int(end)
            if feature == "gene":
                genes_by_chrom[chrom].append((start_i, end_i, strand, gene_id, gene_name))
                saw_gene_feature = True
                continue

            if feature == "transcript" and not saw_gene_feature:
                key = (chrom, gene_id, gene_name)
                bounds = transcript_bounds.get(key)
                if bounds is None:
                    transcript_bounds[key] = [start_i, end_i, strand]
                else:
                    bounds[0] = min(bounds[0], start_i)
                    bounds[1] = max(bounds[1], end_i)

    if not saw_gene_feature:
        for (chrom, gene_id, gene_name), (start_i, end_i, strand) in transcript_bounds.items():
            genes_by_chrom[chrom].append((int(start_i), int(end_i), str(strand), gene_id, gene_name))

    for chrom in list(genes_by_chrom):
        genes_by_chrom[chrom].sort(key=lambda row: (row[0], row[1], row[3], row[4]))
    return genes_by_chrom


def annotate_vcf(vcf_path: Path, genes_by_chrom: dict[str, list[tuple[int, int, str, str, str]]], out_tsv: Path) -> tuple[int, int]:
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    overlap_rows = 0
    variant_count = 0

    current_chrom = None
    chrom_genes: list[tuple[int, int, str, str, str]] = []
    gene_ptr = 0
    active_genes: list[tuple[int, int, str, str, str]] = []

    with open_text(vcf_path) as handle, out_tsv.open("w", encoding="utf-8", newline="") as out_handle:
        writer = csv.writer(out_handle, delimiter="\t")
        writer.writerow(["chrom", "pos", "ref", "alt", "gene_id", "gene_name", "strand"])

        for line in handle:
            if line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 5:
                continue

            chrom, pos, _id, ref, alt = parts[:5]
            pos_i = int(pos)
            alt1 = alt.split(",")[0]
            variant_count += 1

            if chrom != current_chrom:
                current_chrom = chrom
                chrom_genes = genes_by_chrom.get(chrom, [])
                gene_ptr = 0
                active_genes = []

            while gene_ptr < len(chrom_genes) and chrom_genes[gene_ptr][0] <= pos_i:
                active_genes.append(chrom_genes[gene_ptr])
                gene_ptr += 1

            if active_genes:
                active_genes = [gene for gene in active_genes if gene[1] >= pos_i]

            if not active_genes:
                continue

            seen = set()
            for start_i, end_i, strand, gene_id, gene_name in active_genes:
                if pos_i < start_i or pos_i > end_i:
                    continue
                key = (gene_id, gene_name, strand)
                if key in seen:
                    continue
                seen.add(key)
                writer.writerow([chrom, pos_i, ref, alt1, gene_id, gene_name, strand])
                overlap_rows += 1

    return variant_count, overlap_rows


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

    genes_by_chrom = load_gene_intervals(gtf_path)
    gene_total = sum(len(rows) for rows in genes_by_chrom.values())
    if gene_total == 0:
        print("No gene intervals parsed from GTF", file=sys.stderr)
        return 2

    variant_count, overlap_rows = annotate_vcf(vcf_path, genes_by_chrom, out_tsv)
    if variant_count == 0:
        print("VCF has no variants", file=sys.stderr)
        return 2
    if overlap_rows == 0:
        print("No variant-gene overlaps found", file=sys.stderr)
        return 2

    print(f"Wrote: {out_tsv}")
    print(f"Gene intervals: {gene_total}")
    print(f"Variants processed: {variant_count}")
    print(f"Overlap rows: {overlap_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
