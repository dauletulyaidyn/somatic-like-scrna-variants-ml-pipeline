#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd


def open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def normalize_sample_id(value: str | Path) -> str:
    name = value.name if isinstance(value, Path) else str(value)
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


def candidate_vcfs(vcf_dir: Path) -> list[Path]:
    patterns = [
        "*.filtered.vcf",
        "*.filtered.vcf.gz",
        "*.filtered.annotated.vcf",
        "*.filtered.annotated.vcf.gz",
        "*.raw.vcf",
        "*.raw.vcf.gz",
        "*.vcf",
        "*.vcf.gz",
    ]
    priority = {pattern: idx for idx, pattern in enumerate(patterns)}
    best_by_sample: dict[str, tuple[int, Path]] = {}
    for pattern in patterns:
        for path in sorted(vcf_dir.glob(pattern)):
            sample_id = normalize_sample_id(path)
            rank = priority[pattern]
            current = best_by_sample.get(sample_id)
            if current is None or rank < current[0]:
                best_by_sample[sample_id] = (rank, path)
    return [item[1] for item in sorted(best_by_sample.values(), key=lambda pair: pair[1].name.lower())]


def parse_vcf(vcf_path: Path):
    variants = []
    with open_text(vcf_path) as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 5:
                continue
            chrom, pos, _id, ref, alt = parts[:5]
            alt1 = alt.split(",")[0]
            variants.append((chrom, pos, ref, alt1))
    return variants


def main():
    ap = argparse.ArgumentParser(description="Mutational analysis summaries.")
    ap.add_argument("--config", required=True, help="config JSON")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    vcf_dir = Path(cfg.get("vcf_dir", ""))
    driver_genes_path = Path(cfg.get("driver_genes", ""))

    if not vcf_dir.exists():
        print(f"Missing vcf_dir: {vcf_dir}", file=sys.stderr)
        return 2

    vcf_files = candidate_vcfs(vcf_dir)
    if not vcf_files:
        print("No VCFs found", file=sys.stderr)
        return 2

    driver_genes = set()
    if driver_genes_path.exists():
        driver_genes = {line.strip() for line in driver_genes_path.read_text(encoding="utf-8").splitlines() if line.strip()}

    burden_rows = []
    sig_rows = []
    driver_rows = []

    for vcf in vcf_files:
        sample_id = normalize_sample_id(vcf)
        vars_ = parse_vcf(vcf)

        snv_count = sum(1 for _chrom, _pos, ref, alt in vars_ if len(ref) == 1 and len(alt) == 1)
        burden_rows.append(
            {
                "sample_id": sample_id,
                "variant_count": len(vars_),
                "snv_count": snv_count,
                "indel_count": len(vars_) - snv_count,
            }
        )

        sig = Counter()
        for _chrom, _pos, ref, alt in vars_:
            if len(ref) == 1 and len(alt) == 1:
                sig[f"{ref}>{alt}"] += 1
        sig_row = {"sample_id": sample_id}
        sig_row.update(sig)
        sig_rows.append(sig_row)

        if driver_genes:
            driver_rows.append({"sample_id": sample_id, "driver_hits": 0})

    out_burden = Path(cfg.get("out_burden", "outputs/metrics/mutation_burden.tsv"))
    out_signatures = Path(cfg.get("out_signatures", "outputs/metrics/mutation_signatures.tsv"))
    out_drivers = Path(cfg.get("out_drivers", "outputs/metrics/driver_counts.tsv"))
    out_pathways = Path(cfg.get("out_pathways", "outputs/metrics/pathway_enrichment.tsv"))

    out_burden.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(burden_rows).to_csv(out_burden, sep="\t", index=False)
    pd.DataFrame(sig_rows).fillna(0).to_csv(out_signatures, sep="\t", index=False)

    if driver_genes:
        pd.DataFrame(driver_rows).to_csv(out_drivers, sep="\t", index=False)
    else:
        pd.DataFrame([{"note": "driver_genes list not provided"}]).to_csv(out_drivers, sep="\t", index=False)

    pd.DataFrame([{"note": "pathway enrichment placeholder"}]).to_csv(out_pathways, sep="\t", index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
