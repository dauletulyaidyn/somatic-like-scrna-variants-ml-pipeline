#!/usr/bin/env python3
import argparse
import gzip
import sys
from pathlib import Path

import numpy as np
from scipy.io import mmread


def read_barcodes(path: Path):
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_variants(vcf_path: Path):
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
    return rows


def load_cluster_map(path: Path, sample_id: str):
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return {}
    header = lines[0].split("\t")
    idx = {name: i for i, name in enumerate(header)}
    if "barcode" not in idx or "cluster" not in idx:
        raise ValueError("cell_cluster_map must include columns: barcode, cluster")
    has_sample = "sample_id" in idx
    mapping = {}
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        if has_sample and parts[idx["sample_id"]] != sample_id:
            continue
        bc = parts[idx["barcode"]]
        cl = parts[idx["cluster"]]
        mapping[bc] = cl
    return mapping


def main():
    ap = argparse.ArgumentParser(description="Aggregate cellSNP by cluster.")
    ap.add_argument("--srr", required=True)
    ap.add_argument("--cellsnp-outdir", required=True)
    ap.add_argument("--cell-cluster-map", required=True)
    ap.add_argument("--min-alt", type=int, default=3)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    outdir = Path(args.cellsnp_outdir)
    samples_path = outdir / "cellSNP.samples.tsv"
    ad_path = outdir / "cellSNP.tag.AD.mtx"
    dp_path = outdir / "cellSNP.tag.DP.mtx"
    vcf_path = outdir / "cellSNP.cells.vcf"

    if not samples_path.exists() or not ad_path.exists() or not dp_path.exists() or not vcf_path.exists():
        print("Missing required cellSNP outputs", file=sys.stderr)
        return 2

    barcodes = read_barcodes(samples_path)
    cluster_map = load_cluster_map(Path(args.cell_cluster_map), args.srr)
    if not cluster_map:
        print("No cluster mappings found for sample", file=sys.stderr)
        return 2

    idx_by_cluster = {}
    for i, bc in enumerate(barcodes):
        cl = cluster_map.get(bc)
        if cl is None:
            continue
        idx_by_cluster.setdefault(cl, []).append(i)

    if not idx_by_cluster:
        print("No barcodes matched cluster map", file=sys.stderr)
        return 2

    ad = mmread(str(ad_path)).tocsr()
    dp = mmread(str(dp_path)).tocsr()
    variants = read_variants(vcf_path)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if out_path.suffix == ".gz" else open
    with opener(out_path, "wt", encoding="utf-8") as out:
        out.write("chrom\tpos\tref\talt\tcluster\tad_sum\tdp_sum\n")
        for cluster, idxs in idx_by_cluster.items():
            cols = np.array(idxs, dtype=int)
            ad_sum = np.asarray(ad[:, cols].sum(axis=1)).ravel()
            dp_sum = np.asarray(dp[:, cols].sum(axis=1)).ravel()
            for (chrom, pos, ref, alt), a, d in zip(variants, ad_sum, dp_sum):
                if a < args.min_alt:
                    continue
                out.write(f"{chrom}\t{pos}\t{ref}\t{alt}\t{cluster}\t{int(a)}\t{int(d)}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
