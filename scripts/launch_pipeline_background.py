#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER = REPO_ROOT / "scripts" / "run_agentic_pipeline.py"
WATCHDOG = REPO_ROOT / "scripts" / "pipeline_watchdog.py"
STATUS_SCRIPT = REPO_ROOT / "scripts" / "status.py"
STATUS_CONFIG = REPO_ROOT / "config" / "status_config.json"
STATUS_DIR = REPO_ROOT / "status"
STATE_PATH = STATUS_DIR / "pipeline_supervisor.json"
PID_PATH = STATUS_DIR / "pipeline_runner.pid"
STDOUT_LOG = STATUS_DIR / "pipeline_runner.out.log"
STDERR_LOG = STATUS_DIR / "pipeline_runner.err.log"
WATCHDOG_STATE_PATH = STATUS_DIR / "pipeline_watchdog.json"
WATCHDOG_PID_PATH = STATUS_DIR / "pipeline_watchdog.pid"
WATCHDOG_STDOUT_LOG = STATUS_DIR / "pipeline_watchdog.out.log"
WATCHDOG_STDERR_LOG = STATUS_DIR / "pipeline_watchdog.err.log"


def pid_is_running(pid: int | None) -> bool:
    if not pid:
        return False
    if os.name == "nt":
        proc = subprocess.run(
            ["tasklist", "/FI", f"PID eq {int(pid)}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(int(pid)) in proc.stdout
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    return True


def read_existing_pid(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def read_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def launch_detached(cmd: list[str], stdout_path: Path, stderr_path: Path) -> subprocess.Popen:
    stdout = stdout_path.open("a", encoding="utf-8")
    stderr = stderr_path.open("a", encoding="utf-8")
    kwargs = {"cwd": REPO_ROOT, "stdout": stdout, "stderr": stderr}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    return subprocess.Popen(cmd, **kwargs)


def main():
    ap = argparse.ArgumentParser(description="Launch the canonical agentic legacy pipeline as a detached background process.")
    ap.add_argument("--from-stage", default="01_input_data")
    ap.add_argument("--end-stage", default="")
    ap.add_argument("--status-port", type=int, default=5556)
    ap.add_argument("--use-wsl", action="store_true")
    ap.add_argument("--reset-status", action="store_true")
    ap.add_argument("--no-watchdog", action="store_true")
    ap.add_argument("--watchdog-interval", type=int, default=10)
    ap.add_argument("--auto-install", action="store_true")
    args = ap.parse_args()

    STATUS_DIR.mkdir(parents=True, exist_ok=True)

    existing_pid = read_existing_pid(PID_PATH)
    runner_active = pid_is_running(existing_pid)
    existing_state = read_state(STATE_PATH)
    effective_use_wsl = args.use_wsl or bool(existing_state.get("use_wsl"))

    subprocess.run([sys.executable, str(STATUS_SCRIPT), "init", "--config", str(STATUS_CONFIG)], cwd=REPO_ROOT, check=False)
    if args.reset_status and not runner_active:
        subprocess.run([sys.executable, str(STATUS_SCRIPT), "reset"], cwd=REPO_ROOT, check=False)

    if runner_active:
        print(f"Background runner already active with PID {existing_pid}")
    else:
        cmd = [
            sys.executable,
            str(RUNNER),
            "--start-status",
            "--status-port",
            str(args.status_port),
            "--from-stage",
            args.from_stage,
        ]
        if args.end_stage:
            cmd.extend(["--end-stage", args.end_stage])
        if effective_use_wsl:
            cmd.append("--use-wsl")
        if args.auto_install:
            cmd.append("--auto-install")

        proc = launch_detached(cmd, STDOUT_LOG, STDERR_LOG)
        PID_PATH.write_text(f"{proc.pid}\n", encoding="utf-8")
        STATE_PATH.write_text(
            json.dumps(
                {
                    "runner_pid": proc.pid,
                    "from_stage": args.from_stage,
                    "end_stage": args.end_stage,
                    "status_port": args.status_port,
                    "use_wsl": effective_use_wsl,
                    "launched_at": time.time(),
                    "stdout_log": str(STDOUT_LOG),
                    "stderr_log": str(STDERR_LOG),
                    "command": cmd,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Background runner started with PID {proc.pid}")

    if not args.no_watchdog:
        watchdog_pid = read_existing_pid(WATCHDOG_PID_PATH)
        if pid_is_running(watchdog_pid):
            print(f"Watchdog already active with PID {watchdog_pid}")
        else:
            watchdog_cmd = [
                sys.executable,
                str(WATCHDOG),
                "--interval-seconds",
                str(args.watchdog_interval),
                "--status-port",
                str(args.status_port),
                "--ensure-status-server",
            ]
            if effective_use_wsl:
                watchdog_cmd.append("--use-wsl")
            watchdog_proc = launch_detached(watchdog_cmd, WATCHDOG_STDOUT_LOG, WATCHDOG_STDERR_LOG)
            WATCHDOG_PID_PATH.write_text(f"{watchdog_proc.pid}\n", encoding="utf-8")
            WATCHDOG_STATE_PATH.write_text(
                json.dumps(
                    {
                        "watchdog_pid": watchdog_proc.pid,
                        "interval_seconds": args.watchdog_interval,
                        "status_port": args.status_port,
                        "use_wsl": effective_use_wsl,
                        "launched_at": time.time(),
                        "stdout_log": str(WATCHDOG_STDOUT_LOG),
                        "stderr_log": str(WATCHDOG_STDERR_LOG),
                        "command": watchdog_cmd,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(f"Watchdog started with PID {watchdog_proc.pid}")

    print(f"Status page: http://127.0.0.1:{args.status_port}")
    print(f"Runner stdout log: {STDOUT_LOG}")
    print(f"Runner stderr log: {STDERR_LOG}")
    if not args.no_watchdog:
        print(f"Watchdog stdout log: {WATCHDOG_STDOUT_LOG}")
        print(f"Watchdog stderr log: {WATCHDOG_STDERR_LOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
