#!/usr/bin/env python3
from flask import Flask, render_template, send_file, request
import sqlite3
from pathlib import Path

app = Flask(__name__)
DB_PATH = Path(__file__).resolve().parent / "status.db"


def db():
    return sqlite3.connect(DB_PATH)


@app.route("/")
def index():
    con = db()
    cur = con.cursor()
    cur.execute("SELECT id, description, last_status, last_start_ts, last_end_ts, last_duration, last_estimate_error, last_error, last_error_ts FROM stages ORDER BY id")
    stages = cur.fetchall()
    con.close()
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
    return render_template("stage.html", stage=st, events=events, files=files)


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
