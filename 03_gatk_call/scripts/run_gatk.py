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


def run_cmd(cmd, log_handle):
    log_handle.write("CMD: " + " ".join(cmd) + "\n")
    log_handle.flush()
    proc = subprocess.Popen(cmd, stdout=log_handle, stderr=log_handle)
    return proc.wait()


def ensure_exists(path_str: str, label: str):
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    return path


def bam_has_read_groups(bam: Path) -> bool:
    proc = subprocess.run(
        ["samtools", "view", "-H", str(bam)],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return False
    return any(line.startswith("@RG") for line in proc.stdout.splitlines())


def main():
    ap = argparse.ArgumentParser(description="Run GATK RNA-seq calling for all BAMs.")
    ap.add_argument("--bam-dir", required=True, help="Directory with BAM/BAI files")
    ap.add_argument("--config", required=True, help="GATK config JSON")
    ap.add_argument("--outdir", default="outputs/artifacts", help="Output directory")
    args = ap.parse_args()

    cfg = load_config(Path(args.config))
    ref_fa = ensure_exists(cfg.get("ref_fasta", ""), "ref_fasta")
    bam_dir = Path(args.bam_dir)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    java_opts = cfg.get("java_options", ["-Xmx4g"])
    split_reads = bool(cfg.get("split_ncigar_reads", True))
    tmp_root = Path(cfg.get("tmp_dir", "outputs/tmp"))
    gatk_exe = cfg.get("gatk_executable", "gatk")
    haplotype_args = cfg.get("haplotypecaller_args", [])
    filter_rules = cfg.get(
        "hard_filters",
        [
            {"name": "LowQD", "expr": "QD < 2.0"},
            {"name": "HighFS", "expr": "FS > 30.0"},
            {"name": "LowMQ", "expr": "MQ < 40.0"},
            {"name": "HighSOR", "expr": "SOR > 3.0"},
        ],
    )

    if not bam_dir.exists():
        print(f"Missing bam_dir: {bam_dir}", file=sys.stderr)
        return 2
    if shutil.which(gatk_exe) is None:
        print(f"GATK executable not found in PATH: {gatk_exe}", file=sys.stderr)
        return 2
    if shutil.which("samtools") is None:
        print("samtools executable not found in PATH", file=sys.stderr)
        return 2

    bams = sorted(bam_dir.glob("**/*.bam"))
    if not bams:
        print("No BAM files found", file=sys.stderr)
        return 2

    metrics_dir = Path("outputs/metrics")
    metrics_dir.mkdir(parents=True, exist_ok=True)

    for bam in bams:
        sample_id = bam.parent.name if bam.name == "Aligned.sortedByCoord.out.bam" else bam.stem
        sample_tmp = tmp_root / sample_id
        sample_tmp.mkdir(parents=True, exist_ok=True)

        input_bam = bam
        rg_bam = outdir / f"{sample_id}.rg.bam"
        split_bam = outdir / f"{sample_id}.split.bam"
        raw_vcf = outdir / f"{sample_id}.raw.vcf"
        filt_vcf = outdir / f"{sample_id}.filtered.with_filters.vcf"
        pass_vcf = outdir / f"{sample_id}.filtered.vcf"
        log_path = metrics_dir / f"{sample_id}.gatk.log"

        with log_path.open("w", encoding="utf-8") as log:
            if not bam_has_read_groups(bam):
                rg_cmd = [
                    gatk_exe,
                    "--java-options",
                    " ".join(java_opts),
                    "AddOrReplaceReadGroups",
                    "-I",
                    str(bam),
                    "-O",
                    str(rg_bam),
                    "-RGID",
                    sample_id,
                    "-RGLB",
                    sample_id,
                    "-RGPL",
                    "ILLUMINA",
                    "-RGPU",
                    sample_id,
                    "-RGSM",
                    sample_id,
                ]
                rc = run_cmd(rg_cmd, log)
                if rc != 0:
                    print(f"AddOrReplaceReadGroups failed for {sample_id}", file=sys.stderr)
                    return rc
                index_cmd = ["samtools", "index", str(rg_bam)]
                rc = run_cmd(index_cmd, log)
                if rc != 0:
                    print(f"samtools index failed for {sample_id} RG BAM", file=sys.stderr)
                    return rc
                input_bam = rg_bam

            if split_reads:
                split_cmd = [gatk_exe, "--java-options", " ".join(java_opts), "SplitNCigarReads", "-R", str(ref_fa), "-I", str(input_bam), "-O", str(split_bam)]
                rc = run_cmd(split_cmd, log)
                if rc != 0:
                    print(f"SplitNCigarReads failed for {sample_id}", file=sys.stderr)
                    return rc
                input_bam = split_bam

            hc_cmd = [
                gatk_exe,
                "--java-options",
                " ".join(java_opts),
                "HaplotypeCaller",
                "-R",
                str(ref_fa),
                "-I",
                str(input_bam),
                "-O",
                str(raw_vcf),
            ] + haplotype_args
            rc = run_cmd(hc_cmd, log)
            if rc != 0:
                print(f"HaplotypeCaller failed for {sample_id}", file=sys.stderr)
                return rc

            vf_cmd = [gatk_exe, "--java-options", " ".join(java_opts), "VariantFiltration", "-R", str(ref_fa), "-V", str(raw_vcf), "-O", str(filt_vcf)]
            for rule in filter_rules:
                vf_cmd += ["--filter-name", str(rule["name"]), "--filter-expression", str(rule["expr"])]
            rc = run_cmd(vf_cmd, log)
            if rc != 0:
                print(f"VariantFiltration failed for {sample_id}", file=sys.stderr)
                return rc

            sv_cmd = [gatk_exe, "--java-options", " ".join(java_opts), "SelectVariants", "--exclude-filtered", "true", "-V", str(filt_vcf), "-O", str(pass_vcf)]
            rc = run_cmd(sv_cmd, log)
            if rc != 0:
                print(f"SelectVariants failed for {sample_id}", file=sys.stderr)
                return rc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
