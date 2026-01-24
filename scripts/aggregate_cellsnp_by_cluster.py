#!/usr/bin/env python3
import argparse
import gzip
import os
import re
import sys
from typing import Dict, List, Tuple


def open_text(path: str):
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, "r", encoding="utf-8")


def open_text_write(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if path.endswith(".gz"):
        return gzip.open(path, "wt", encoding="utf-8")
    return open(path, "w", encoding="utf-8")


def extract_barcode(cell_id: str) -> str:
    m = re.search(r"([ACGT]{16,})", cell_id)
    if m:
        return m.group(1)
    return cell_id.split("-")[0].split("_")[0]


def find_one(outdir: str, candidates: List[str]) -> str:
    for name in candidates:
        p = os.path.join(outdir, name)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            return p
    return ""


def load_cell_cluster_map(path: str, sample: str, sample_mode: str) -> Dict[str, str]:
    barcode_to_cluster: Dict[str, str] = {}
    with open_text(path) as f:
        header = f.readline().rstrip("\n").split("\t")
        idx_cell = header.index("cell_id") if "cell_id" in header else 0
        idx_sample = header.index("sample") if "sample" in header else 1
        idx_cluster = header.index("cluster") if "cluster" in header else 2

        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) <= max(idx_cell, idx_sample, idx_cluster):
                continue
            sample_val = parts[idx_sample]
            ok = sample_val == sample if sample_mode == "equals" else (sample in sample_val)
            if not ok:
                continue
            barcode = extract_barcode(parts[idx_cell])
            cluster = str(parts[idx_cluster])
            barcode_to_cluster[barcode] = cluster
    return barcode_to_cluster


def main():
    p = argparse.ArgumentParser(
        description="Aggregate cellsnp-lite AD/DP matrices into per-cluster allele counts."
    )
    p.add_argument("--srr", required=True, help="Sample id (e.g., SRR14762239).")
    p.add_argument(
        "--cellsnp-outdir",
        default="",
        help="cellsnp-lite output dir (default: results/cellsnp/<SRR>/).",
    )
    p.add_argument(
        "--cell-cluster-map",
        default="",
        help="TSV(.gz) from cluster annotation with columns: cell_id, sample, cluster",
    )
    p.add_argument(
        "--sample-mode",
        choices=["contains", "equals"],
        default="contains",
        help="How to match obs sample column against --srr.",
    )
    p.add_argument(
        "--min-alt",
        type=int,
        default=3,
        help="Only emit rows with cluster alt_sum >= this.",
    )
    p.add_argument(
        "--out",
        default="",
        help="Output TSV(.gz) path.",
    )
    args = p.parse_args()

    try:
        import numpy as np
        from scipy.io import mmread
    except Exception as e:
        print(
            "Missing Python packages (numpy/scipy).\n"
            f"Error: {e}",
            file=sys.stderr,
        )
        return 2

    outdir = args.cellsnp_outdir
    out_path = args.out

    ad_mtx = find_one(outdir, ["cellSNP.tag.AD.mtx", "cellSNP.tag.AD.mtx.gz"])
    dp_mtx = find_one(outdir, ["cellSNP.tag.DP.mtx", "cellSNP.tag.DP.mtx.gz"])
    var_tsv = find_one(outdir, ["cellSNP.variants.tsv", "cellSNP.variants.tsv.gz"])
    base_vcf = find_one(outdir, ["cellSNP.base.vcf", "cellSNP.base.vcf.gz"])
    bc_tsv = find_one(outdir, ["cellSNP.samples.tsv", "cellSNP.barcodes.tsv", "barcodes.tsv"])

    if not ad_mtx or not dp_mtx or (not var_tsv and not base_vcf) or not bc_tsv:
        print(
            "Missing expected cellsnp-lite outputs under:\n"
            f"  {outdir}\n"
            "Need AD/DP mtx + (variants.tsv or base.vcf) + samples/barcodes.tsv.",
            file=sys.stderr,
        )
        return 2

    barcode_to_cluster = load_cell_cluster_map(
        args.cell_cluster_map, sample=args.srr, sample_mode=args.sample_mode
    )
    if not barcode_to_cluster:
        print(
            f"No cells matched sample '{args.srr}' in cell-cluster map: {args.cell_cluster_map}",
            file=sys.stderr,
        )
        return 2

    # Load barcodes order from cellsnp output.
    out_barcodes: List[str] = []
    with open_text(bc_tsv) as f:
        for line in f:
            out_barcodes.append(line.strip().split("\t")[0])

    # Map column indices to cluster.
    cluster_to_cols: Dict[str, List[int]] = {}
    for idx, bc in enumerate(out_barcodes):
        cluster = barcode_to_cluster.get(bc)
        if cluster is None:
            continue
        cluster_to_cols.setdefault(cluster, []).append(idx)

    if not cluster_to_cols:
        print(
            "No overlap between cellsnp barcodes and cluster map for this sample.",
            file=sys.stderr,
        )
        return 2

    # Load variants list.
    variants: List[Tuple[str, str, str, str]] = []
    if var_tsv:
        with open_text(var_tsv) as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 4:
                    continue
                variants.append((parts[0], parts[1], parts[2], parts[3]))
    else:
        with open_text(base_vcf) as f:
            for line in f:
                if not line or line.startswith("#"):
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 5:
                    continue
                chrom, pos, _vid, ref, alt = parts[:5]
                alt1 = alt.split(",")[0]
                variants.append((chrom, pos, ref, alt1))

    AD = mmread(ad_mtx).tocsr()
    DP = mmread(dp_mtx).tocsr()
    if AD.shape != DP.shape:
        print(f"AD/DP shape mismatch: {AD.shape} vs {DP.shape}", file=sys.stderr)
        return 2

    if AD.shape[0] != len(variants):
        print(
            f"Variant count mismatch: matrix has {AD.shape[0]} rows, variants.tsv has {len(variants)}",
            file=sys.stderr,
        )
        return 2

    with open_text_write(out_path) as out:
        out.write("chrom\tpos\tref\talt\tcluster\talt_sum\tdepth_sum\tvaf\n")
        for cluster, cols in sorted(cluster_to_cols.items(), key=lambda x: x[0]):
            alt_sum = __import__("numpy").asarray(AD[:, cols].sum(axis=1)).reshape(-1)
            depth_sum = __import__("numpy").asarray(DP[:, cols].sum(axis=1)).reshape(-1)
            keep = alt_sum >= args.min_alt
            for i in __import__("numpy").where(keep)[0]:
                chrom, pos, ref, alt = variants[i]
                d = float(depth_sum[i])
                vaf = (float(alt_sum[i]) / d) if d > 0 else 0.0
                out.write(
                    f"{chrom}\t{pos}\t{ref}\t{alt}\t{cluster}\t{int(alt_sum[i])}\t{int(depth_sum[i])}\t{vaf:.6f}\n"
                )

    print(f"Wrote: {out_path}")
    print(f"Clusters: {len(cluster_to_cols)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
