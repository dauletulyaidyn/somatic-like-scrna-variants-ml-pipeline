#!/usr/bin/env python3
import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path


def load_config(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def read_metadata(path: Path):
    delim = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=delim)
        rows = list(reader)
    return rows


def find_fastq(fastq_dir: Path, sample_id: str, read: str):
    for ext in (".fastq.gz", ".fq.gz", ".fastq", ".fq"):
        p = fastq_dir / f"{sample_id}_{read}{ext}"
        if p.exists():
            return p
    return None


def run_cmd(cmd, log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        log.write("CMD: " + " ".join(cmd) + "\n")
        log.flush()
        proc = subprocess.Popen(cmd, stdout=log, stderr=log)
        return proc.wait()


def main():
    ap = argparse.ArgumentParser(description="Run STARsolo for all samples.")
    ap.add_argument("--metadata", required=True, help="metadata.cleaned.tsv")
    ap.add_argument("--fastq-dir", required=True, help="FASTQ directory")
    ap.add_argument("--config", required=True, help="STARsolo config JSON")
    ap.add_argument("--outdir", default="outputs/artifacts", help="Output base dir")
    args = ap.parse_args()

    meta_path = Path(args.metadata)
    fastq_dir = Path(args.fastq_dir)
    cfg = load_config(Path(args.config))

    rows = read_metadata(meta_path)
    if not rows:
        print("Metadata is empty", file=sys.stderr)
        return 2

    star_index = cfg.get("star_index")
    gtf = cfg.get("gtf")
    threads = str(cfg.get("threads", 8))
    solo = cfg.get("solo", {})
    cb_start = str(solo.get("CBstart"))
    cb_len = str(solo.get("CBlen"))
    umi_start = str(solo.get("UMIstart"))
    umi_len = str(solo.get("UMIlen"))
    whitelist = solo.get("whitelist")
    read_files_command = cfg.get("readFilesCommand", "")
    extra_args = cfg.get("extra_args", [])

    if not (star_index and gtf and cb_start and cb_len and umi_start and umi_len and whitelist):
        print("Missing required STARsolo config fields", file=sys.stderr)
        return 2

    for row in rows:
        sample_id = (row.get("sample_id") or "").strip()
        if not sample_id:
            continue
        r3 = find_fastq(fastq_dir, sample_id, "R3")
        r2 = find_fastq(fastq_dir, sample_id, "R2")
        if not r3 or not r2:
            print(f"Missing R3/R2 FASTQ for {sample_id}", file=sys.stderr)
            return 2

        out_prefix = Path(args.outdir) / sample_id / ""
        cmd = [
            "STAR",
            "--genomeDir", star_index,
            "--readFilesIn", str(r3), str(r2),
            "--runThreadN", threads,
            "--sjdbGTFfile", gtf,
            "--soloType", "CB_UMI_Simple",
            "--soloCBstart", cb_start,
            "--soloCBlen", cb_len,
            "--soloUMIstart", umi_start,
            "--soloUMIlen", umi_len,
            "--soloCBwhitelist", whitelist,
            "--outFileNamePrefix", str(out_prefix),
        ]
        if read_files_command:
            cmd += ["--readFilesCommand", read_files_command]
        if extra_args:
            cmd += extra_args

        log_path = Path("outputs/metrics") / f"{sample_id}.starsolo.log"
        rc = run_cmd(cmd, log_path)
        if rc != 0:
            print(f"STARsolo failed for {sample_id} (exit {rc})", file=sys.stderr)
            return rc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
