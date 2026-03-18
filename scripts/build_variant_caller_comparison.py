#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
FINAL_ROOT = REPO_ROOT.parent
BASELINE = REPO_ROOT / "archive" / "bcftools_baseline" / "results_tables_snapshot"


def count_vcf_records(path: Path) -> int:
    opener = gzip.open if path.suffix == ".gz" else open
    n = 0
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.startswith("#"):
                n += 1
    return n


def read_variant_gene_stats(path: Path) -> tuple[int, int, list[str]]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            df = pd.read_csv(handle, sep="\t")
    else:
        df = pd.read_csv(path, sep="\t")
    gene_col = "gene_name" if "gene_name" in df.columns else "gene_id"
    top = (
        df.groupby(gene_col)
        .size()
        .sort_values(ascending=False)
        .head(20)
        .index.astype(str)
        .tolist()
    )
    return len(df), df[gene_col].astype(str).nunique(), top


def build_sample_table(active_vcf_dir: Path) -> pd.DataFrame:
    baseline = pd.read_csv(BASELINE / "variant_counts_filtered_vs_cohort.csv").rename(
        columns={
            "sample": "sample_id",
            "filtered_number of records:": "n_variants_bcftools",
            "cohort_number of records:": "n_cohort_variants_bcftools",
        }
    )[["sample_id", "n_variants_bcftools", "n_cohort_variants_bcftools"]]

    gatk_rows = []
    for vcf in sorted(active_vcf_dir.glob("*.filtered.vcf.gz")):
        gatk_rows.append(
            {
                "sample_id": vcf.name.replace(".filtered.vcf.gz", ""),
                "n_variants_gatk": count_vcf_records(vcf),
            }
        )
    gatk = pd.DataFrame(gatk_rows)
    if gatk.empty:
        raise FileNotFoundError(f"No active GATK VCFs found in {active_vcf_dir}")

    out = baseline.merge(gatk, on="sample_id", how="outer").sort_values("sample_id").reset_index(drop=True)
    out["delta"] = out["n_variants_gatk"] - out["n_variants_bcftools"]
    out["ratio"] = out["n_variants_gatk"] / out["n_variants_bcftools"].replace({0: pd.NA})
    return out


