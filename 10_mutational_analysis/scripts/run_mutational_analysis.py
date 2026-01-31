#!/usr/bin/env python3
import argparse
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd


def parse_vcf(vcf_path: Path):
    variants = []
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
            variants.append((chrom, pos, ref, alt1))
    return variants


def main():
    ap = argparse.ArgumentParser(description="Mutational analysis summaries.")
    ap.add_argument("--config", required=True, help="config JSON")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    repo_root = Path(__file__).resolve().parents[2]

    def resolve_cfg_path(p: str) -> Path:
        p = Path(p)
        return p if p.is_absolute() else (repo_root / p)

    vcf_dir = resolve_cfg_path(cfg.get("vcf_dir", ""))
    driver_genes_path = resolve_cfg_path(cfg.get("driver_genes", ""))

    if not vcf_dir.exists():
        print(f"Missing vcf_dir: {vcf_dir}", file=sys.stderr)
        return 2

    vcf_files = sorted(vcf_dir.glob("*.vcf.gz"))
    if not vcf_files:
        vcf_files = sorted(vcf_dir.glob("*.vcf"))
    if not vcf_files:
        print("No VCFs found", file=sys.stderr)
        return 2

    driver_genes = set()
    if driver_genes_path.exists():
        driver_genes = set([l.strip() for l in driver_genes_path.read_text(encoding="utf-8").splitlines() if l.strip()])

    burden_rows = []
    sig_rows = []
    driver_rows = []

    for vcf in vcf_files:
        sample_id = vcf.name.replace(".filtered.vcf.gz", "").replace(".filtered.vcf", "")
        if sample_id.endswith("Aligned.sortedByCoord.out"):
            sample_id = sample_id.replace("Aligned.sortedByCoord.out", "")
        vars_ = parse_vcf(vcf)

        # burden
        burden_rows.append({"sample_id": sample_id, "variant_count": len(vars_)})

        # signatures (simple base change counts)
        sig = Counter()
        for _chrom, _pos, ref, alt in vars_:
            if len(ref) == 1 and len(alt) == 1:
                sig[f"{ref}>{alt}"] += 1
        sig_row = {"sample_id": sample_id}
        sig_row.update(sig)
        sig_rows.append(sig_row)

        # driver hits (placeholder: none without annotation)
        if driver_genes:
            driver_rows.append({"sample_id": sample_id, "driver_hits": 0})

    out_burden = resolve_cfg_path(cfg.get("out_burden", "outputs/metrics/mutation_burden.tsv"))
    out_signatures = resolve_cfg_path(cfg.get("out_signatures", "outputs/metrics/mutation_signatures.tsv"))
    out_drivers = resolve_cfg_path(cfg.get("out_drivers", "outputs/metrics/driver_counts.tsv"))
    out_pathways = resolve_cfg_path(cfg.get("out_pathways", "outputs/metrics/pathway_enrichment.tsv"))

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
