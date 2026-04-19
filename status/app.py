#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file

STATUS_DIR_PATH = Path(__file__).resolve().parent
app = Flask(__name__, template_folder=str(STATUS_DIR_PATH / "templates"))

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "status" / "status.db"
SUPERVISOR_STATE_PATH = REPO_ROOT / "status" / "pipeline_supervisor.json"
WATCHDOG_STATE_PATH = REPO_ROOT / "status" / "pipeline_watchdog.json"
CHANGE_MANIFEST_PATH = REPO_ROOT / "config" / "pipeline_change_manifest.json"


def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def fmt_ts(ts):
    if ts in (None, ""):
        return ""
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)


def fmt_num(val, digits=1):
    if val in (None, ""):
        return ""
    try:
        return f"{float(val):.{digits}f}"
    except Exception:
        return str(val)


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


def load_supervisor_state() -> dict[str, object]:
    if not SUPERVISOR_STATE_PATH.exists():
        return {"status": "not_started", "alive": False}
    try:
        state = json.loads(SUPERVISOR_STATE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "invalid_state", "alive": False, "error": str(exc)}
    pid = state.get("runner_pid")
    state["alive"] = pid_is_running(pid if isinstance(pid, int) else None)
    state["status"] = "running" if state["alive"] else "stopped"
    return state


def load_watchdog_state() -> dict[str, object]:
    if not WATCHDOG_STATE_PATH.exists():
        return {"status": "not_started", "alive": False, "anomalies": []}
    try:
        state = json.loads(WATCHDOG_STATE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "invalid_state", "alive": False, "anomalies": [], "error": str(exc)}
    pid = state.get("watchdog_pid")
    state["alive"] = pid_is_running(pid if isinstance(pid, int) else None)
    state["status"] = "running" if state["alive"] else "stopped"
    anomalies = state.get("anomalies", [])
    state["anomalies"] = anomalies if isinstance(anomalies, list) else [str(anomalies)]
    return state


def fetch_stages() -> list[dict[str, object]]:
    con = db()
    cur = con.cursor()
    cur.execute(
        """
        SELECT
            id,
            description,
            last_status,
            last_start_ts,
            last_end_ts,
            last_duration,
            last_estimate_error,
            last_error,
            last_error_ts,
            estimate_seconds
        FROM stages
        ORDER BY id
        """
    )
    rows = [dict(row) for row in cur.fetchall()]
    con.close()
    return rows


def load_change_manifest() -> dict[str, str]:
    if not CHANGE_MANIFEST_PATH.exists():
        return {}
    try:
        payload = json.loads(CHANGE_MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    changed = payload.get("changed_stages", {})
    if not isinstance(changed, dict):
        return {}
    return {str(k): str(v) for k, v in changed.items()}


def annotate_changed_stages(stages: list[dict[str, object]]) -> list[dict[str, object]]:
    changed = load_change_manifest()
    annotated = []
    for stage in stages:
        item = dict(stage)
        item["changed"] = item.get("id") in changed
        item["change_note"] = changed.get(str(item.get("id")), "")
        annotated.append(item)
    return annotated


def summarize_stages(stages: list[dict[str, object]]) -> dict[str, int]:
    counts = {"finished": 0, "running": 0, "error": 0, "idle": 0, "other": 0}
    for stage in stages:
        status = str(stage.get("last_status") or "idle")
        if status in counts:
            counts[status] += 1
        else:
            counts["other"] += 1
    return counts


def fetch_event_count() -> int:
    con = db()
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM events")
    value = int(cur.fetchone()[0])
    con.close()
    return value


@app.after_request
def disable_cache(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


app.jinja_env.filters["fmt_ts"] = fmt_ts
app.jinja_env.filters["fmt_num"] = fmt_num


@app.route("/")
def index():
    stages = annotate_changed_stages(fetch_stages())
    return render_template(
        "pipeline_index.html",
        stages=stages,
        stage_counts=summarize_stages(stages),
        event_count=fetch_event_count(),
        supervisor=load_supervisor_state(),
        watchdog=load_watchdog_state(),
    )


@app.route("/api/status")
def api_status():
    stages = annotate_changed_stages(fetch_stages())
    return jsonify(
        {
            "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "event_count": fetch_event_count(),
            "supervisor": load_supervisor_state(),
            "watchdog": load_watchdog_state(),
            "stage_counts": summarize_stages(stages),
            "stages": stages,
        }
    )


@app.route("/stage/<stage_id>")
def stage(stage_id):
    con = db()
    cur = con.cursor()
    cur.execute(
        """
        SELECT
            id,
            description,
            last_status,
            last_start_ts,
            last_end_ts,
            last_duration,
            last_estimate_error,
            last_error,
            last_error_ts,
            estimate_seconds
        FROM stages
        WHERE id=?
        """,
        (stage_id,),
    )
    stage_row = cur.fetchone()
    if stage_row is None:
        con.close()
        abort(404)
    cur.execute("SELECT type, ts, message FROM events WHERE stage=? ORDER BY ts DESC", (stage_id,))
    events = [dict(row) for row in cur.fetchall()]
    cur.execute("SELECT path, size_bytes, ts FROM files WHERE stage=? ORDER BY ts DESC", (stage_id,))
    files = [dict(row) for row in cur.fetchall()]
    con.close()
    changed = load_change_manifest()
    stage_payload = dict(stage_row)
    stage_payload["changed"] = stage_id in changed
    stage_payload["change_note"] = changed.get(stage_id, "")
    return render_template(
        "pipeline_stage.html",
        stage=stage_payload,
        events=events,
        files=files,
        supervisor=load_supervisor_state(),
        watchdog=load_watchdog_state(),
    )


@app.route("/file")
def file_view():
    path = request.args.get("path")
    if not path:
        return "missing path", 400
    p = Path(path)
    if not p.exists():
        return "not found", 404
    return send_file(str(p))


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=5556)
    args = ap.parse_args()
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