def build_summary_rows(
    sample_table: pd.DataFrame,
    active_cohort_vcf: Path,
    active_variant_gene_tsv: Path,
    active_mutation_burden_tsv: Path,
) -> pd.DataFrame:
    baseline_summary = pd.read_csv(BASELINE / "table2_variant_counts_summary.csv")
    baseline_variant_gene_rows, baseline_gene_count, baseline_top_genes = read_variant_gene_stats(
        BASELINE / "variant_gene_long.tsv.gz"
    )
    active_variant_gene_rows, active_gene_count, active_top_genes = read_variant_gene_stats(active_variant_gene_tsv)
    overlap = sorted(set(baseline_top_genes) & set(active_top_genes))
    active_mutation_burden = pd.read_csv(active_mutation_burden_tsv, sep="\t")
    active_total_burden = (
        int(active_mutation_burden["variant_count"].sum())
        if "variant_count" in active_mutation_burden.columns
        else int(sample_table["n_variants_gatk"].sum())
    )
    baseline_total_burden = int(sample_table["n_variants_bcftools"].sum())
    baseline_filtered = baseline_summary.loc[baseline_summary["set"] == "filtered"].iloc[0]
    baseline_cohort = baseline_summary.loc[baseline_summary["set"] == "cohort_filtered"].iloc[0]

    rows = [
        {
            "scope": "cohort",
            "entity": "filtered_records_median",
            "bcftools_value": float(baseline_filtered["records_median"]),
            "gatk_value": float(sample_table["n_variants_gatk"].median()),
            "delta": float(sample_table["n_variants_gatk"].median()) - float(baseline_filtered["records_median"]),
            "ratio": float(sample_table["n_variants_gatk"].median()) / float(baseline_filtered["records_median"]),
            "notes": "",
        },
        {
            "scope": "cohort",
            "entity": "filtered_records_min",
            "bcftools_value": float(baseline_filtered["records_min"]),
            "gatk_value": float(sample_table["n_variants_gatk"].min()),
            "delta": float(sample_table["n_variants_gatk"].min()) - float(baseline_filtered["records_min"]),
            "ratio": float(sample_table["n_variants_gatk"].min()) / float(baseline_filtered["records_min"]),
            "notes": "",
        },
        {
            "scope": "cohort",
            "entity": "filtered_records_max",
            "bcftools_value": float(baseline_filtered["records_max"]),
            "gatk_value": float(sample_table["n_variants_gatk"].max()),
            "delta": float(sample_table["n_variants_gatk"].max()) - float(baseline_filtered["records_max"]),
            "ratio": float(sample_table["n_variants_gatk"].max()) / float(baseline_filtered["records_max"]),
            "notes": "",
        },
        {
            "scope": "cohort",
            "entity": "cohort_common_loci",
            "bcftools_value": float(baseline_cohort["records_median"]),
            "gatk_value": float(count_vcf_records(active_cohort_vcf)),
            "delta": float(count_vcf_records(active_cohort_vcf)) - float(baseline_cohort["records_median"]),
            "ratio": float(count_vcf_records(active_cohort_vcf)) / float(baseline_cohort["records_median"]),
            "notes": "Baseline uses the archived cohort-filtered branch summary median.",
        },
        {
            "scope": "cohort",
            "entity": "variant_gene_rows",
            "bcftools_value": baseline_variant_gene_rows,
            "gatk_value": active_variant_gene_rows,
            "delta": active_variant_gene_rows - baseline_variant_gene_rows,
            "ratio": active_variant_gene_rows / baseline_variant_gene_rows if baseline_variant_gene_rows else None,
            "notes": "",
        },
        {
            "scope": "cohort",
            "entity": "genes_with_variant_burden",
            "bcftools_value": baseline_gene_count,
            "gatk_value": active_gene_count,
            "delta": active_gene_count - baseline_gene_count,
            "ratio": active_gene_count / baseline_gene_count if baseline_gene_count else None,
            "notes": "",
        },
        {
            "scope": "cohort",
            "entity": "mutation_burden_total",
            "bcftools_value": baseline_total_burden,
            "gatk_value": active_total_burden,
            "delta": active_total_burden - baseline_total_burden,
            "ratio": active_total_burden / baseline_total_burden if baseline_total_burden else None,
            "notes": "",
        },
        {
            "scope": "cohort",
            "entity": "top20_mutated_gene_overlap_count",
            "bcftools_value": 20,
            "gatk_value": len(overlap),
            "delta": len(overlap) - 20,
            "ratio": len(overlap) / 20.0,
            "notes": ",".join(overlap),
        },
    ]
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build manuscript-ready bcftools vs GATK comparison tables.")
    ap.add_argument("--active-vcf-dir", default=str(REPO_ROOT / "03_gatk_call" / "outputs" / "artifacts"))
    ap.add_argument("--active-cohort-vcf", default=str(REPO_ROOT / "04_cohort_filter" / "outputs" / "artifacts" / "cohort.common.vcf.gz"))
    ap.add_argument("--active-variant-gene", default=str(REPO_ROOT / "05_variant_to_gene" / "outputs" / "artifacts" / "variant_gene_long.tsv"))
    ap.add_argument("--active-mutation-burden", default=str(REPO_ROOT / "10_mutational_analysis" / "outputs" / "metrics" / "mutation_burden.tsv"))
    ap.add_argument("--out-table", default=str(FINAL_ROOT / "results" / "tables" / "table_bcftools_vs_gatk.csv"))
    ap.add_argument("--out-samples", default=str(FINAL_ROOT / "results" / "tables" / "table_bcftools_vs_gatk_per_sample.csv"))
    ap.add_argument("--out-summary", default=str(FINAL_ROOT / "results" / "tables" / "table_bcftools_vs_gatk_summary.csv"))
    args = ap.parse_args()

    sample_table = build_sample_table(Path(args.active_vcf_dir))
    sample_table["scope"] = "sample"
    sample_table["entity"] = sample_table["sample_id"]
    sample_table["metric"] = "filtered_records_per_sample"
    sample_long = sample_table.rename(
        columns={
            "n_variants_bcftools": "bcftools_value",
            "n_variants_gatk": "gatk_value",
        }
    )[["scope", "entity", "metric", "bcftools_value", "gatk_value", "delta", "ratio"]]
    sample_long["notes"] = ""

    summary = build_summary_rows(
        sample_table=sample_table,
        active_cohort_vcf=Path(args.active_cohort_vcf),
        active_variant_gene_tsv=Path(args.active_variant_gene),
        active_mutation_burden_tsv=Path(args.active_mutation_burden),
    )
    summary["metric"] = summary["entity"]
    summary = summary[["scope", "entity", "metric", "bcftools_value", "gatk_value", "delta", "ratio", "notes"]]

    combined = pd.concat([sample_long, summary], ignore_index=True)
    Path(args.out_table).parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(args.out_table, index=False)
    sample_table.to_csv(args.out_samples, index=False)
    summary.to_csv(args.out_summary, index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
