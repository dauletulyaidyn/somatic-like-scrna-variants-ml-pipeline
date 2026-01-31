#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd, log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        log.write("CMD: " + " ".join(cmd) + "\n")
        log.flush()
        proc = subprocess.Popen(cmd, stdout=log, stderr=log)
        return proc.wait()


def main():
    ap = argparse.ArgumentParser(description="Run cluster aggregation for all samples.")
    ap.add_argument("--config", required=True, help="cluster aggregation config JSON")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    repo_root = Path(__file__).resolve().parents[2]

    def resolve_cfg_path(p: str) -> Path:
        p = Path(p)
        return p if p.is_absolute() else (repo_root / p)

    cellsnp_dir = resolve_cfg_path(cfg.get("cellsnp_dir", ""))
    cell_cluster_map = resolve_cfg_path(cfg.get("cell_cluster_map", ""))
    outdir = resolve_cfg_path(cfg.get("outdir", "outputs/artifacts"))
    min_alt = str(cfg.get("min_alt", 3))

    if not cellsnp_dir.exists():
        print(f"Missing cellsnp_dir: {cellsnp_dir}", file=sys.stderr)
        return 2
    if not cell_cluster_map.exists():
        print(f"Missing cell_cluster_map: {cell_cluster_map}", file=sys.stderr)
        return 2

    sample_dirs = sorted([p for p in cellsnp_dir.iterdir() if p.is_dir()])
    if not sample_dirs:
        print("No sample dirs found", file=sys.stderr)
        return 2

    for sdir in sample_dirs:
        srr = sdir.name
        out_path = outdir / f"{srr}.cellsnp.cluster_counts.tsv.gz"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "python3",
            str(Path(__file__).resolve().parent / "aggregate_cellsnp_by_cluster.py"),
            "--srr", srr,
            "--cellsnp-outdir", str(sdir),
            "--cell-cluster-map", str(cell_cluster_map),
            "--min-alt", min_alt,
            "--out", str(out_path),
        ]
        log_path = Path("outputs/metrics") / f"{srr}.cluster_agg.log"
        rc = run_cmd(cmd, log_path)
        if rc != 0:
            print(f"Cluster aggregation failed for {srr} (exit {rc})", file=sys.stderr)
            return rc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
