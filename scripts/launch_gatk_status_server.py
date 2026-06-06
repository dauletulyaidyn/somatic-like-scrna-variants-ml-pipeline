#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATUS_APP = REPO_ROOT / "status" / "app.py"
STATUS_DIR = REPO_ROOT / "status"
PID_PATH = STATUS_DIR / "gatk_status_server.pid"
STDOUT_LOG = STATUS_DIR / "gatk_status_server.out.log"
STDERR_LOG = STATUS_DIR / "gatk_status_server.err.log"


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


def launch_detached(cmd: list[str], stdout_path: Path, stderr_path: Path) -> subprocess.Popen:
    stdout = stdout_path.open("a", encoding="utf-8")
    stderr = stderr_path.open("a", encoding="utf-8")
    kwargs = {"cwd": REPO_ROOT, "stdout": stdout, "stderr": stderr}
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    return subprocess.Popen(cmd, **kwargs)


def main() -> int:
    ap = argparse.ArgumentParser(description="Launch the GATK run status page as a detached Flask server.")
    ap.add_argument("--run-root", required=True, help="GATK run folder to monitor")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5556)
    ap.add_argument("--force-new", action="store_true", help="Start a new server even if the saved PID is alive")
    args = ap.parse_args()

    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    existing_pid = read_pid(PID_PATH)
    if existing_pid and pid_is_running(existing_pid) and not args.force_new:
        print(f"GATK status server already appears active with PID {existing_pid}")
        print(f"Open: http://{args.host}:{args.port}/gatk")
        return 0

    cmd = [
        sys.executable,
        str(STATUS_APP),
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--gatk-run-root",
        args.run_root,
    ]
    proc = launch_detached(cmd, STDOUT_LOG, STDERR_LOG)
    PID_PATH.write_text(f"{proc.pid}\n", encoding="utf-8")
    print(f"GATK status server started with PID {proc.pid}")
    print(f"Open: http://{args.host}:{args.port}/gatk")
    print(f"stdout: {STDOUT_LOG}")
    print(f"stderr: {STDERR_LOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
