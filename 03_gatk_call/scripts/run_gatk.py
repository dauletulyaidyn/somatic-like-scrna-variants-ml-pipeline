#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def load_config(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_path(repo_root: Path, value: str | None, default: str | None = None) -> Path:
    raw = value or default
    if not raw:
        raise ValueError("Missing required path value")
    path = Path(raw)
    return path if path.is_absolute() else (repo_root / path)


def sample_id_from_bam(path: Path) -> str:
    sample_id = path.stem
    if sample_id.endswith("Aligned.sortedByCoord.out"):
        sample_id = sample_id.replace("Aligned.sortedByCoord.out", "")
    return sample_id


def copy_if_exists(src: Path | None, dst: Path) -> bool:
    if not src or not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def run_cmd(cmd: list[str], log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        log.write("CMD: " + " ".join(cmd) + "\n")
        log.flush()
        proc = subprocess.run(cmd, stdout=log, stderr=log, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed with exit {proc.returncode}: {' '.join(cmd)}")


def import_existing(cfg: dict, repo_root: Path, bam_dir: Path, outdir: Path) -> list[dict]:
    stage_dir = Path(__file__).resolve().parents[1]
    metrics_dir = stage_dir / "outputs" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)

    filtered_dir = resolve_path(repo_root, cfg.get("external_filtered_vcf_dir"))
    raw_dir = resolve_path(repo_root, cfg.get("external_raw_vcf_dir"), "outputs/artifacts/raw")
    logs_dir = resolve_path(repo_root, cfg.get("external_logs_dir"))

    rows: list[dict] = []
    bams = sorted(bam_dir.glob("*.bam"))
    sample_ids = [sample_id_from_bam(bam) for bam in bams]
    if not sample_ids:
        sample_ids = sorted(
            {
                path.name.replace(".filtered.pass.vcf.gz", "").replace(".filtered.annotated.vcf.gz", "")
                for path in filtered_dir.glob("*.vcf.gz")
            }
        )
    if not sample_ids:
        raise RuntimeError("No importable samples found in BAM or external filtered VCF directories")

    for sample_id in sample_ids:
        src_vcf = filtered_dir / f"{sample_id}.filtered.pass.vcf.gz"
        if not src_vcf.exists():
            fallback = filtered_dir / f"{sample_id}.filtered.annotated.vcf.gz"
            src_vcf = fallback if fallback.exists() else src_vcf
        if not src_vcf.exists():
            raise RuntimeError(f"Missing external filtered VCF for {sample_id}: {src_vcf}")

        dst_vcf = outdir / f"{sample_id}.filtered.vcf.gz"
        dst_tbi = Path(str(dst_vcf) + ".tbi")
        copy_if_exists(src_vcf, dst_vcf)
        copy_if_exists(Path(str(src_vcf) + ".tbi"), dst_tbi)

        copy_if_exists(raw_dir / f"{sample_id}.raw.vcf.gz", outdir / f"{sample_id}.raw.vcf.gz")
        copy_if_exists(raw_dir / f"{sample_id}.raw.vcf.gz.tbi", outdir / f"{sample_id}.raw.vcf.gz.tbi")
        copy_if_exists(filtered_dir / f"{sample_id}.filtered.annotated.vcf.gz", outdir / f"{sample_id}.filtered.annotated.vcf.gz")
        copy_if_exists(
            filtered_dir / f"{sample_id}.filtered.annotated.vcf.gz.tbi",
            outdir / f"{sample_id}.filtered.annotated.vcf.gz.tbi",
        )

        imported_log = metrics_dir / f"{sample_id}.gatk.log"
        log_copied = copy_if_exists(logs_dir / f"{sample_id}.log", imported_log)
        summary_log = metrics_dir / f"{sample_id}.import.log"
        with summary_log.open("w", encoding="utf-8") as f:
            f.write(f"mode\timport_existing\n")
            f.write(f"sample_id\t{sample_id}\n")
            f.write(f"source_vcf\t{src_vcf}\n")
            f.write(f"source_log\t{logs_dir / f'{sample_id}.log'}\n")
            f.write(f"log_copied\t{int(log_copied)}\n")

        rows.append(
            {
                "sample_id": sample_id,
                "mode": "import_existing",
                "vcf_path": str(dst_vcf),
                "vcf_exists": int(dst_vcf.exists()),
                "tbi_exists": int(dst_tbi.exists()),
                "vcf_size_bytes": dst_vcf.stat().st_size if dst_vcf.exists() else 0,
                "source_vcf": str(src_vcf),
            }
        )
    return rows


def build_gatk_base_cmd(cfg: dict) -> list[str]:
    gatk_cmd = str(cfg.get("gatk_cmd", "gatk"))
    java_options = cfg.get("java_options", [])
    cmd = [gatk_cmd]
    if java_options:
        cmd.extend(["--java-options", " ".join(str(x) for x in java_options)])
    return cmd


def run_fresh(cfg: dict, repo_root: Path, bam_dir: Path, outdir: Path) -> list[dict]:
    ref_fa = resolve_path(repo_root, cfg.get("ref_fasta"))
    work_root = resolve_path(repo_root, cfg.get("work_dir"), "03_gatk_call/outputs/work")
    work_root.mkdir(parents=True, exist_ok=True)
    stage_dir = Path(__file__).resolve().parents[1]
    metrics_dir = stage_dir / "outputs" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    filters = cfg.get("variant_filters", [])
    pass_only = bool(cfg.get("emit_pass_only", True))

    bams = sorted(bam_dir.glob("*.bam"))
    if not bams:
        raise RuntimeError("No BAM files found")

    rows: list[dict] = []
    gatk_base = build_gatk_base_cmd(cfg)
    for bam in bams:
        sample_id = sample_id_from_bam(bam)
        sample_work = work_root / sample_id
        sample_work.mkdir(parents=True, exist_ok=True)
        log_path = metrics_dir / f"{sample_id}.gatk.log"

        rg_bam = sample_work / f"{sample_id}.rg.bam"
        dedup_bam = sample_work / f"{sample_id}.dedup.bam"
        split_bam = sample_work / f"{sample_id}.split.bam"
        raw_vcf = outdir / f"{sample_id}.raw.vcf.gz"
        annotated_vcf = outdir / f"{sample_id}.filtered.annotated.vcf.gz"
        out_vcf = outdir / f"{sample_id}.filtered.vcf.gz"

        run_cmd(
            gatk_base
            + [
                "AddOrReplaceReadGroups",
                "--INPUT", str(bam),
                "--OUTPUT", str(rg_bam),
                "--SORT_ORDER", "coordinate",
                "--RGID", sample_id,
                "--RGLB", sample_id,
                "--RGPL", "ILLUMINA",
                "--RGPU", sample_id,
                "--RGSM", sample_id,
                "--CREATE_INDEX", "true",
            ],
            log_path,
        )
        run_cmd(
            gatk_base
            + [
                "MarkDuplicates",
                "--INPUT", str(rg_bam),
                "--OUTPUT", str(dedup_bam),
                "--METRICS_FILE", str(sample_work / f"{sample_id}.dup_metrics.txt"),
                "--CREATE_INDEX", "true",
            ],
            log_path,
        )
        run_cmd(
            gatk_base
            + [
                "SplitNCigarReads",
                "--reference", str(ref_fa),
                "--input", str(dedup_bam),
                "--output", str(split_bam),
                "--create-output-bam-index", "true",
            ]
            + [str(x) for x in cfg.get("split_ncigar_extra", [])],
            log_path,
        )
        run_cmd(
            gatk_base
            + [
                "HaplotypeCaller",
                "--reference", str(ref_fa),
                "--input", str(split_bam),
                "--output", str(raw_vcf),
            ]
            + [str(x) for x in cfg.get("haplotypecaller_extra", [])],
            log_path,
        )

        vf_cmd = gatk_base + [
            "VariantFiltration",
            "--reference", str(ref_fa),
            "--variant", str(raw_vcf),
            "--output", str(annotated_vcf),
        ]
        for filt in filters:
            vf_cmd.extend(["--filter-name", str(filt["name"]), "--filter-expression", str(filt["expression"])])
        vf_cmd.extend([str(x) for x in cfg.get("variant_filtration_extra", [])])
        run_cmd(vf_cmd, log_path)

        if pass_only:
            run_cmd(
                gatk_base
                + [
                    "SelectVariants",
                    "--reference", str(ref_fa),
                    "--variant", str(annotated_vcf),
                    "--output", str(out_vcf),
                    "--exclude-filtered", "true",
                ],
                log_path,
            )
        else:
            copy_if_exists(annotated_vcf, out_vcf)

        rows.append(
            {
                "sample_id": sample_id,
                "mode": "run_fresh",
                "vcf_path": str(out_vcf),
                "vcf_exists": int(out_vcf.exists()),
                "tbi_exists": int(Path(str(out_vcf) + ".tbi").exists()),
                "vcf_size_bytes": out_vcf.stat().st_size if out_vcf.exists() else 0,
                "source_vcf": str(raw_vcf),
            }
        )
    return rows


def main():
    ap = argparse.ArgumentParser(description="Import or run the active GATK RNA variant-calling stage.")
    ap.add_argument("--bam-dir", required=True, help="Directory with BAM/BAI files")
    ap.add_argument("--config", required=True, help="GATK config JSON")
    ap.add_argument("--outdir", default="outputs/artifacts", help="Output directory")
    args = ap.parse_args()

    cfg = load_config(Path(args.config))
    repo_root = Path(__file__).resolve().parents[2]
    bam_dir = Path(args.bam_dir)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    mode = str(cfg.get("mode", "import_existing")).strip().lower()
    if mode == "import_existing":
        rows = import_existing(cfg, repo_root, bam_dir, outdir)
    elif mode == "run_fresh":
        rows = run_fresh(cfg, repo_root, bam_dir, outdir)
    else:
        print(f"Unsupported mode: {mode}", file=sys.stderr)
        return 2

    if rows:
        import pandas as pd

        stage_dir = Path(__file__).resolve().parents[1]
        metrics_dir = stage_dir / "outputs" / "metrics"
        metrics_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(metrics_dir / "gatk_outputs.tsv", sep="\t", index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
