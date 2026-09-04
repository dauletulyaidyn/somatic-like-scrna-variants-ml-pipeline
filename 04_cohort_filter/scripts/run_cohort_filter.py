#!/usr/bin/env python3
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def load_config(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_sample_af(parts):
    fmt = parts[8].split(":") if len(parts) > 8 else []
    sample = parts[9].split(":") if len(parts) > 9 else []
    if not fmt or not sample:
        return 1.0
    values = dict(zip(fmt, sample))
    if "AF" in values and values["AF"] not in (".", ""):
        try:
            return float(values["AF"].split(",")[0])
        except ValueError:
            pass
    if "AD" in values:
        try:
            ref, alt = values["AD"].split(",")[:2]
            ref_n = float(ref)
            alt_n = float(alt)
            total = ref_n + alt_n
            if total > 0:
                return alt_n / total
        except Exception:
            pass
    return 1.0


def main():
    ap = argparse.ArgumentParser(description="Build cohort-common VCF without bcftools.")
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

    vcfs = sorted(vcf_dir.glob("*.filtered.vcf"))
    if not vcfs:
        print("No VCFs found", file=sys.stderr)
        return 2

    loci = defaultdict(lambda: {"count": 0, "max_af": 0.0, "record": None})
    header = []

    for vcf in vcfs:
        seen = set()
        with vcf.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("#"):
                    if vcf == vcfs[0]:
                        header.append(line)
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 8:
                    continue
                key = (parts[0], parts[1], parts[3], parts[4])
                if key in seen:
                    continue
                seen.add(key)
                af = parse_sample_af(parts)
                row = loci[key]
                row["count"] += 1
                row["max_af"] = max(row["max_af"], af)
                if row["record"] is None:
                    row["record"] = parts[:8]

    cohort = outdir / "cohort.common.vcf"
    metrics = Path("outputs/metrics") / "cohort_filter.log"
    metrics.parent.mkdir(parents=True, exist_ok=True)
    selected = 0
    with cohort.open("w", encoding="utf-8") as out, metrics.open("w", encoding="utf-8") as log:
        for line in header:
            out.write(line)
        for key in sorted(loci, key=lambda x: (x[0], int(x[1]))):
            row = loci[key]
            if row["count"] < min_samples or row["max_af"] < min_vaf:
                continue
            record = list(row["record"])
            info = record[7] if record[7] not in (".", "") else ""
            tags = []
            if info:
                tags.append(info)
            tags.append(f"COHORT_COUNT={row['count']}")
            tags.append(f"MAX_AF={row['max_af']:.6f}")
            record[7] = ";".join(tags)
            out.write("\t".join(record) + "\n")
            selected += 1
        log.write(f"Selected cohort-common loci: {selected}\n")
        log.write(f"min_samples={min_samples} min_vaf={min_vaf}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
