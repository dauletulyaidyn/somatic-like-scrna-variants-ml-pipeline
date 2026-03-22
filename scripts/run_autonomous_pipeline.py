#!/usr/bin/env python3
import argparse
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
STATUS_SCRIPT = REPO_ROOT / "scripts" / "status.py"
STATUS_CONFIG = REPO_ROOT / "config" / "status_config.json"


def run(cmd, cwd=None, check=True):
    proc = subprocess.run(cmd, cwd=cwd or REPO_ROOT)
    if check and proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}")
    return proc.returncode


def wsl_available() -> bool:
    if os.name != "nt":
        return False
    proc = subprocess.run(["wsl.exe", "--status"], capture_output=True)
    return proc.returncode == 0


def to_wsl_path(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    tail = resolved.as_posix().split(":/", 1)[1]
    return f"/mnt/{drive}/{tail}"


def run_wsl(cmd, cwd=None, check=True):
    workdir = to_wsl_path(Path(cwd or REPO_ROOT))
    script = f"cd {shlex.quote(workdir)} && " + " ".join(shlex.quote(str(x)) for x in cmd)
    proc = subprocess.run(["wsl.exe", "-e", "bash", "-lc", script], cwd=cwd or REPO_ROOT)
    if check and proc.returncode != 0:
        raise RuntimeError(f"WSL command failed ({proc.returncode}): {' '.join(map(str, cmd))}")
    return proc.returncode


def port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def start_status_server(port: int):
    if port_open("127.0.0.1", port):
        return
    log_dir = REPO_ROOT / "status"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout = (log_dir / "status_server.out.log").open("a", encoding="utf-8")
    stderr = (log_dir / "status_server.err.log").open("a", encoding="utf-8")
    kwargs = {"cwd": REPO_ROOT, "stdout": stdout, "stderr": stderr}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    subprocess.Popen([sys.executable, "status/app.py", "--port", str(port)], **kwargs)
    time.sleep(1.5)


def ensure_python_packages():
    required = {
        "pandas": "pandas",
        "numpy": "numpy",
        "scipy": "scipy",
        "sklearn": "scikit-learn",
        "flask": "flask",
    }
    missing = []
    for mod, pkg in required.items():
        try:
            __import__(mod)
        except Exception:
            missing.append(pkg)
    if missing:
        run([sys.executable, "-m", "pip", "install", *missing])


def ensure_python_packages_wsl():
    check_script = (
        "python3 - <<'PY'\n"
        "mods=['pandas','numpy','scipy','sklearn','flask']\n"
        "missing=[]\n"
        "for m in mods:\n"
        "    try:\n"
        "        __import__(m)\n"
        "    except Exception:\n"
        "        missing.append(m)\n"
        "print(' '.join(missing))\n"
        "PY"
    )
    proc = subprocess.run(
        ["wsl.exe", "-e", "bash", "-lc", check_script],
        capture_output=True,
        text=True,
    )
    missing = proc.stdout.strip().split()
    if missing:
        pkg_map = {"pandas": "pandas", "numpy": "numpy", "scipy": "scipy", "sklearn": "scikit-learn", "flask": "flask"}
        pkgs = [pkg_map[m] for m in missing]
        run_wsl(["python3", "-m", "pip", "install", "--user", "--break-system-packages", *pkgs])


def try_install_external(tools):
    missing = [tool for tool in tools if shutil.which(tool) is None]
    if not missing:
        return
    conda_like = shutil.which("micromamba") or shutil.which("mamba") or shutil.which("conda")
    mapping = {"gatk": "gatk4", "STAR": "star", "samtools": "samtools", "cellsnp-lite": "cellsnp-lite"}
    packages = [mapping[t] for t in missing if t in mapping]
    if conda_like and packages:
        run([conda_like, "install", "-y", "-c", "bioconda", "-c", "conda-forge", *packages], check=False)


def try_install_external_wsl(tools):
    missing = []
    for tool in tools:
        proc = subprocess.run(
            ["wsl.exe", "-e", "bash", "-lc", f"command -v {shlex.quote(tool)} >/dev/null 2>&1"],
            check=False,
        )
        if proc.returncode != 0:
            missing.append(tool)
    if not missing:
        return

    apt_packages = [
        "rna-star",
        "samtools",
        "openjdk-17-jre-headless",
        "unzip",
        "wget",
        "curl",
        "git",
        "python3-pip",
        "python-is-python3",
        "build-essential",
        "autoconf",
        "automake",
        "pkg-config",
        "libhts-dev",
        "libbz2-dev",
        "liblzma-dev",
        "libcurl4-gnutls-dev",
        "libssl-dev",
    ]
    apt_cmd = "apt-get update -qq && apt-get install -y " + " ".join(apt_packages)
    subprocess.run(["wsl.exe", "-u", "root", "-e", "bash", "-lc", apt_cmd], check=False)

    if "gatk" in missing:
        gatk_cmd = (
            "mkdir -p /opt/gatk && cd /opt/gatk && "
            "if [ ! -x /usr/local/bin/gatk ]; then "
            "wget -q -O gatk.zip https://github.com/broadinstitute/gatk/releases/download/4.6.2.0/gatk-4.6.2.0.zip && "
            "unzip -q -o gatk.zip && "
            "ln -sf /opt/gatk/gatk-4.6.2.0/gatk /usr/local/bin/gatk; "
            "fi"
        )
        subprocess.run(["wsl.exe", "-u", "root", "-e", "bash", "-lc", gatk_cmd], check=False)

    if "cellsnp-lite" in missing:
        cellsnp_cmd = (
            "rm -rf /tmp/cellsnp-lite && "
            "git clone --depth 1 https://github.com/single-cell-genetics/cellsnp-lite.git /tmp/cellsnp-lite >/dev/null 2>&1 && "
            "cd /tmp/cellsnp-lite && "
            "./configure >/tmp/cellsnp_configure.log 2>&1 && "
            "make -j4 >/tmp/cellsnp_make.log 2>&1 && "
            "cp -f cellsnp-lite /usr/local/bin/cellsnp-lite"
        )
        subprocess.run(["wsl.exe", "-u", "root", "-e", "bash", "-lc", cellsnp_cmd], check=False)


def ensure_whitelist():
    cfg_path = REPO_ROOT / "config" / "starsolo_config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    whitelist_path = REPO_ROOT / "config" / "ref" / "whitelist.txt"
    if whitelist_path.exists():
        return
    bundles = REPO_ROOT / "config" / "ref" / "whitelists" / "10x"
    read_structure = str(cfg.get("read_structure", "two_read")).lower()
    candidate = bundles / ("737K-april-2014_rc.txt" if read_structure == "three_read" else "3M-february-2018_TRU.txt.gz")
    if not candidate.exists():
        raise FileNotFoundError(f"Could not infer whitelist from bundled files: {candidate}")
    whitelist_path.parent.mkdir(parents=True, exist_ok=True)
    if candidate.suffix == ".gz":
        import gzip
        with gzip.open(candidate, "rt", encoding="utf-8") as src, whitelist_path.open("w", encoding="utf-8") as dst:
            dst.write(src.read())
    else:
        shutil.copyfile(candidate, whitelist_path)


def ensure_reference_defaults():
    cfg_path = REPO_ROOT / "config" / "starsolo_config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    fallback = REPO_ROOT / "config" / "ref" / "STAR_index"
    if not Path(cfg.get("star_index", "")).exists() and fallback.exists():
        cfg["star_index"] = "config/ref/STAR_index"
        cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")


def log_status(cmd, *args):
    run([sys.executable, str(STATUS_SCRIPT), cmd, *args], cwd=REPO_ROOT, check=False)


def stage_definitions(python_cmd=None):
    py = python_cmd or sys.executable
    return [
        ("01_input_data", [py, "01_input_data/scripts/validate_inputs.py", "--fastq-dir", "data/fastq", "--metadata", "data/metadata/metadata.tsv", "--out", "data/metadata/metadata.cleaned.tsv"], ["data/metadata"]),
        ("02_starsolo", [py, "02_starsolo/scripts/run_starsolo.py", "--metadata", "data/metadata/metadata.cleaned.tsv", "--fastq-dir", "data/fastq", "--config", "config/starsolo_config.json", "--outdir", "02_starsolo/outputs/artifacts"], ["02_starsolo/outputs"]),
        ("03_gatk_call", [py, "03_gatk_call/scripts/run_gatk.py", "--bam-dir", "02_starsolo/outputs/artifacts", "--config", "config/gatk_config.json", "--outdir", "03_gatk_call/outputs/artifacts"], ["03_gatk_call/outputs"]),
        ("04_cohort_filter", [py, "04_cohort_filter/scripts/run_cohort_filter.py", "--vcf-dir", "03_gatk_call/outputs/artifacts", "--config", "config/cohort_filter_config.json", "--outdir", "04_cohort_filter/outputs/artifacts"], ["04_cohort_filter/outputs"]),
        ("05_variant_to_gene", [py, "05_variant_to_gene/scripts/run_variant_to_gene.py", "--config", "config/variant_to_gene_config.json"], ["05_variant_to_gene/outputs"]),
        ("06_gene_burden", [py, "06_gene_burden/scripts/run_gene_burden.py", "--config", "config/gene_burden_config.json"], ["06_gene_burden/outputs"]),
        ("07_ml_control_vs_disease", [py, "07_ml_control_vs_disease/scripts/run_ml.py", "--config", "config/ml_config.json"], ["07_ml_control_vs_disease/outputs"]),
        ("08_cellsnp", [py, "08_cellsnp/scripts/run_cellsnp.py", "--config", "config/cellsnp_config.json"], ["08_cellsnp/outputs"]),
        ("09_cluster_aggregation", [py, "09_cluster_aggregation/scripts/run_cluster_aggregation.py", "--config", "config/cluster_aggregation_config.json"], ["09_cluster_aggregation/outputs"]),
        ("10_mutational_analysis", [py, "10_mutational_analysis/scripts/run_mutational_analysis.py", "--config", "config/mutational_analysis_config.json"], ["10_mutational_analysis/outputs"]),
        ("11_correlation", [py, "11_correlation/scripts/run_correlation.py", "--config", "config/correlation_config.json"], ["11_correlation/outputs"]),
        ("12_integrated_interpretation", [py, "12_integrated_interpretation/scripts/collect_for_report.py", "--repo-root", ".", "--out", "for_report"], ["12_integrated_interpretation/outputs", "for_report"]),
    ]


def write_agent_brief():
    brief = REPO_ROOT / "docs" / "AUTONOMOUS_AGENT_QUICKSTART.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text(
        "\n".join(
            [
                "# Autonomous Agent Quickstart",
                "",
                "Start the full pipeline with one command:",
                "",
                "- `python scripts/run_autonomous_pipeline.py --auto-install --start-status`",
                "- `./zapusti_analiz.ps1`",
                "",
                "Suggested agent prompt:",
                "- `zapusti analiz`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main():
    ap = argparse.ArgumentParser(description="Autonomous end-to-end pipeline runner.")
    ap.add_argument("--auto-install", action="store_true", help="Attempt to install missing dependencies")
    ap.add_argument("--start-status", action="store_true", help="Start the Flask status server")
    ap.add_argument("--status-port", type=int, default=5556)
    ap.add_argument("--from-stage", default="01_input_data")
    ap.add_argument("--end-stage", default="")
    ap.add_argument("--use-wsl", action="store_true", help="Run pipeline stages inside WSL while keeping status UI local")
    args = ap.parse_args()

    write_agent_brief()
    run([sys.executable, str(STATUS_SCRIPT), "init", "--config", str(STATUS_CONFIG)], cwd=REPO_ROOT, check=False)
    run([sys.executable, str(STATUS_SCRIPT), "reset"], cwd=REPO_ROOT, check=False)

    if args.start_status:
        start_status_server(args.status_port)

    ensure_reference_defaults()
    ensure_whitelist()
    if args.auto_install:
        if args.use_wsl:
            ensure_python_packages_wsl()
            try_install_external_wsl(["STAR", "samtools", "gatk", "cellsnp-lite"])
        else:
            ensure_python_packages()
            try_install_external(["STAR", "samtools", "gatk", "cellsnp-lite"])

    stage_ids = [stage_id for stage_id, _, _ in stage_definitions()]
    if args.from_stage not in stage_ids:
        raise ValueError(f"Unknown from-stage: {args.from_stage}")
    if args.end_stage and args.end_stage not in stage_ids:
        raise ValueError(f"Unknown end-stage: {args.end_stage}")

    stage_runner = run_wsl if args.use_wsl else run
    python_cmd = "python3" if args.use_wsl else sys.executable

    started = False
    for stage_id, command, scan_paths in stage_definitions(python_cmd=python_cmd):
        if stage_id == args.from_stage:
            started = True
        if not started:
            continue
        log_status("start", "--stage", stage_id, "--message", "start")
        try:
            stage_runner(command, cwd=REPO_ROOT)
            if scan_paths:
                log_status("scan", "--stage", stage_id, "--paths", *scan_paths)
            log_status("finish", "--stage", stage_id, "--message", "success")
        except Exception as exc:
            log_status("error", "--stage", stage_id, "--message", str(exc))
            raise
        if args.end_stage and stage_id == args.end_stage:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
