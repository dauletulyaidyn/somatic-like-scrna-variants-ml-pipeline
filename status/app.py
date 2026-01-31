#!/usr/bin/env python3
from flask import Flask, render_template, send_file, request
import json
import sqlite3
from pathlib import Path
from typing import Dict

app = Flask(__name__)
DB_PATH = Path(__file__).resolve().parent / "status.db"
REPO_ROOT = Path(__file__).resolve().parent.parent
STATUS_CONFIG = REPO_ROOT / "config" / "status_config.json"


def load_stage_config() -> Dict[str, dict]:
    if not STATUS_CONFIG.exists():
        return {}
    cfg = json.loads(STATUS_CONFIG.read_text(encoding="utf-8"))
    return {s.get("id"): s for s in cfg.get("stages", []) if s.get("id")}


def resolve_path(path_str: str) -> Path:
    p = Path(path_str)
    if not p.is_absolute():
        p = REPO_ROOT / p
    return p


def path_summary(path_str: str) -> dict:
    p = resolve_path(path_str)
    if not p.exists():
        return {"path": path_str, "resolved": str(p), "exists": False, "kind": "missing"}
    if p.is_file():
        return {
            "path": path_str,
            "resolved": str(p),
            "exists": True,
            "kind": "file",
            "size_bytes": p.stat().st_size,
        }
    try:
        entries = list(p.iterdir())
    except OSError:
        entries = []
    return {
        "path": path_str,
        "resolved": str(p),
        "exists": True,
        "kind": "dir",
        "entries": len(entries),
    }


def db():
    return sqlite3.connect(DB_PATH)


@app.route("/")
def index():
    con = db()
    cur = con.cursor()
    cur.execute("SELECT id, description, last_status, last_start_ts, last_end_ts, last_duration, last_estimate_error, last_error, last_error_ts FROM stages ORDER BY id")
    rows = cur.fetchall()
    con.close()
    cfg = load_stage_config()
    stages = []
    for r in rows:
        sid = r[0]
        meta = cfg.get(sid, {})
        stages.append(
            {
                "id": sid,
                "description": r[1] or meta.get("description", ""),
                "status": r[2],
                "start_ts": r[3],
                "end_ts": r[4],
                "duration": r[5],
                "estimate_error": r[6],
                "last_error": r[7],
                "inputs": meta.get("inputs", []),
                "outputs": meta.get("outputs", []),
            }
        )
    return render_template("index.html", stages=stages)


@app.route("/stage/<stage_id>")
def stage(stage_id):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT id, description, last_status, last_start_ts, last_end_ts, last_duration, last_estimate_error, last_error, last_error_ts, estimate_seconds FROM stages WHERE id=?", (stage_id,))
    st = cur.fetchone()
    cur.execute("SELECT type, ts, message FROM events WHERE stage=? ORDER BY ts DESC", (stage_id,))
    events = cur.fetchall()
    cur.execute("SELECT path, size_bytes, ts FROM files WHERE stage=? ORDER BY ts DESC", (stage_id,))
    files = cur.fetchall()
    con.close()
    cfg = load_stage_config()
    meta = cfg.get(stage_id, {})
    inputs = [path_summary(p) for p in meta.get("inputs", [])]
    outputs = [path_summary(p) for p in meta.get("outputs", [])]
    return render_template(
        "stage.html",
        stage=st,
        events=events,
        files=files,
        inputs=inputs,
        outputs=outputs,
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
