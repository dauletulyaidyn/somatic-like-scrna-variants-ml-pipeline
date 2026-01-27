#!/usr/bin/env python3
import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "status" / "status.db"


def ensure_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS stages (
            id TEXT PRIMARY KEY,
            description TEXT,
            estimate_seconds INTEGER,
            last_status TEXT,
            last_start_ts REAL,
            last_end_ts REAL,
            last_error TEXT,
            last_error_ts REAL,
            last_duration REAL,
            last_estimate_error REAL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stage TEXT,
            type TEXT,
            ts REAL,
            message TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stage TEXT,
            path TEXT,
            size_bytes INTEGER,
            ts REAL
        )
        """
    )
    con.commit()
    return con


def init_from_config(config_path: Path):
    con = ensure_db()
    cur = con.cursor()
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    for s in cfg.get("stages", []):
        cur.execute(
            """
            INSERT OR REPLACE INTO stages (id, description, estimate_seconds, last_status)
            VALUES (?, ?, ?, COALESCE((SELECT last_status FROM stages WHERE id=?), 'idle'))
            """,
            (s["id"], s.get("description", ""), int(s.get("estimate_seconds", 0)), s["id"]),
        )
    con.commit()
    con.close()


def log_event(stage, etype, message=""):
    con = ensure_db()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO events (stage, type, ts, message) VALUES (?, ?, ?, ?)",
        (stage, etype, time.time(), message),
    )
    con.commit()
    con.close()


def update_stage(stage, **kwargs):
    con = ensure_db()
    cur = con.cursor()
    sets = []
    vals = []
    for k, v in kwargs.items():
        sets.append(f"{k}=?")
        vals.append(v)
    vals.append(stage)
    cur.execute(f"UPDATE stages SET {', '.join(sets)} WHERE id=?", vals)
    con.commit()
    con.close()


def record_files(stage, paths):
    con = ensure_db()
    cur = con.cursor()
    now = time.time()
    for p in paths:
        p = Path(p)
        if p.is_dir():
            files = [f for f in p.rglob("*") if f.is_file()]
        else:
            files = [p] if p.is_file() else []
        for f in files:
            cur.execute(
                "INSERT INTO files (stage, path, size_bytes, ts) VALUES (?, ?, ?, ?)",
                (stage, str(f), f.stat().st_size, now),
            )
    con.commit()
    con.close()


def main():
    ap = argparse.ArgumentParser(description="Status logger")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("--config", required=True)

    p_start = sub.add_parser("start")
    p_start.add_argument("--stage", required=True)
    p_start.add_argument("--message", default="")

    p_finish = sub.add_parser("finish")
    p_finish.add_argument("--stage", required=True)
    p_finish.add_argument("--message", default="")

    p_error = sub.add_parser("error")
    p_error.add_argument("--stage", required=True)
    p_error.add_argument("--message", default="")

    p_scan = sub.add_parser("scan")
    p_scan.add_argument("--stage", required=True)
    p_scan.add_argument("--paths", nargs="+", required=True)

    args = ap.parse_args()

    if args.cmd == "init":
        init_from_config(Path(args.config))
        return 0

    if args.cmd == "start":
        log_event(args.stage, "start", args.message)
        update_stage(args.stage, last_status="running", last_start_ts=time.time())
        return 0

    if args.cmd == "finish":
        con = ensure_db()
        cur = con.cursor()
        cur.execute("SELECT last_start_ts, estimate_seconds FROM stages WHERE id=?", (args.stage,))
        row = cur.fetchone()
        con.close()
        start_ts = row[0] if row else None
        estimate = row[1] if row else 0
        end_ts = time.time()
        duration = end_ts - start_ts if start_ts else None
        est_err = (duration - estimate) if (duration is not None and estimate) else None
        log_event(args.stage, "finish", args.message)
        update_stage(
            args.stage,
            last_status="finished",
            last_end_ts=end_ts,
            last_duration=duration,
            last_estimate_error=est_err,
        )
        return 0

    if args.cmd == "error":
        log_event(args.stage, "error", args.message)
        update_stage(args.stage, last_status="error", last_error=args.message, last_error_ts=time.time())
        return 0

    if args.cmd == "scan":
        record_files(args.stage, args.paths)
        log_event(args.stage, "scan", "scanned outputs")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
