#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


def load_config(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser(description="Build cohort-common VCF.")
    ap.add_argument("--vcf-dir", required=True, help="Directory with per-sample VCFs")
    ap.add_argument("--config", required=True, help="cohort filter config JSON")
    ap.add_argument("--outdir", default="outputs/artifacts", help="Output directory")
    args = ap.parse_args()

    cfg = load_config(Path(args.config))
    min_samples = int(cfg.get("min_samples", 4))
    min_vaf = float(cfg.get("min_vaf", 0.05))

    vcf_dir = Path(args.vcf_dir)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    vcfs = sorted(vcf_dir.glob("*.vcf.gz"))
    if not vcfs:
        vcfs = sorted(vcf_dir.glob("*.vcf"))
    if not vcfs:
        print("No VCFs found", file=sys.stderr)
        return 2

    # Merge VCFs to compute cohort counts
    merged = outdir / "cohort.merged.vcf.gz"
    cohort = outdir / "cohort.common.vcf.gz"

    merge_cmd = [
        "bcftools", "merge",
        "-m", "none",
        "-Oz",
        "-o", str(merged),
    ] + [str(v) for v in vcfs]

    filter_expr = f"COUNT(GT!=\".\")>={min_samples} && MAX(INFO/AF)>={min_vaf}"
    filter_cmd = [
        "bcftools", "view",
        "-i", filter_expr,
        "-Oz",
        "-o", str(cohort),
        str(merged),
    ]

    rc = Path("outputs/metrics").joinpath("cohort_filter.log")
    rc.parent.mkdir(parents=True, exist_ok=True)
    with rc.open("w", encoding="utf-8") as log:
        log.write("CMD: " + " ".join(merge_cmd) + "\n")
        log.flush()
        if __import__("subprocess").call(merge_cmd, stdout=log, stderr=log) != 0:
            return 2
        log.write("CMD: " + " ".join(filter_cmd) + "\n")
        log.flush()
        if __import__("subprocess").call(filter_cmd, stdout=log, stderr=log) != 0:
            return 2

    # index
    if __import__("subprocess").call(["tabix", "-p", "vcf", str(cohort)]) != 0:
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
