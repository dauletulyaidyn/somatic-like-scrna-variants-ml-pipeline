#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def natural_key(value: str) -> tuple[str, list[int], str]:
    return (re.sub(r"\d+", "", value), [int(x) for x in re.findall(r"\d+", value)] or [0], value)


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def discover_bams(bam_dir: Path) -> dict[str, Path]:
    bams = {}
    for bam in sorted(bam_dir.rglob("*.bam"), key=lambda path: natural_key(path.stem)):
        bams[bam.stem] = bam
    return bams


def find_bai(bam: Path) -> Path | None:
    candidates = [bam.with_suffix(bam.suffix + ".bai"), bam.with_suffix(".bai")]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def link_or_symlink(src: Path, dst: Path) -> None:
    if dst.exists() or dst.is_symlink():
        return
    try:
        os.link(src, dst)
        return
    except OSError:
        pass
    try:
        os.symlink(src, dst)
        return
    except OSError as exc:
        raise RuntimeError(f"Could not hardlink or symlink {src} -> {dst}: {exc}") from exc


def prepare_single_sample_bam_dir(run_root: Path, sample: str, source_bam: Path) -> Path:
    sample_dir = run_root / f"input_bam_parallel_{sample}"
    sample_dir.mkdir(parents=True, exist_ok=True)
    link_or_symlink(source_bam, sample_dir / source_bam.name)

    source_bai = find_bai(source_bam)
    if source_bai:
        link_or_symlink(source_bai, sample_dir / f"{source_bam.name}.bai")
    return sample_dir


def ps_rows() -> list[dict[str, str]]:
    proc = subprocess.run(["ps", "-eo", "pid=,ppid=,etime=,cmd="], capture_output=True, text=True, check=False)
    rows = []
    for line in proc.stdout.splitlines():
        parts = line.strip().split(None, 3)
        if len(parts) == 4:
            rows.append({"pid": parts[0], "ppid": parts[1], "etime": parts[2], "cmd": parts[3]})
    return rows


def active_samples(run_root: Path, samples: set[str]) -> dict[str, dict[str, str]]:
    root_marker = str(run_root)
    active = {}
    for row in ps_rows():
        cmd = row["cmd"]
        if root_marker not in cmd:
            continue
        if not any(token in cmd for token in ("run_gatk.py", "gatk", "samtools")):
            continue
        for sample in samples:
            if sample not in cmd:
                continue
            active[sample] = {
                "sample": sample,
                "pid": row["pid"],
                "etime": row["etime"],
                "cmd": cmd,
            }
    return active


def output_paths(outdir: Path, metrics_dir: Path, sample: str) -> dict[str, Path]:
    return {
        "rg_bam": outdir / f"{sample}.rg.bam",
        "split_bam": outdir / f"{sample}.split.bam",
        "raw_vcf": outdir / f"{sample}.raw.vcf",
        "filtered_with_filters_vcf": outdir / f"{sample}.filtered.with_filters.vcf",
        "filtered_vcf": outdir / f"{sample}.filtered.vcf",
        "log": metrics_dir / f"{sample}.gatk.log",
    }


def nonempty(path: Path) -> bool:
    return path.exists() and path.is_file() and path.stat().st_size > 0


def classify_sample(outdir: Path, metrics_dir: Path, sample: str, active: dict[str, dict[str, str]]) -> str:
    paths = output_paths(outdir, metrics_dir, sample)
    if nonempty(paths["filtered_vcf"]):
        return "finished"
    if sample in active:
        return "running"
    if any(path.exists() for path in paths.values()):
        return "stopped_or_failed"
    return "pending"


def launch_sample(
    run_root: Path,
    repo_root: Path,
    sample: str,
    sample_bam_dir: Path,
    config: Path,
    outdir: Path,
    log_dir: Path,
) -> int:
    script = repo_root / "03_gatk_call" / "scripts" / "run_gatk.py"
    stdout_path = log_dir / f"parallel_{sample}_stdout.log"
    stderr_path = log_dir / f"parallel_{sample}_stderr.log"
    pid_path = log_dir / f"parallel_{sample}_linux_pid.txt"
    cmd = [
        sys.executable,
        str(script),
        "--bam-dir",
        str(sample_bam_dir),
        "--config",
        str(config),
        "--outdir",
        str(outdir),
    ]
    stdout = stdout_path.open("a", encoding="utf-8")
    stderr = stderr_path.open("a", encoding="utf-8")
    kwargs: dict[str, object] = {
        "cwd": run_root,
        "stdin": subprocess.DEVNULL,
        "stdout": stdout,
        "stderr": stderr,
        "start_new_session": True,
    }
    proc = subprocess.Popen(cmd, **kwargs)
    pid_path.write_text(f"{proc.pid}\n", encoding="utf-8")
    return proc.pid


