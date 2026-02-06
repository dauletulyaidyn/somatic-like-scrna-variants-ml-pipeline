#!/usr/bin/env python3
import argparse
import gzip
import json
import math
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


def load_gene_burden_matrix(path: Path) -> tuple[pd.DataFrame, list[str]]:
    df = pd.read_csv(path, sep="\t")
    if "gene_name" not in df.columns:
        raise ValueError("gene_burden_matrix must contain column: gene_name")
    sample_cols = [c for c in df.columns if c not in ("gene_id", "gene_name")]
    if not sample_cols:
        raise ValueError("gene_burden_matrix has no sample columns")
    return df, sample_cols


def parse_gmt(path: Path) -> list[dict[str, object]]:
    """
    Returns list of dicts: {term, desc, genes(set[str])}
    GMT format: term<TAB>desc<TAB>gene1<TAB>gene2...
    """
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for ln in f:
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            parts = ln.split("\t")
            if len(parts) < 3:
                continue
            term = parts[0].strip()
            desc = parts[1].strip()
            genes = {g.strip() for g in parts[2:] if g.strip()}
            if not term or not genes:
                continue
            rows.append({"term": term, "desc": desc, "genes": genes})
    return rows


def bh_fdr(p_values: list[float]) -> list[float]:
    m = len(p_values)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: p_values[i])
    q = [0.0] * m
    prev = 1.0
    for rank, idx in enumerate(reversed(order), start=1):
        p = float(p_values[idx])
        q_i = min(prev, p * m / (m - rank + 1))
        q[idx] = q_i
        prev = q_i
    return q


def _log_comb(n: int, k: int) -> float:
    if k < 0 or k > n:
        return float("-inf")
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def hypergeom_sf(k_minus_1: int, N: int, K: int, n: int) -> float:
    """
    Survival function P[X > k_minus_1] for X ~ Hypergeom(N, K, n).
    Uses scipy if available; otherwise an exact log-sum-exp fallback.
    """
    try:
        from scipy.stats import hypergeom as _hg  # type: ignore

        return float(_hg.sf(k_minus_1, N, K, n))
    except Exception:
        k0 = k_minus_1 + 1
        hi = min(n, K)
        if k0 > hi:
            return 0.0

        log_den = _log_comb(N, n)
        logs = []
        for k in range(k0, hi + 1):
            logs.append(_log_comb(K, k) + _log_comb(N - K, n - k) - log_den)
        m = max(logs)
        if m == float("-inf"):
            return 0.0
        s = sum(math.exp(x - m) for x in logs)
        return float(min(1.0, math.exp(m) * s))


