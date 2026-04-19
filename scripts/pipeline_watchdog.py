#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
STATUS_SCRIPT = REPO_ROOT / "scripts" / "status.py"
STATUS_CONFIG = REPO_ROOT / "config" / "status_config.json"
RUNNER = REPO_ROOT / "scripts" / "run_agentic_pipeline.py"
STATUS_APP = REPO_ROOT / "status" / "app.py"
STATUS_DIR = REPO_ROOT / "status"
DB_PATH = STATUS_DIR / "status.db"
RUNNER_STATE_PATH = STATUS_DIR / "pipeline_supervisor.json"
RUNNER_PID_PATH = STATUS_DIR / "pipeline_runner.pid"
RUNNER_STDOUT_LOG = STATUS_DIR / "pipeline_runner.out.log"
RUNNER_STDERR_LOG = STATUS_DIR / "pipeline_runner.err.log"
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


def read_pid(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent, encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
        tmp_name = handle.name
    os.replace(tmp_name, path)


def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def start_status_server(port: int) -> None:
    if port_open("127.0.0.1", port):
        return
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    stdout = (STATUS_DIR / "status_server.out.log").open("a", encoding="utf-8")
    stderr = (STATUS_DIR / "status_server.err.log").open("a", encoding="utf-8")
    kwargs = {"cwd": REPO_ROOT, "stdout": stdout, "stderr": stderr}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    subprocess.Popen([sys.executable, str(STATUS_APP), "--port", str(port)], **kwargs)
    time.sleep(1.5)


def stage_order() -> list[str]:
    cfg = json.loads(STATUS_CONFIG.read_text(encoding="utf-8"))
    return [str(stage["id"]) for stage in cfg.get("stages", [])]


def load_stage_rows() -> dict[str, dict[str, object]]:
    con = db()
    cur = con.cursor()
    cur.execute(
        """
        SELECT id, estimate_seconds, last_status, last_start_ts, last_end_ts, last_error
        FROM stages
        """
    )
    rows = {str(row["id"]): dict(row) for row in cur.fetchall()}
    con.close()
    return rows


def log_status(cmd: str, *args: str) -> None:
    subprocess.run([sys.executable, str(STATUS_SCRIPT), cmd, *args], cwd=REPO_ROOT, check=False)


def compute_plan(order: list[str], rows: dict[str, dict[str, object]]) -> tuple[str | None, str, list[str], dict[str, object]]:
    anomalies: list[str] = []
    counts = {"finished": 0, "running": 0, "error": 0, "idle": 0}
    earliest_unfinished: str | None = None
    seen_unfinished = False
    running_stage: str | None = None
    overdue_stage: str | None = None
    now = time.time()

    for stage_id in order:
        row = rows.get(stage_id, {})
        status = str(row.get("last_status") or "idle")
        counts[status] = counts.get(status, 0) + 1

        if status == "running":
            if running_stage is None:
                running_stage = stage_id
            else:
                anomalies.append(f"multiple_running:{running_stage},{stage_id}")

            start_ts = row.get("last_start_ts")
            estimate = float(row.get("estimate_seconds") or 0)
            if start_ts:
                elapsed = max(0.0, now - float(start_ts))
                threshold = max(estimate * 2.0, 1800.0)
                if elapsed > threshold:
                    overdue_stage = stage_id
                    anomalies.append(f"stage_overdue:{stage_id}:{elapsed:.0f}s")

        if status != "finished" and earliest_unfinished is None:
            earliest_unfinished = stage_id
            seen_unfinished = True
        elif status == "finished" and seen_unfinished:
            anomalies.append(f"out_of_order_finished:{stage_id}")

    if counts.get("running", 0) > 1:
        anomalies.append("sequence_violation:multiple_running_stages")

    if counts.get("finished", 0) == len(order):
        return None, "complete", anomalies, {"counts": counts, "running_stage": running_stage, "overdue_stage": overdue_stage}

    if running_stage:
        return running_stage, "resume_running_stage_if_runner_dead", anomalies, {"counts": counts, "running_stage": running_stage, "overdue_stage": overdue_stage}

    if earliest_unfinished:
        row = rows.get(earliest_unfinished, {})
        status = str(row.get("last_status") or "idle")
        if status == "error":
            return earliest_unfinished, "retry_earliest_error", anomalies, {"counts": counts, "running_stage": running_stage, "overdue_stage": overdue_stage}
        return earliest_unfinished, "continue_from_next_unfinished", anomalies, {"counts": counts, "running_stage": running_stage, "overdue_stage": overdue_stage}

    return None, "unknown", anomalies, {"counts": counts, "running_stage": running_stage, "overdue_stage": overdue_stage}


def start_runner(from_stage: str, status_port: int, use_wsl: bool, end_stage: str = "") -> int:
    cmd = [
        sys.executable,
        str(RUNNER),
        "--start-status",
        "--status-port",
        str(status_port),
        "--from-stage",
        from_stage,
    ]
    if end_stage:
        cmd.extend(["--end-stage", end_stage])
    if use_wsl:
        cmd.append("--use-wsl")

    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    stdout = RUNNER_STDOUT_LOG.open("a", encoding="utf-8")
    stderr = RUNNER_STDERR_LOG.open("a", encoding="utf-8")
    kwargs = {"cwd": REPO_ROOT, "stdout": stdout, "stderr": stderr}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    proc = subprocess.Popen(cmd, **kwargs)

    RUNNER_PID_PATH.write_text(f"{proc.pid}\n", encoding="utf-8")
    write_json_atomic(
        RUNNER_STATE_PATH,
        {
            "runner_pid": proc.pid,
            "from_stage": from_stage,
            "end_stage": end_stage,
            "status_port": status_port,
            "use_wsl": use_wsl,
            "launched_at": time.time(),
            "stdout_log": str(RUNNER_STDOUT_LOG),
            "stderr_log": str(RUNNER_STDERR_LOG),
            "command": cmd,
            "launched_by": "pipeline_watchdog",
        },
    )
    return proc.pid


def main() -> int:
    ap = argparse.ArgumentParser(description="Watchdog for sequential agentic execution of the legacy pipeline.")
    ap.add_argument("--interval-seconds", type=int, default=10)
    ap.add_argument("--status-port", type=int, default=5556)
    ap.add_argument("--use-wsl", action="store_true")
    ap.add_argument("--max-retries-per-stage", type=int, default=2)
    ap.add_argument("--ensure-status-server", action="store_true")
    args = ap.parse_args()

    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    WATCHDOG_PID_PATH.write_text(f"{os.getpid()}\n", encoding="utf-8")
    subprocess.run([sys.executable, str(STATUS_SCRIPT), "init", "--config", str(STATUS_CONFIG)], cwd=REPO_ROOT, check=False)

    state = read_json(WATCHDOG_STATE_PATH)
    retry_counts = state.get("retry_counts", {})
    if not isinstance(retry_counts, dict):
        retry_counts = {}

    while True:
        if args.ensure-status-server:
            start_status_server(args.status_port)

        order = stage_order()
        rows = load_stage_rows()
        next_stage, reason, anomalies, extras = compute_plan(order, rows)

        runner_state = read_json(RUNNER_STATE_PATH)
        runner_pid = read_pid(RUNNER_PID_PATH) or int(runner_state.get("runner_pid") or 0) or None
        runner_alive = pid_is_running(runner_pid)
        effective_use_wsl = bool(runner_state.get("use_wsl")) or args.use_wsl
        last_action = "observe"

        if runner_alive:
            last_action = "runner_alive"
        elif next_stage is None and reason == "complete":
            last_action = "pipeline_complete"
        elif next_stage:
            current_retry = int(retry_counts.get(next_stage, 0))
            if current_retry >= args.max_retries_per_stage:
                last_action = f"retry_limit_reached:{next_stage}"
                anomalies.append(f"retry_limit_reached:{next_stage}")
            else:
                current_status = str(rows.get(next_stage, {}).get("last_status") or "idle")
                if current_status == "running":
                    log_status(
                        "error",
                        "--stage",
                        next_stage,
                        "--message",
                        "watchdog detected dead runner during running stage; restarting automatically",
                    )
                elif current_status == "error":
                    log_status(
                        "error",
                        "--stage",
                        next_stage,
                        "--message",
                        "watchdog retrying failed stage automatically",
                    )
                new_pid = start_runner(next_stage, args.status_port, effective_use_wsl)
                retry_counts[next_stage] = current_retry + 1
                runner_pid = new_pid
                runner_alive = True
                last_action = f"restarted_from:{next_stage}"

        payload = {
            "watchdog_pid": os.getpid(),
            "alive": True,
            "last_check_ts": time.time(),
            "interval_seconds": args.interval_seconds,
            "status_port": args.status_port,
            "runner_pid_observed": runner_pid,
            "runner_alive": runner_alive,
            "use_wsl": effective_use_wsl,
            "next_stage_candidate": next_stage,
            "decision_reason": reason,
            "last_action": last_action,
            "retry_counts": retry_counts,
            "anomalies": anomalies,
            "counts": extras.get("counts", {}),
            "running_stage": extras.get("running_stage"),
            "overdue_stage": extras.get("overdue_stage"),
        }
        write_json_atomic(WATCHDOG_STATE_PATH, payload)
        time.sleep(max(2, int(args.interval_seconds)))


if __name__ == "__main__":
    raise SystemExit(main())
