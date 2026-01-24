#!/usr/bin/env python3
import argparse
import shutil
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description="Collect outputs into for_report.")
    ap.add_argument("--repo-root", default="..", help="Repo root path")
    ap.add_argument("--out", default="for_report", help="Output report dir")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    outdir = (repo / args.out).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    manifest = []
    stages = [p for p in repo.iterdir() if p.is_dir() and p.name[:2].isdigit()]
    stages.sort()

    for stage in stages:
        stage_name = stage.name
        outputs = stage / "outputs"
        if not outputs.exists():
            continue
        files = list(outputs.rglob("*"))
        files = [f for f in files if f.is_file()]
        if not files:
            continue
        idx = 1
        for f in files:
            ext = "".join(f.suffixes)
            base = f"{stage_name}_{idx}"
            target = outdir / f"{base}_{f.stem}{ext}"
            shutil.copy2(f, target)
            manifest.append({
                "stage": stage_name,
                "source": str(f.relative_to(repo)),
                "target": str(target.relative_to(repo)),
            })
            idx += 1

    manifest_path = repo / "12_integrated_interpretation" / "outputs" / "metrics" / "for_report_manifest.tsv"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as out:
        out.write("stage\tsource\ttarget\n")
        for m in manifest:
            out.write(f"{m['stage']}\t{m['source']}\t{m['target']}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
