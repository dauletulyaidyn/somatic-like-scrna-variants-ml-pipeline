#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SUPERVISOR_SCRIPT = REPO_ROOT / "03_gatk_call" / "scripts" / "run_gatk_parallel_supervisor.py"
STATUS_DIR = REPO_ROOT / "status"
PID_PATH = STATUS_DIR / "gatk_parallel_supervisor.pid"


def hidden_subprocess_kwargs() -> dict[str, object]:
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    return {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
        "startupinfo": startupinfo,
    }


def pid_is_running(pid: int | None) -> bool:
    if not pid:
        return False
    if os.name == "nt":
        proc = subprocess.run(
            ["tasklist", "/FI", f"PID eq {int(pid)}"],
            capture_output=True,
            text=True,
            check=False,
            **hidden_subprocess_kwargs(),
        )
        return str(int(pid)) in proc.stdout
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    return True


def read_pid(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def windows_path_to_wsl(path: Path) -> str:
    text = str(path)
    if re.match(r"^[A-Za-z]:\\", text):
        drive = text[0].lower()
        rest = text[2:].replace("\\", "/").lstrip("/")
        return f"/mnt/{drive}/{rest}"
    return text.replace("\\", "/")


def newest_config(run_root: Path) -> Path | None:
    config_dir = run_root / "configs"
    candidates = sorted(config_dir.glob("gatk_config*.json"), key=lambda p: p.stat().st_mtime if p.exists() else 0)
    return candidates[-1] if candidates else None


def launch_detached(cmd: list[str], cwd: Path, stdout_path: Path, stderr_path: Path) -> subprocess.Popen:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout = stdout_path.open("a", encoding="utf-8")
    stderr = stderr_path.open("a", encoding="utf-8")
    kwargs: dict[str, object] = {"cwd": cwd, "stdout": stdout, "stderr": stderr, "stdin": subprocess.DEVNULL}
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(cmd, **kwargs)


def main() -> int:
    ap = argparse.ArgumentParser(description="Launch a detached GATK parallel supervisor.")
    ap.add_argument("--run-root", required=True, help="GATK run folder")
    ap.add_argument("--bam-dir", default="", help="Source BAM directory; default: RUN_ROOT/input_bam_remaining_13")
    ap.add_argument("--config", default="", help="GATK config JSON; default: newest RUN_ROOT/configs/gatk_config*.json")
    ap.add_argument("--outdir", default="", help="VCF output directory; default: RUN_ROOT/vcf")
    ap.add_argument("--max-parallel", type=int, default=2)
    ap.add_argument("--poll-seconds", type=int, default=60)
    ap.add_argument("--force-new", action="store_true", help="Start even if saved supervisor PID is alive")
    ap.add_argument("--no-wsl", action="store_true", help="Run directly instead of using WSL on Windows")
    args = ap.parse_args()

    run_root = Path(args.run_root)
    bam_dir = Path(args.bam_dir) if args.bam_dir else run_root / "input_bam_remaining_13"
    config = Path(args.config) if args.config else newest_config(run_root)
    if config is None:
        print(f"Could not find gatk_config*.json under {run_root / 'configs'}", file=sys.stderr)
        return 2
    outdir = Path(args.outdir) if args.outdir else run_root / "vcf"
    log_dir = run_root / "logs"
    state_file = log_dir / "gatk_parallel_supervisor_state.json"
    stdout_path = log_dir / "gatk_parallel_supervisor_stdout.log"
    stderr_path = log_dir / "gatk_parallel_supervisor_stderr.log"

    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    existing_pid = read_pid(PID_PATH)
    if existing_pid and pid_is_running(existing_pid) and not args.force_new:
        print(f"GATK parallel supervisor already appears active with PID {existing_pid}")
        print(f"State: {state_file}")
        return 0

    use_wsl = os.name == "nt" and not args.no_wsl
    if use_wsl:
        cmd = [
            "wsl.exe",
            "-e",
            "python3",
            windows_path_to_wsl(SUPERVISOR_SCRIPT),
            "--run-root",
            windows_path_to_wsl(run_root),
            "--bam-dir",
            windows_path_to_wsl(bam_dir),
            "--config",
            windows_path_to_wsl(config),
            "--outdir",
            windows_path_to_wsl(outdir),
            "--repo-root",
            windows_path_to_wsl(REPO_ROOT),
            "--max-parallel",
            str(args.max_parallel),
            "--poll-seconds",
            str(args.poll_seconds),
            "--state-file",
            windows_path_to_wsl(state_file),
        ]
    else:
        cmd = [
            sys.executable,
            str(SUPERVISOR_SCRIPT),
            "--run-root",
            str(run_root),
            "--bam-dir",
            str(bam_dir),
            "--config",
            str(config),
            "--outdir",
            str(outdir),
            "--repo-root",
            str(REPO_ROOT),
            "--max-parallel",
            str(args.max_parallel),
            "--poll-seconds",
            str(args.poll_seconds),
            "--state-file",
            str(state_file),
        ]

    proc = launch_detached(cmd, REPO_ROOT, stdout_path, stderr_path)
    PID_PATH.write_text(f"{proc.pid}\n", encoding="utf-8")
    print(f"GATK parallel supervisor started with PID {proc.pid}")
    print(f"State: {state_file}")
    print(f"stdout: {stdout_path}")
    print(f"stderr: {stderr_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