def run_pathway_enrichment(
    gene_burden_path: Path,
    gmt_paths: list[Path],
    out_pathways: Path,
    *,
    min_query_genes: int = 5,
    min_term_size: int = 10,
    max_term_size: int = 2000,
    min_overlap: int = 3,
    top_terms_per_sample: int = 50,
    include_cohort_union: bool = True,
) -> None:
    gb, sample_cols = load_gene_burden_matrix(gene_burden_path)
    gb = gb.copy()
    gb["gene_name"] = gb["gene_name"].astype(str)
    universe = {g for g in gb["gene_name"].tolist() if g and g != "nan"}
    if not universe:
        raise ValueError("gene_burden_matrix has empty gene_name universe")

    N = len(universe)

    term_rows: list[dict[str, object]] = []
    for gmt_path in gmt_paths:
        if not gmt_path.exists():
            raise FileNotFoundError(f"Missing gene sets GMT: {gmt_path}")
        for r in parse_gmt(gmt_path):
            genes = set(r["genes"]) & universe  # type: ignore[arg-type]
            if len(genes) < min_term_size or len(genes) > max_term_size:
                continue
            term_rows.append(
                {
                    "geneset": gmt_path.stem,
                    "term": r["term"],
                    "desc": r["desc"],
                    "genes": genes,
                }
            )

    if not term_rows:
        raise ValueError("No usable gene sets after filtering (check GMT content and gene symbols)")

    queries: dict[str, set[str]] = {}
    for sample_id in sample_cols:
        sub = gb.loc[gb[sample_id].astype(float) > 0, "gene_name"]
        q = {g for g in sub.astype(str).tolist() if g and g != "nan"}
        if len(q) >= min_query_genes:
            queries[sample_id] = q

    if include_cohort_union and queries:
        union = set().union(*queries.values())
        if len(union) >= min_query_genes:
            queries["cohort_union"] = union

    out_rows: list[dict[str, object]] = []
    for sample_id, q in queries.items():
        n = len(q)
        for tr in term_rows:
            genes = tr["genes"]  # type: ignore[assignment]
            overlap = q & genes  # type: ignore[arg-type]
            k = len(overlap)
            if k < min_overlap:
                continue
            M = len(genes)  # type: ignore[arg-type]
            p = hypergeom_sf(k - 1, N, M, n)
            expected = (n * M) / max(1, N)
            enr_ratio = (k / max(1.0, expected)) if expected > 0 else float("inf")
            out_rows.append(
                {
                    "sample_id": sample_id,
                    "geneset": tr["geneset"],
                    "term": tr["term"],
                    "desc": tr["desc"],
                    "p_value": p,
                    "fdr": 1.0,
                    "overlap_size": k,
                    "term_size": M,
                    "query_size": n,
                    "universe_size": N,
                    "enrichment_ratio": enr_ratio,
                    "overlap_genes": ",".join(sorted(overlap)),
                }
            )

    out_pathways.parent.mkdir(parents=True, exist_ok=True)
    if not out_rows:
        pd.DataFrame([{"note": "no eligible enrichments (check gene sets and thresholds)"}]).to_csv(
            out_pathways, sep="\t", index=False
        )
        return

    res = pd.DataFrame(out_rows)
    for sample_id, idx in res.groupby("sample_id").groups.items():
        pvals = res.loc[list(idx), "p_value"].astype(float).tolist()
        res.loc[list(idx), "fdr"] = bh_fdr(pvals)

    res = res.sort_values(["sample_id", "fdr", "p_value", "overlap_size"], ascending=[True, True, True, False])
    if top_terms_per_sample and top_terms_per_sample > 0:
        res = res.groupby("sample_id", as_index=False).head(int(top_terms_per_sample))

    res.to_csv(out_pathways, sep="\t", index=False)


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
    gene_burden_path = resolve_cfg_path(cfg.get("gene_burden_matrix", ""))

    gmt_cfg = cfg.get("gene_sets_gmt", "")
    if isinstance(gmt_cfg, list):
        gmt_paths = [resolve_cfg_path(str(p)) for p in gmt_cfg if str(p).strip()]
    else:
        gmt_paths = [resolve_cfg_path(str(gmt_cfg))] if str(gmt_cfg).strip() else []

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
    if driver_genes_path.is_file():
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

    if not gene_burden_path.exists():
        print(f"Missing gene_burden_matrix: {gene_burden_path}", file=sys.stderr)
        return 2
    if not gmt_paths:
        print("Missing gene_sets_gmt in config (provide one or more .gmt files)", file=sys.stderr)
        return 2

    run_pathway_enrichment(
        gene_burden_path=gene_burden_path,
        gmt_paths=gmt_paths,
        out_pathways=out_pathways,
        min_query_genes=int(cfg.get("pathway_min_query_genes", 5)),
        min_term_size=int(cfg.get("pathway_min_term_size", 10)),
        max_term_size=int(cfg.get("pathway_max_term_size", 2000)),
        min_overlap=int(cfg.get("pathway_min_overlap", 3)),
        top_terms_per_sample=int(cfg.get("pathway_top_terms_per_sample", 50)),
        include_cohort_union=bool(cfg.get("pathway_include_cohort_union", True)),
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
