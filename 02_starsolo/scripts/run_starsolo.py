#!/usr/bin/env python3
import argparse
import csv
import json
import os
import gzip
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


def open_fastq(path: Path, mode: str):
    if path.suffix == ".gz":
        return gzip.open(path, mode, encoding="utf-8")
    return path.open(mode, encoding="utf-8")


def merge_cb_umi(r2_path: Path, r3_path: Path, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open_fastq(r2_path, "rt") as r2, open_fastq(r3_path, "rt") as r3, gzip.open(out_path, "wt", encoding="utf-8") as out:
        while True:
            h2 = r2.readline()
            h3 = r3.readline()
            if not h2 and not h3:
                break
            if not h2 or not h3:
                raise ValueError("R2/R3 FASTQ lengths do not match")
            s2 = r2.readline().strip()
            s3 = r3.readline().strip()
            p2 = r2.readline()
            p3 = r3.readline()
            q2 = r2.readline().strip()
            q3 = r3.readline().strip()
            if not (s2 and s3 and q2 and q3 and p2 and p3):
                raise ValueError("Malformed R2/R3 FASTQ record")
            out.write(h2)
            out.write(s2 + s3 + "\n")
            out.write(p2)
            out.write(q2 + q3 + "\n")


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
    cfg_path = Path(args.config)
    cfg = load_config(cfg_path)
    repo_root = Path(__file__).resolve().parents[2]

    rows = read_metadata(meta_path)
    if not rows:
        print("Metadata is empty", file=sys.stderr)
        return 2

    star_index = cfg.get("star_index")
    gtf = cfg.get("gtf")
    threads = str(cfg.get("threads", 8))
    solo = cfg.get("solo", {})
    read_structure = (cfg.get("read_structure") or "two_read").strip().lower()
    cb_start = str(solo.get("CBstart"))
    cb_len = str(solo.get("CBlen"))
    umi_start = str(solo.get("UMIstart"))
    umi_len = str(solo.get("UMIlen"))
    whitelist = solo.get("whitelist")
    read_files_command = cfg.get("readFilesCommand", "")
    extra_args = cfg.get("extra_args", [])

    if read_structure in ("two_read", "common", "tenx_v2", "tenx_v3", "tenx_v2v3", "tenx_5p", "tenx_5prime", "10x_v2", "10x_v3"):
        read_structure = "two_read"
    elif read_structure in ("three_read", "tenx_v1", "10x_v1"):
        read_structure = "three_read"
    else:
        print(f"Unsupported read_structure: {read_structure}", file=sys.stderr)
        return 2
    if not (star_index and gtf and cb_start and cb_len and umi_start and umi_len and whitelist):
        print("Missing required STARsolo config fields", file=sys.stderr)
        return 2

    def resolve_cfg_path(p):
        p = Path(p)
        return p if p.is_absolute() else (repo_root / p)

    star_index = str(resolve_cfg_path(star_index))
    gtf = str(resolve_cfg_path(gtf))
    whitelist = str(resolve_cfg_path(whitelist))

    for row in rows:
        sample_id = (row.get("sample_id") or "").strip()
        if not sample_id:
            continue
        r1 = find_fastq(fastq_dir, sample_id, "R1")
        r2 = find_fastq(fastq_dir, sample_id, "R2")
        r3 = find_fastq(fastq_dir, sample_id, "R3")
        if read_structure == "three_read":
            if not (r1 and r2 and r3):
                print(f"Missing R1/R2/R3 FASTQ for {sample_id}", file=sys.stderr)
                return 2
            merged_cb_umi = Path(args.outdir) / sample_id / "cb_umi_R2R3.fastq.gz"
            merge_cb_umi(r2, r3, merged_cb_umi)
            cdna_read = r1
            barcode_read = merged_cb_umi
        else:
            if not (r1 and r2):
                print(f"Missing R1/R2 FASTQ for {sample_id}", file=sys.stderr)
                return 2
            cdna_read = r2
            barcode_read = r1

        out_prefix = Path(args.outdir) / sample_id / ""
        tmp_base = Path(os.environ.get("STAR_TMP_DIR", "/tmp"))
        tmp_dir = tmp_base / f"STARtmp_{sample_id}_{os.getpid()}"

        cmd = [
            "STAR",
            "--genomeDir", star_index,
            "--readFilesIn", str(cdna_read), str(barcode_read),
            "--runThreadN", threads,
            "--sjdbGTFfile", gtf,
            "--soloType", "CB_UMI_Simple",
            "--soloCBstart", cb_start,
            "--soloCBlen", cb_len,
            "--soloUMIstart", umi_start,
            "--soloUMIlen", umi_len,
            "--soloCBwhitelist", whitelist,
            "--outFileNamePrefix", str(out_prefix),
            "--outTmpDir", str(tmp_dir),
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

        bam_path = Path(args.outdir) / sample_id / "Aligned.sortedByCoord.out.bam"
        if bam_path.exists():
            idx_rc = subprocess.run(["samtools", "index", str(bam_path)]).returncode
            if idx_rc != 0:
                print(f"samtools index failed for {sample_id} (exit {idx_rc})", file=sys.stderr)
                return idx_rc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
