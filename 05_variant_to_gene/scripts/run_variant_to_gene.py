#!/usr/bin/env python3
import argparse
import gzip
import json
import sys
from pathlib import Path

from collections import defaultdict


def parse_gtf(gtf_path: Path):
    genes_by_chrom = defaultdict(list)
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
            genes_by_chrom[chrom].append((int(start), int(end), strand, gene_id, gene_name))
    for chrom in genes_by_chrom:
        genes_by_chrom[chrom].sort(key=lambda x: x[0])
    return genes_by_chrom


def parse_vcf(vcf_path: Path):
    variants = defaultdict(list)
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
            variants[chrom].append((int(pos), ref, alt1))
    for chrom in variants:
        variants[chrom].sort(key=lambda x: x[0])
    return variants


def main():
    ap = argparse.ArgumentParser(description="Annotate cohort VCF with gene context.")
    ap.add_argument("--config", required=True, help="config JSON")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    repo_root = Path(__file__).resolve().parents[2]

    def resolve_cfg_path(p: str) -> Path:
        p = Path(p)
        return p if p.is_absolute() else (repo_root / p)

    vcf_path = resolve_cfg_path(cfg.get("cohort_vcf", ""))
    gtf_path = resolve_cfg_path(cfg.get("gtf", ""))
    out_tsv = resolve_cfg_path(cfg.get("out_tsv", ""))

    if not vcf_path.exists():
        print(f"Missing VCF: {vcf_path}", file=sys.stderr)
        return 2
    if not gtf_path.exists():
        print(f"Missing GTF: {gtf_path}", file=sys.stderr)
        return 2

    genes_by_chrom = parse_gtf(gtf_path)
    if not genes_by_chrom:
        print("No genes parsed from GTF", file=sys.stderr)
        return 2

    variants_by_chrom = parse_vcf(vcf_path)
    if not variants_by_chrom:
        print("VCF has no variants", file=sys.stderr)
        return 2

    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    wrote = 0
    gene_counts = defaultdict(int)
    variant_keys = set()
    with out_tsv.open("w", encoding="utf-8") as out:
        out.write("chrom\tpos\tref\talt\tgene_id\tgene_name\tstrand\n")
        for chrom, variants in variants_by_chrom.items():
            genes = genes_by_chrom.get(chrom)
            if not genes:
                continue
            active = []
            gi = 0
            for pos, ref, alt in variants:
                while gi < len(genes) and genes[gi][0] <= pos:
                    active.append(genes[gi])
                    gi += 1
                if active:
                    active = [g for g in active if g[1] >= pos]
                for start, end, strand, gene_id, gene_name in active:
                    if start <= pos <= end:
                        out.write(f"{chrom}\t{pos}\t{ref}\t{alt}\t{gene_id}\t{gene_name}\t{strand}\n")
                        wrote += 1
                        gene_counts[gene_name] += 1
                        variant_keys.add((chrom, pos, ref, alt))

    if wrote == 0:
        print("No variant-gene overlaps found", file=sys.stderr)
        return 2

    # Metrics table for the report bundle.
    metrics_dir = Path("outputs/metrics")
    metrics_dir.mkdir(parents=True, exist_ok=True)
    summary_path = metrics_dir / "variant_to_gene_summary.tsv"
    top_genes = sorted(gene_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:25]
    with summary_path.open("w", encoding="utf-8") as f:
        f.write("metric\tvalue\n")
        f.write(f"n_variant_gene_rows\t{wrote}\n")
        f.write(f"n_unique_variants_overlapping_gene\t{len(variant_keys)}\n")
        f.write(f"n_genes_with_variant\t{len(gene_counts)}\n")
        if top_genes:
            f.write(f"top_gene_by_rows\t{top_genes[0][0]}\n")
            f.write(f"top_gene_rows\t{top_genes[0][1]}\n")

    top_path = metrics_dir / "variant_to_gene_top_genes.tsv"
    with top_path.open("w", encoding="utf-8") as f:
        f.write("gene_name\tn_rows\n")
        for g, c in top_genes:
            f.write(f"{g}\t{c}\n")

    # Optional plot (best-effort).
    try:
        import matplotlib.pyplot as plt  # type: ignore

        if top_genes:
            plot_dir = Path("outputs/plots")
            plot_dir.mkdir(parents=True, exist_ok=True)
            names = [g for g, _c in top_genes[::-1]]
            vals = [c for _g, c in top_genes[::-1]]
            plt.figure(figsize=(10, max(4, 0.25 * len(names) + 1)))
            plt.barh(names, vals)
            plt.xlabel("Variant-gene rows")
            plt.title("Top genes by overlapping variants (cohort VCF)")
            plt.tight_layout()
            plt.savefig(plot_dir / "variant_to_gene_top_genes.png", dpi=200)
            plt.close()
    except Exception:
        pass

    print(f"Wrote: {out_tsv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
