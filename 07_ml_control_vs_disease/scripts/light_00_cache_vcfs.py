#!/usr/bin/env python3
"""Parse the 14 GATK PASS VCFs once into compact per-run .npz caches.

Locus key (int64): chrom_index << 56 | pos << 24 | crc32(ref>alt) & 0xFFFFFF.
Per-run arrays: key, vaf (alt/(ref+alt) from AD, as in the benchmark script),
dp (FORMAT DP), is_snp, is_hom_alt.
"""
from __future__ import annotations

import argparse
import zlib
from multiprocessing import Pool
from pathlib import Path

import numpy as np

CHROMS = [f"chr{c}" for c in list(range(1, 23)) + ["X", "Y", "M"]]
CHROM_INDEX = {c: i + 1 for i, c in enumerate(CHROMS)}  # other contigs -> 100+


def encode(chrom: str, pos: int, ref: str, alt: str, extra: dict[str, int]) -> int:
    idx = CHROM_INDEX.get(chrom)
    if idx is None:
        idx = extra.setdefault(chrom, 100 + (zlib.crc32(chrom.encode()) % 27))
    return (idx << 56) | (pos << 24) | (zlib.crc32(f"{ref}>{alt}".encode()) & 0xFFFFFF)


def parse_one(args: tuple[Path, Path]) -> str:
    vcf, out = args
    keys, vafs, dps, snp, hom = [], [], [], [], []
    extra: dict[str, int] = {}
    with vcf.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line[0] == "#":
                continue
            p = line.rstrip("\n").split("\t")
            alt = p[4].split(",")[0]
            keys.append(encode(p[0], int(p[1]), p[3], alt, extra))
            fmt = dict(zip(p[8].split(":"), p[9].split(":")))
            vaf, dp = 1.0, 0
            try:
                ad = [float(v) for v in fmt.get("AD", "").split(",")[:2]]
                vaf = ad[1] / (ad[0] + ad[1]) if ad[0] + ad[1] else 0.0
            except (ValueError, IndexError):
                pass
            try:
                dp = int(fmt.get("DP", "0"))
            except ValueError:
                dp = 0
            vafs.append(vaf)
            dps.append(dp)
            snp.append(len(p[3]) == 1 and len(alt) == 1)
            gt = fmt.get("GT", "")
            hom.append(gt in {"1/1", "1|1"})
    k = np.asarray(keys, dtype=np.int64)
    order = np.argsort(k, kind="stable")
    k = k[order]
    # collapse duplicate keys (keep max VAF), as the benchmark does
    uniq, first = np.unique(k, return_index=True)
    v = np.asarray(vafs, dtype=np.float32)[order]
    vmax = np.maximum.reduceat(v, first)
    np.savez_compressed(
        out,
        key=uniq,
        vaf=vmax,
        dp=np.asarray(dps, dtype=np.int32)[order][first],
        is_snp=np.asarray(snp, dtype=bool)[order][first],
        is_hom=np.asarray(hom, dtype=bool)[order][first],
    )
    return f"{vcf.name}: {len(uniq)} loci"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vcf-dir", type=Path, required=True)
    ap.add_argument("--cache-dir", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=7)
    a = ap.parse_args()
    a.cache_dir.mkdir(parents=True, exist_ok=True)
    tasks = [(v, a.cache_dir / (v.name.split(".")[0] + ".npz")) for v in sorted(a.vcf_dir.glob("*.filtered.vcf"))]
    tasks = [t for t in tasks if not t[1].exists()]
    with Pool(a.jobs) as pool:
        for msg in pool.imap_unordered(parse_one, tasks):
            print(msg, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
