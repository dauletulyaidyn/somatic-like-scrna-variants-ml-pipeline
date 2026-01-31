#!/usr/bin/env python3
import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path


def load_config(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def run_cmd(cmd, log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        log.write("CMD: " + " ".join(cmd) + "\n")
        log.flush()
        proc = subprocess.Popen(cmd, stdout=log, stderr=log)
        return proc.wait()


def main():
    ap = argparse.ArgumentParser(description="Run bcftools mpileup/call/filter for all BAMs.")
    ap.add_argument("--bam-dir", required=True, help="Directory with BAM/BAI files")
    ap.add_argument("--config", required=True, help="bcftools config JSON")
    ap.add_argument("--outdir", default="outputs/artifacts", help="Output directory")
    args = ap.parse_args()

    cfg = load_config(Path(args.config))
    repo_root = Path(__file__).resolve().parents[2]
    ref_fa = cfg.get("ref_fasta")
    threads = str(cfg.get("threads", 4))
    min_baseq = str(cfg.get("min_baseq", 20))
    min_mapq = str(cfg.get("min_mapq", 30))
    extra_mpileup = cfg.get("extra_mpileup", [])
    extra_call = cfg.get("extra_call", [])
    extra_filter = cfg.get("extra_filter", [])

    if not ref_fa:
        print("Missing ref_fasta in config", file=sys.stderr)
        return 2
    ref_fa = str(Path(ref_fa) if Path(ref_fa).is_absolute() else (repo_root / ref_fa))

    bam_dir = Path(args.bam_dir)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    bams = sorted(bam_dir.glob("**/*.bam"))
    if not bams:
        print("No BAM files found", file=sys.stderr)
        return 2

    for bam in bams:
        sample_id = bam.stem
        out_vcf = outdir / f"{sample_id}.filtered.vcf.gz"
        log_path = Path("outputs/metrics") / f"{sample_id}.bcftools.log"

        mpileup_cmd = [
            "bcftools", "mpileup",
            "-f", ref_fa,
            "-q", min_mapq,
            "-Q", min_baseq,
            "-Ou",
            "-a", "AD,DP",
            "--threads", threads,
            str(bam),
        ] + extra_mpileup
        call_cmd = ["bcftools", "call"] + extra_call + ["-Ov"]
        filter_cmd = ["bcftools", "filter"] + extra_filter + ["-Oz", "-o", str(out_vcf)]

        # Run via shell to support pipes
        cmd_str = (
            " ".join(shlex.quote(c) for c in mpileup_cmd)
            + " | "
            + " ".join(shlex.quote(c) for c in call_cmd)
            + " | "
            + " ".join(shlex.quote(c) for c in filter_cmd)
        )
        rc = run_cmd(["bash", "-lc", cmd_str], log_path)
        if rc != 0:
            print(f"bcftools failed for {sample_id} (exit {rc})", file=sys.stderr)
            return rc
        if __import__("subprocess").call(["tabix", "-p", "vcf", str(out_vcf)]) != 0:
            print(f"tabix failed for {sample_id}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
