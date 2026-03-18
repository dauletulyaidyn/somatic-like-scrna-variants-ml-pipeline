#!/usr/bin/env python3
import argparse
import gzip
import json
import shutil
import subprocess
import sys
from pathlib import Path


def load_config(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_sample_vaf(fmt: str, sample_value: str) -> float:
    keys = fmt.split(":")
    vals = sample_value.split(":")
    lookup = {k: vals[i] if i < len(vals) else "" for i, k in enumerate(keys)}
    dp_raw = lookup.get("DP", "")
    ad_raw = lookup.get("AD", "")
    try:
        dp = float(dp_raw) if dp_raw not in ("", ".") else 0.0
    except ValueError:
        dp = 0.0
    alt_ad = 0.0
    if ad_raw not in ("", "."):
        parts = ad_raw.split(",")
        if len(parts) >= 2:
            try:
                alt_ad = float(parts[1])
            except ValueError:
                alt_ad = 0.0
    if dp <= 0:
        return 0.0
    return alt_ad / dp


def compress_vcf(src_vcf: Path, out_vcfgz: Path, metrics_log: Path) -> tuple[str, bool]:
    bgzip = shutil.which("bgzip")
    tabix = shutil.which("tabix")
    metrics_log.parent.mkdir(parents=True, exist_ok=True)

    if bgzip:
        with out_vcfgz.open("wb") as out_handle:
            subprocess.run([bgzip, "-f", "-c", str(src_vcf)], check=True, stdout=out_handle)
        indexed = False
        if tabix:
            subprocess.run([tabix, "-f", "-p", "vcf", str(out_vcfgz)], check=True)
            indexed = True
        with metrics_log.open("a", encoding="utf-8") as log:
            log.write("compression_mode\tbgzip\n")
            log.write(f"index_created\t{int(indexed)}\n")
        return "bgzip", indexed

    with src_vcf.open("rt", encoding="utf-8") as src, gzip.open(out_vcfgz, "wt", encoding="utf-8") as dst:
        for line in src:
            dst.write(line)
    with metrics_log.open("a", encoding="utf-8") as log:
        log.write("compression_mode\tgzip\n")
        log.write("index_created\t0\n")
        log.write("index_note\tbgzip/tabix not found on PATH; cellsnp indexing must be created in the target runtime.\n")
    return "gzip", False


def main():
    ap = argparse.ArgumentParser(description="Build cohort-common VCF from per-sample GATK VCFs.")
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
    metrics_dir = Path("outputs/metrics")
    metrics_dir.mkdir(parents=True, exist_ok=True)
    metrics_log = metrics_dir / "cohort_filter.log"

    vcfs = sorted(vcf_dir.glob("*.filtered.vcf.gz"))
    if not vcfs:
        vcfs = sorted(vcf_dir.glob("*.filtered.vcf"))
    if not vcfs:
        print("No VCFs found", file=sys.stderr)
        return 2

    headers: list[str] = []
    contig_order: dict[str, int] = {}
    loci: dict[tuple[str, int, str, str], dict] = {}

    for vcf_path in vcfs:
        opener = gzip.open if vcf_path.suffix == ".gz" else open
        with opener(vcf_path, "rt", encoding="utf-8") as f:
            local_headers: list[str] = []
            for line in f:
                if line.startswith("#"):
                    local_headers.append(line)
                    if not headers:
                        headers = local_headers.copy()
                    if line.startswith("##contig=<ID="):
                        contig = line.split("ID=", 1)[1].split(",", 1)[0].rstrip(">")
                        if contig not in contig_order:
                            contig_order[contig] = len(contig_order)
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 10:
                    continue
                chrom, pos, _id, ref, alt, _qual, _filt, _info, fmt, sample_value = parts[:10]
                alt1 = alt.split(",")[0]
                key = (chrom, int(pos), ref, alt1)
                vaf = parse_sample_vaf(fmt, sample_value)
                entry = loci.setdefault(
                    key,
                    {
                        "count": 0,
                        "max_vaf": 0.0,
                        "line": line.rstrip("\n"),
                    },
                )
                entry["count"] += 1
                if vaf > entry["max_vaf"]:
                    entry["max_vaf"] = vaf
                    entry["line"] = line.rstrip("\n")

    if not headers:
        print("VCFs contain no headers", file=sys.stderr)
        return 2

    kept = []
    for key, entry in loci.items():
        if entry["count"] >= min_samples and entry["max_vaf"] >= min_vaf:
            kept.append((key, entry))

    kept.sort(key=lambda item: (contig_order.get(item[0][0], 10**9), item[0][1], item[0][2], item[0][3]))

    plain_vcf = outdir / "cohort.common.vcf"
    gz_vcf = outdir / "cohort.common.vcf.gz"
    with plain_vcf.open("w", encoding="utf-8") as out:
        for header in headers:
            out.write(header if header.endswith("\n") else header + "\n")
        for _key, entry in kept:
            out.write(entry["line"] + "\n")

    compression_mode, indexed = compress_vcf(plain_vcf, gz_vcf, metrics_log)

    try:
        import pandas as pd

        rows = [
            {"metric": "n_input_vcfs", "value": len(vcfs)},
            {"metric": "n_unique_loci_seen", "value": len(loci)},
            {"metric": "n_cohort_common_loci", "value": len(kept)},
            {"metric": "min_samples", "value": min_samples},
            {"metric": "min_vaf", "value": min_vaf},
            {"metric": "compression_mode", "value": compression_mode},
            {"metric": "index_created", "value": int(indexed)},
            {"metric": "cohort_vcf_size_bytes", "value": gz_vcf.stat().st_size if gz_vcf.exists() else 0},
        ]
        pd.DataFrame(rows).to_csv(metrics_dir / "cohort_filter_summary.tsv", sep="\t", index=False)
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