def supervisor_tick(args: argparse.Namespace, launched_total: list[dict[str, object]]) -> tuple[bool, dict[str, object]]:
    run_root = Path(args.run_root)
    bam_dir = Path(args.bam_dir)
    config = Path(args.config)
    outdir = Path(args.outdir)
    repo_root = Path(args.repo_root)
    metrics_dir = run_root / "outputs" / "metrics"
    log_dir = run_root / "logs"

    bams = discover_bams(bam_dir)
    samples = list(sorted(bams.keys(), key=natural_key))
    active = active_samples(run_root, set(samples))
    statuses = {sample: classify_sample(outdir, metrics_dir, sample, active) for sample in samples}

    running = [sample for sample in samples if statuses[sample] == "running"]
    pending = [sample for sample in samples if statuses[sample] == "pending"]
    stopped = [sample for sample in samples if statuses[sample] == "stopped_or_failed"]
    finished = [sample for sample in samples if statuses[sample] == "finished"]

    launched_now: list[dict[str, object]] = []
    slots = max(0, int(args.max_parallel) - len(running))
    for sample in pending[:slots]:
        if args.dry_run:
            launched_now.append({"sample": sample, "pid": None, "dry_run": True})
            continue
        sample_bam_dir = prepare_single_sample_bam_dir(run_root, sample, bams[sample])
        pid = launch_sample(run_root, repo_root, sample, sample_bam_dir, config, outdir, log_dir)
        launched = {
            "sample": sample,
            "pid": pid,
            "bam_dir": str(sample_bam_dir),
            "launched_at": now_text(),
        }
        launched_now.append(launched)
        launched_total.append(launched)

    state = {
        "updated_at": now_text(),
        "supervisor_pid": os.getpid(),
        "run_root": str(run_root),
        "bam_dir": str(bam_dir),
        "config": str(config),
        "outdir": str(outdir),
        "max_parallel": int(args.max_parallel),
        "poll_seconds": int(args.poll_seconds),
        "counts": {
            "finished": len(finished),
            "running": len(running),
            "pending": len(pending),
            "stopped_or_failed": len(stopped),
        },
        "running": [active[sample] for sample in running if sample in active],
        "pending": pending,
        "stopped_or_failed": stopped,
        "launched_this_tick": launched_now,
        "launched_total": launched_total[-100:],
    }
    write_json(Path(args.state_file), state)

    if not running and not pending:
        return False, state
    return True, state


def main() -> int:
    repo_root_default = Path(__file__).resolve().parents[2]
    ap = argparse.ArgumentParser(description="Keep a GATK run at N parallel single-sample workers.")
    ap.add_argument("--run-root", required=True, help="GATK run folder")
    ap.add_argument("--bam-dir", required=True, help="Source BAM directory containing all samples to supervise")
    ap.add_argument("--config", required=True, help="GATK config JSON")
    ap.add_argument("--outdir", required=True, help="GATK output VCF directory")
    ap.add_argument("--repo-root", default=str(repo_root_default), help="Repository root containing 03_gatk_call/scripts/run_gatk.py")
    ap.add_argument("--max-parallel", type=int, default=2, help="Maximum active samples to keep running")
    ap.add_argument("--poll-seconds", type=int, default=60, help="Seconds between supervisor checks")
    ap.add_argument("--state-file", default="", help="Supervisor state JSON path")
    ap.add_argument("--dry-run", action="store_true", help="Report what would launch without starting GATK")
    ap.add_argument("--once", action="store_true", help="Run one supervisor check and exit")
    args = ap.parse_args()

    run_root = Path(args.run_root)
    if not args.state_file:
        args.state_file = str(run_root / "logs" / "gatk_parallel_supervisor_state.json")
    if args.max_parallel < 1:
        raise SystemExit("--max-parallel must be >= 1")
    if not Path(args.bam_dir).exists():
        raise SystemExit(f"Missing --bam-dir: {args.bam_dir}")
    if not Path(args.config).exists():
        raise SystemExit(f"Missing --config: {args.config}")

    launched_total: list[dict[str, object]] = []
    while True:
        keep_running, state = supervisor_tick(args, launched_total)
        print(
            f"[{state['updated_at']}] running={state['counts']['running']} "
            f"pending={state['counts']['pending']} finished={state['counts']['finished']} "
            f"launched={len(state['launched_this_tick'])}",
            flush=True,
        )
        if args.once:
            return 0
        if not keep_running:
            return 1 if state["counts"]["stopped_or_failed"] else 0
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
