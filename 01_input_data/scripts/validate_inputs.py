#!/usr/bin/env python3
import argparse
import csv
import re
import sys
from pathlib import Path

RE_FASTQ = re.compile(r"(.+?)_(R[123])(_\d+)?\.f(ast)?q(\.gz)?$", re.IGNORECASE)


def find_fastq_samples(fastq_dir: Path):
    samples = {}
    for p in fastq_dir.rglob("*"):
        if not p.is_file():
            continue
        m = RE_FASTQ.match(p.name)
        if not m:
            continue
        sample_id = m.group(1)
        read = m.group(2).upper()
        samples.setdefault(sample_id, set()).add(read)
    return samples


def read_metadata(path: Path):
    delim = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=delim)
        rows = list(reader)
    if not rows:
        raise ValueError("Metadata file is empty")
    return reader.fieldnames, rows


def write_metadata(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def main():
    ap = argparse.ArgumentParser(description="Validate FASTQ + metadata inputs.")
    ap.add_argument("--fastq-dir", required=True, help="Path to FASTQ directory")
    ap.add_argument("--metadata", required=True, help="Path to metadata TSV/CSV")
    ap.add_argument("--out", required=True, help="Output cleaned metadata TSV")
    args = ap.parse_args()

    fastq_dir = Path(args.fastq_dir)
    meta_path = Path(args.metadata)
    out_path = Path(args.out)

    if not fastq_dir.exists():
        print(f"FASTQ dir not found: {fastq_dir}", file=sys.stderr)
        return 2
    if not meta_path.exists():
        print(f"Metadata not found: {meta_path}", file=sys.stderr)
        return 2

    samples = find_fastq_samples(fastq_dir)
    if not samples:
        print("No FASTQ files found.", file=sys.stderr)
        return 2

    fieldnames, rows = read_metadata(meta_path)
    required = {"sample_id", "condition", "run_id"}
    if not required.issubset(set(fieldnames or [])):
        missing = ", ".join(sorted(required - set(fieldnames or [])))
        print(f"Missing required metadata columns: {missing}", file=sys.stderr)
        return 2

    cleaned = []
    missing_fastq = []
    for r in rows:
        sid = (r.get("sample_id") or "").strip()
        if not sid:
            continue
        if sid not in samples:
            missing_fastq.append(sid)
            continue
        cleaned.append(r)

    if missing_fastq:
        print("Samples in metadata without FASTQ:", ", ".join(missing_fastq), file=sys.stderr)
        return 2

    write_metadata(out_path, fieldnames, cleaned)
    print(f"Wrote: {out_path}")
    print(f"Samples: {len(cleaned)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
