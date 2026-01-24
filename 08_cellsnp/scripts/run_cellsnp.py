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
    ap = argparse.ArgumentParser(description="Run cellsnp-lite for all samples.")
    ap.add_argument("--config", required=True, help="cellsnp config JSON")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    bam_dir = Path(cfg.get("bam_dir", ""))
    vcf = Path(cfg.get("vcf", ""))
    whitelist = Path(cfg.get("barcode_whitelist", ""))
    threads = str(cfg.get("threads", 4))
    outdir = Path(cfg.get("outdir", "outputs/artifacts"))

    if not bam_dir.exists():
        print(f"Missing bam_dir: {bam_dir}", file=sys.stderr)
        return 2
    if not vcf.exists():
        print(f"Missing VCF: {vcf}", file=sys.stderr)
        return 2
    if not whitelist.exists():
        print(f"Missing whitelist: {whitelist}", file=sys.stderr)
        return 2

    bams = sorted(bam_dir.glob("**/*.bam"))
    if not bams:
        print("No BAM files found", file=sys.stderr)
        return 2

    for bam in bams:
        sample_id = bam.stem
        sample_out = outdir / sample_id
        cmd = [
            "cellsnp-lite",
            "-s", str(bam),
            "-b", str(whitelist),
            "-R", str(vcf),
            "-O", str(sample_out),
            "-p", threads,
            "--genotype",
        ]
        log_path = Path("outputs/metrics") / f"{sample_id}.cellsnp.log"
        rc = run_cmd(cmd, log_path)
        if rc != 0:
            print(f"cellsnp-lite failed for {sample_id} (exit {rc})", file=sys.stderr)
            return rc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
