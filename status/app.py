#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file

STATUS_DIR_PATH = Path(__file__).resolve().parent
app = Flask(__name__, template_folder=str(STATUS_DIR_PATH / "templates"))

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "status" / "status.db"
SUPERVISOR_STATE_PATH = REPO_ROOT / "status" / "pipeline_supervisor.json"
WATCHDOG_STATE_PATH = REPO_ROOT / "status" / "pipeline_watchdog.json"
CHANGE_MANIFEST_PATH = REPO_ROOT / "config" / "pipeline_change_manifest.json"
DEFAULT_GATK_RUN_ROOT = Path(os.environ["GATK_RUN_ROOT"]) if os.environ.get("GATK_RUN_ROOT") else None
VCF_COUNT_CACHE: dict[str, dict[str, object]] = {}
BYTES_PER_GB = 1024**3

GATK_STEPS = (
    "AddOrReplaceReadGroups",
    "samtools index",
    "SplitNCigarReads",
    "HaplotypeCaller",
    "VariantFiltration",
    "SelectVariants",
)
ESTIMATE_BASELINE_FILENAME = "gatk_estimate_baseline.json"


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


def fmt_bytes(num_bytes: int | None) -> str:
    if num_bytes is None:
        return ""
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024.0


def tail_lines(path: Path, line_count: int = 80, max_bytes: int = 256_000) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > max_bytes:
                handle.seek(-max_bytes, os.SEEK_END)
                handle.readline()
            data = handle.read()
        text = data.decode("utf-8", errors="replace")
    except Exception as exc:
        return [f"Could not read {path}: {exc}"]
    return text.splitlines()[-line_count:]


def read_text_safe(path: Path, max_bytes: int = 2_000_000) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > max_bytes:
                handle.seek(-max_bytes, os.SEEK_END)
                handle.readline()
            data = handle.read()
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


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


def windows_path_to_wsl(path: Path) -> str:
    text = str(path)
    if re.match(r"^[A-Za-z]:\\", text):
        drive = text[0].lower()
        rest = text[2:].replace("\\", "/").lstrip("/")
        return f"/mnt/{drive}/{rest}"
    return text


def run_ps_snapshot() -> list[dict[str, str]]:
    command = "ps -eo pid=,ppid=,etime=,cmd="
    if os.name == "nt":
        cmd = ["wsl.exe", "-e", "bash", "-lc", command]
    else:
        cmd = ["bash", "-lc", command]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, **hidden_subprocess_kwargs())
    if proc.returncode != 0:
        return []
    rows = []
    for line in proc.stdout.splitlines():
        parts = line.strip().split(None, 3)
        if len(parts) < 4:
            continue
        rows.append({"pid": parts[0], "ppid": parts[1], "etime": parts[2], "cmd": parts[3]})
    return rows


def infer_step_from_text(text: str) -> str:
    for step in GATK_STEPS:
        if step in text:
            return step
    if "samtools index" in text:
        return "samtools index"
    return ""


def infer_sample_from_text(text: str) -> str:
    match = re.search(r"(SRR\d+)", text)
    return match.group(1) if match else ""


def process_snapshot_for_run(run_root: Path) -> dict[str, object]:
    root_markers = {str(run_root), windows_path_to_wsl(run_root)}
    rows = []
    for proc in run_ps_snapshot():
        cmd = proc["cmd"]
        if not any(marker and marker in cmd for marker in root_markers):
            continue
        if not any(token in cmd for token in ("run_gatk.py", "gatk", "samtools", "run_remaining", "run_GATK")):
            continue
        item = dict(proc)
        item["step"] = infer_step_from_text(cmd)
        item["sample"] = infer_sample_from_text(cmd)
        rows.append(item)

    active_by_sample: dict[str, dict[str, str]] = {}
    for row in rows:
        sample = str(row.get("sample") or "")
        step = str(row.get("step") or "")
        if sample and step in GATK_STEPS:
            active_by_sample[sample] = {
                "sample": sample,
                "step": step,
                "pid": str(row.get("pid") or ""),
                "etime": str(row.get("etime") or ""),
                "cmd": str(row.get("cmd") or ""),
            }

    current = next((row for row in rows if row.get("step") in GATK_STEPS), None)
    if current is None:
        current = next((row for row in rows if "run_gatk.py" in row.get("cmd", "")), None)
    return {
        "active": bool(rows),
        "current_sample": current.get("sample", "") if current else "",
        "current_step": current.get("step", "") if current else "",
        "active_samples": list(active_by_sample.values()),
        "processes": rows,
    }


def latest_pid_state(run_root: Path) -> dict[str, object]:
    candidates = sorted((run_root / "logs").glob("*pid*.txt"), key=lambda p: p.stat().st_mtime if p.exists() else 0)
    if not candidates:
        return {"pid": None, "running": False, "pid_file": ""}
    pid_file = candidates[-1]
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except Exception:
        pid = None
    return {"pid": pid, "running": pid_is_running(pid), "pid_file": str(pid_file)}


def discover_gatk_samples(run_root: Path) -> list[str]:
    samples: set[str] = set()
    for pattern in ("input_bam*/*.bam", "one_sample_input*/*.bam", "vcf/*.raw.vcf", "vcf/*.filtered.vcf", "outputs/metrics/*.gatk.log"):
        for path in run_root.glob(pattern):
            name = path.name
            if name.endswith(".gatk.log"):
                samples.add(name[: -len(".gatk.log")])
            elif name.endswith(".raw.vcf"):
                samples.add(name[: -len(".raw.vcf")])
            elif name.endswith(".filtered.vcf"):
                samples.add(name[: -len(".filtered.vcf")])
            elif name.endswith(".bam"):
                samples.add(path.stem)
    return sorted(samples, key=lambda value: (re.sub(r"\d+", "", value), [int(x) for x in re.findall(r"\d+", value)] or [0], value))


def vcf_record_count(path: Path) -> int | None:
    if not path.exists() or not path.is_file() or path.stat().st_size == 0:
        return None
    stat = path.stat()
    cache_key = str(path)
    cached = VCF_COUNT_CACHE.get(cache_key)
    if cached and cached.get("mtime") == stat.st_mtime and cached.get("size") == stat.st_size:
        return int(cached["count"])
    count = 0
    try:
        with path.open("rb") as handle:
            for line in handle:
                if line.startswith(b"#"):
                    continue
                count += 1
    except Exception:
        return None
    VCF_COUNT_CACHE[cache_key] = {"mtime": stat.st_mtime, "size": stat.st_size, "count": count}
    return count


def file_payload(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"exists": False, "path": str(path), "size_bytes": 0, "size": "", "mtime": ""}
    stat = path.stat()
    return {
        "exists": True,
        "path": str(path),
        "size_bytes": stat.st_size,
        "size": fmt_bytes(stat.st_size),
        "mtime": fmt_ts(stat.st_mtime),
    }


def find_input_bam(run_root: Path, sample: str) -> Path:
    for pattern in ("input_bam*/*.bam", "one_sample_input*/*.bam"):
        candidate = next(run_root.glob(pattern.replace("*.bam", f"{sample}.bam")), None)
        if candidate:
            return candidate
    return run_root / "input_bam" / f"{sample}.bam"


def file_size_gb(file_info: dict[str, object] | None) -> float | None:
    if not file_info:
        return None
    size = file_info.get("size_bytes")
    if not isinstance(size, (int, float)) or size <= 0:
        return None
    return float(size) / BYTES_PER_GB


def timestamp_from_brackets(line: str) -> str:
    match = re.search(r"\[([^\]]+)\]", line)
    return clean_timestamp(match.group(1)) if match else ""


def timestamp_from_start_date(line: str) -> str:
    marker = "Start Date/Time:"
    if marker not in line:
        return ""
    return clean_timestamp(line.split(marker, 1)[1])


def clean_timestamp(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u202f", " ").replace("\xa0", " ")).strip()


def parse_log_datetime(value: str) -> datetime | None:
    value = clean_timestamp(value)
    if not value:
        return None
    value = re.sub(r"\s+(?!(?:AM|PM)\b)[A-Z]{2,5}\b", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    for fmt in (
        "%a %b %d %H:%M:%S %Y",
        "%b %d, %Y, %I:%M:%S %p",
        "%B %d, %Y, %I:%M:%S %p",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def fmt_dt(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else ""


def fmt_duration_minutes(minutes: float | None) -> str:
    if minutes is None:
        return ""
    minutes = max(0.0, float(minutes))
    if minutes < 1:
        return f"{minutes:.1f} min"
    if minutes < 90:
        return f"{minutes:.0f} min"
    hours = int(minutes // 60)
    mins = int(round(minutes % 60))
    if mins == 60:
        hours += 1
        mins = 0
    return f"{hours} h {mins} min"


def fmt_signed_duration_minutes(minutes: float | None) -> str:
    if minutes is None:
        return ""
    sign = "+" if minutes >= 0 else "-"
    return f"{sign}{fmt_duration_minutes(abs(minutes))}"


def elapsed_from_done_line(line: str) -> str:
    match = re.search(r"Elapsed time:\s*([^.]+(?:\.\d+)?)\s*minutes", line)
    return f"{match.group(1)} min" if match else ""


def elapsed_minutes_from_done_line(line: str) -> float | None:
    match = re.search(r"Elapsed time:\s*([0-9.]+)\s*minutes", line)
    return float(match.group(1)) if match else None


def build_step_timeline(lines: list[str]) -> dict[str, dict[str, object]]:
    records = {
        step: {
            "step": step,
            "start": "",
            "end": "",
            "elapsed": "",
            "elapsed_minutes": None,
            "done": False,
            "start_inferred": False,
            "end_inferred": False,
        }
        for step in GATK_STEPS
    }
    saw_samtools_index = False

    for line in lines:
        step = infer_step_from_text(line)
        if line.startswith("CMD:"):
            if step == "samtools index":
                saw_samtools_index = True
            continue

        if "Start Date/Time:" in line and step in records:
            records[step]["start"] = timestamp_from_start_date(line)
            records[step]["start_inferred"] = False
            continue

        if (
            step == "AddOrReplaceReadGroups"
            and "AddOrReplaceReadGroups --" in line
            and " done. Elapsed time:" not in line
        ):
            records[step]["start"] = timestamp_from_brackets(line)
            records[step]["start_inferred"] = False
            continue

        if " done. Elapsed time:" in line and step in records:
            records[step]["end"] = timestamp_from_brackets(line)
            records[step]["elapsed"] = elapsed_from_done_line(line)
            records[step]["elapsed_minutes"] = elapsed_minutes_from_done_line(line)
            records[step]["done"] = True
            records[step]["end_inferred"] = False

    if saw_samtools_index:
        samtools = records["samtools index"]
        previous_end = records["AddOrReplaceReadGroups"]["end"]
        next_start = records["SplitNCigarReads"]["start"]
        if previous_end and not samtools["start"]:
            samtools["start"] = str(previous_end)
            samtools["start_inferred"] = True
        if next_start and not samtools["end"]:
            samtools["end"] = str(next_start)
            samtools["end_inferred"] = True
        if next_start:
            samtools["done"] = True
        start_dt = parse_log_datetime(str(samtools["start"]))
        end_dt = parse_log_datetime(str(samtools["end"]))
        if start_dt and end_dt and end_dt >= start_dt:
            elapsed = (end_dt - start_dt).total_seconds() / 60.0
            samtools["elapsed_minutes"] = elapsed
            samtools["elapsed"] = fmt_duration_minutes(elapsed)

    return records


def parse_progress_locus(lines: list[str]) -> dict[str, object] | None:
    for line in reversed(lines):
        if "ProgressMeter -" not in line:
            continue
        match = re.search(r"ProgressMeter -\s+([A-Za-z0-9_.-]+):([0-9,]+)\s+([0-9.]+)", line)
        if not match:
            continue
        return {
            "contig": match.group(1),
            "position": int(match.group(2).replace(",", "")),
            "elapsed_minutes": float(match.group(3)),
            "line": line.strip(),
        }
    return None


def load_contig_index(run_root: Path) -> dict[str, object]:
    candidates = sorted((run_root / "ref").glob("*.fai"))
    if not candidates:
        return {"total": 0, "offsets": {}, "lengths": {}, "source": ""}
    lengths: dict[str, int] = {}
    offsets: dict[str, int] = {}
    total = 0
    try:
        for line in candidates[0].read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            contig = parts[0]
            length = int(parts[1])
            offsets[contig] = total
            lengths[contig] = length
            total += length
    except Exception:
        return {"total": 0, "offsets": {}, "lengths": {}, "source": str(candidates[0])}
    return {"total": total, "offsets": offsets, "lengths": lengths, "source": str(candidates[0])}


def progress_fraction(progress: dict[str, object] | None, contig_index: dict[str, object]) -> float | None:
    if not progress:
        return None
    total = int(contig_index.get("total") or 0)
    offsets = contig_index.get("offsets") or {}
    lengths = contig_index.get("lengths") or {}
    contig = str(progress.get("contig") or "")
    position = int(progress.get("position") or 0)
    if total <= 0 or contig not in offsets or contig not in lengths:
        return None
    length = int(lengths[contig])
    offset = int(offsets[contig])
    clamped_position = min(max(position, 0), length)
    return min(0.999, max(0.001, (offset + clamped_position) / total))


def build_duration_stats(parsed_logs: dict[str, dict[str, object]]) -> dict[str, dict[str, float]]:
    values: dict[str, list[float]] = {step: [] for step in GATK_STEPS}
    for log_info in parsed_logs.values():
        for detail in log_info.get("done_step_details", []):
            elapsed = detail.get("elapsed_minutes")
            if isinstance(elapsed, (int, float)) and elapsed > 0:
                values[str(detail["step"])].append(float(elapsed))

    stats: dict[str, dict[str, float]] = {}
    for step, step_values in values.items():
        if not step_values:
            continue
        ordered = sorted(step_values)
        mid = len(ordered) // 2
        if len(ordered) % 2:
            expected = ordered[mid]
        else:
            expected = (ordered[mid - 1] + ordered[mid]) / 2
        if len(ordered) == 1:
            stats[step] = {
                "min": max(0.1, ordered[0] * 0.8),
                "expected": ordered[0],
                "max": max(ordered[0], ordered[0] * 1.3),
            }
        else:
            stats[step] = {"min": ordered[0], "expected": expected, "max": ordered[-1]}
    return stats


def estimate_payload(min_minutes: float, expected_minutes: float, max_minutes: float, now: datetime, method: str) -> dict[str, object]:
    min_minutes = max(0.0, float(min_minutes))
    expected_minutes = max(min_minutes, float(expected_minutes))
    max_minutes = max(expected_minutes, float(max_minutes))
    return {
        "min_minutes": round(min_minutes, 1),
        "expected_minutes": round(expected_minutes, 1),
        "max_minutes": round(max_minutes, 1),
        "min_remaining": fmt_duration_minutes(min_minutes),
        "expected_remaining": fmt_duration_minutes(expected_minutes),
        "max_remaining": fmt_duration_minutes(max_minutes),
        "min_finish": fmt_dt(now + timedelta(minutes=min_minutes)),
        "expected_finish": fmt_dt(now + timedelta(minutes=expected_minutes)),
        "max_finish": fmt_dt(now + timedelta(minutes=max_minutes)),
        "method": method,
    }


def json_clone(value: object) -> object:
    return json.loads(json.dumps(value))


def estimate_baseline_path(run_root: Path) -> Path:
    return run_root / "logs" / ESTIMATE_BASELINE_FILENAME


def load_estimate_baseline(run_root: Path) -> dict[str, object]:
    path = estimate_baseline_path(run_root)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def save_estimate_baseline(run_root: Path, baseline: dict[str, object]) -> None:
    path = estimate_baseline_path(run_root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(baseline, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(path)
    except Exception:
        return


def attach_baseline_estimate_field(
    output: dict[str, object],
    output_key: str,
    baseline: dict[str, object],
    baseline_key: str,
    baseline_output_key: str,
) -> bool:
    value = output.get(output_key)
    cached = baseline.get(baseline_key)
    if isinstance(cached, dict):
        output[baseline_output_key] = json_clone(cached)
        return False

    if isinstance(value, dict):
        baseline[baseline_key] = json_clone(value)
        output[baseline_output_key] = json_clone(value)
        return True
    return False


def finished_estimate_with_prediction(
    finished_estimate: dict[str, object],
    prediction: dict[str, object],
) -> dict[str, object]:
    clone = json_clone(finished_estimate)
    if isinstance(clone, dict):
        apply_finished_prediction(clone, prediction)
        return clone
    return {}


def apply_finished_prediction(finished_estimate: dict[str, object], prediction: dict[str, object]) -> None:
    estimated_spend = prediction.get("estimated_spend")
    if not isinstance(estimated_spend, dict):
        return

    finished_estimate["estimated_spend"] = json_clone(estimated_spend)
    if prediction.get("method"):
        finished_estimate["method"] = prediction["method"]

    total_spend = finished_estimate.get("total_spend")
    if not isinstance(total_spend, dict):
        return
    actual_minutes = total_spend.get("minutes")
    if not isinstance(actual_minutes, (int, float)):
        return

    try:
        min_minutes = float(estimated_spend["min_minutes"])
        exact_minutes = float(estimated_spend["exact_minutes"])
        max_minutes = float(estimated_spend["max_minutes"])
    except (KeyError, TypeError, ValueError):
        return

    total_spend["deviation_from_min"] = fmt_signed_duration_minutes(actual_minutes - min_minutes)
    total_spend["deviation_from_exact"] = fmt_signed_duration_minutes(actual_minutes - exact_minutes)
    total_spend["deviation_from_max"] = fmt_signed_duration_minutes(actual_minutes - max_minutes)
    total_spend["deviation_minutes_from_min"] = round(actual_minutes - min_minutes, 1)
    total_spend["deviation_minutes_from_exact"] = round(actual_minutes - exact_minutes, 1)
    total_spend["deviation_minutes_from_max"] = round(actual_minutes - max_minutes, 1)


def attach_baseline_sample_step_estimates(sample: dict[str, object], sample_baseline: dict[str, object]) -> bool:
    changed = False
    step_estimates = sample.get("step_estimates")
    if not isinstance(step_estimates, list):
        return changed

    cached_steps = sample_baseline.setdefault("step_estimates", {})
    if not isinstance(cached_steps, dict):
        cached_steps = {}
        sample_baseline["step_estimates"] = cached_steps

    baseline_step_estimates = []
    for item in step_estimates:
        if not isinstance(item, dict):
            continue
        step = str(item.get("step") or "")
        estimate_type = str(item.get("type") or "")
        if not step or not estimate_type:
            continue
        key = f"{estimate_type}:{step}"
        cached = cached_steps.get(key)
        if isinstance(cached, dict):
            baseline_step_estimates.append({"step": step, "type": estimate_type, "finish": json_clone(cached)})
            continue
        finish = item.get("finish")
        if isinstance(finish, dict):
            cached_steps[key] = json_clone(finish)
            baseline_step_estimates.append({"step": step, "type": estimate_type, "finish": json_clone(finish)})
            changed = True
    if baseline_step_estimates:
        sample["baseline_step_estimates"] = baseline_step_estimates
    return changed


def attach_baseline_finished_sample_estimate(sample: dict[str, object], sample_baseline: dict[str, object]) -> bool:
    finished_estimate = sample.get("finished_estimate")
    if not isinstance(finished_estimate, dict):
        return False

    cached = sample_baseline.get("finished_estimate_prediction")
    if isinstance(cached, dict):
        sample["baseline_finished_estimate"] = finished_estimate_with_prediction(finished_estimate, cached)
        return False

    estimated_spend = finished_estimate.get("estimated_spend")
    if not isinstance(estimated_spend, dict):
        return False

    prediction = {
        "estimated_spend": json_clone(estimated_spend),
        "method": finished_estimate.get("method", ""),
    }
    sample_baseline["finished_estimate_prediction"] = prediction
    sample["baseline_finished_estimate"] = finished_estimate_with_prediction(finished_estimate, prediction)
    return True


def attach_estimate_baselines(run_root: Path, payload: dict[str, object]) -> None:
    baseline = load_estimate_baseline(run_root)
    changed = False
    if "created_at" not in baseline:
        baseline["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        changed = True
    payload["estimate_baseline_created_at"] = baseline.get("created_at", "")

    changed = attach_baseline_estimate_field(
        payload,
        "run_estimate",
        baseline,
        "run_estimate",
        "run_baseline_estimate",
    ) or changed

    samples_baseline = baseline.setdefault("samples", {})
    if not isinstance(samples_baseline, dict):
        samples_baseline = {}
        baseline["samples"] = samples_baseline
        changed = True

    samples = payload.get("samples")
    if not isinstance(samples, list):
        if changed:
            save_estimate_baseline(run_root, baseline)
        return

    for sample in samples:
        if not isinstance(sample, dict):
            continue
        sample_name = str(sample.get("sample") or "")
        if not sample_name:
            continue
        sample_baseline = samples_baseline.setdefault(sample_name, {})
        if not isinstance(sample_baseline, dict):
            sample_baseline = {}
            samples_baseline[sample_name] = sample_baseline
            changed = True

        changed = attach_baseline_estimate_field(
            sample,
            "queue_start_estimate",
            sample_baseline,
            "queue_start_estimate",
            "baseline_queue_start_estimate",
        ) or changed
        changed = attach_baseline_estimate_field(
            sample,
            "sample_estimate",
            sample_baseline,
            "sample_estimate",
            "baseline_sample_estimate",
        ) or changed
        changed = attach_baseline_sample_step_estimates(sample, sample_baseline) or changed
        changed = attach_baseline_finished_sample_estimate(sample, sample_baseline) or changed

    if changed:
        baseline["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_estimate_baseline(run_root, baseline)


def estimate_current_step_remaining(
    log_info: dict[str, object],
    duration_stats: dict[str, dict[str, float]],
    contig_index: dict[str, object],
    now: datetime,
) -> dict[str, object] | None:
    step = str(log_info.get("last_step") or "")
    if not step:
        return None
    start_dt = parse_log_datetime(str(log_info.get("current_step_started_at") or ""))
    elapsed = max(0.0, (now - start_dt).total_seconds() / 60.0) if start_dt else 0.0
    progress = log_info.get("current_progress") if isinstance(log_info.get("current_progress"), dict) else None
    fraction = progress_fraction(progress, contig_index)
    if fraction and elapsed > 0:
        total_expected = elapsed / fraction
        remaining_expected = max(0.0, total_expected - elapsed)
        return estimate_payload(
            remaining_expected * 0.65,
            remaining_expected,
            remaining_expected * 1.6,
            now,
            f"ProgressMeter {fraction * 100:.1f}% reference",
        )

    stats = duration_stats.get(step)
    if not stats:
        return None
    return estimate_payload(
        max(0.0, stats["min"] - elapsed),
        max(0.0, stats["expected"] - elapsed),
        max(0.0, stats["max"] - elapsed),
        now,
        "completed-sample duration",
    )


def estimate_full_step_duration(step: str, duration_stats: dict[str, dict[str, float]], now: datetime) -> dict[str, object] | None:
    stats = duration_stats.get(step)
    if not stats:
        return None
    return estimate_payload(stats["min"], stats["expected"], stats["max"], now, "completed-sample duration")


def build_running_step_estimates(
    log_info: dict[str, object],
    duration_stats: dict[str, dict[str, float]],
    contig_index: dict[str, object],
) -> tuple[list[dict[str, object]], dict[str, object] | None]:
    now = datetime.now()
    current_step = str(log_info.get("last_step") or "")
    if current_step not in GATK_STEPS:
        return [], None

    step_estimates: list[dict[str, object]] = []
    base_min = base_expected = base_max = 0.0
    current_index = GATK_STEPS.index(current_step)
    for index, step in enumerate(GATK_STEPS[current_index:], start=current_index):
        if index == current_index:
            estimate = estimate_current_step_remaining(log_info, duration_stats, contig_index, now)
            estimate_type = "current"
        else:
            estimate = estimate_full_step_duration(step, duration_stats, now)
            estimate_type = "upcoming"
        if not estimate:
            continue
        base_min += float(estimate["min_minutes"])
        base_expected += float(estimate["expected_minutes"])
        base_max += float(estimate["max_minutes"])
        chained = estimate_payload(base_min, base_expected, base_max, now, str(estimate["method"]))
        step_estimates.append({"step": step, "type": estimate_type, "finish": chained})

    sample_estimate = step_estimates[-1]["finish"] if step_estimates else None
    return step_estimates, sample_estimate


def estimate_full_sample_duration(duration_stats: dict[str, dict[str, float]]) -> dict[str, float] | None:
    totals = {"min": 0.0, "expected": 0.0, "max": 0.0}
    used = 0
    for step in GATK_STEPS:
        stats = duration_stats.get(step)
        if not stats:
            continue
        totals["min"] += stats["min"]
        totals["expected"] += stats["expected"]
        totals["max"] += stats["max"]
        used += 1
    return totals if used else None


def median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def stat_model(values: list[dict[str, float]]) -> dict[str, float] | None:
    if not values:
        return None
    model = {
        "min": median([value["min"] for value in values]),
        "expected": median([value["expected"] for value in values]),
        "max": median([value["max"] for value in values]),
    }
    model["expected"] = max(model["min"], model["expected"])
    model["max"] = max(model["expected"], model["max"])
    return model


def build_size_duration_models(samples: list[dict[str, object]]) -> dict[str, object]:
    now = datetime.now()
    full_values: list[dict[str, float]] = []
    step_values: dict[str, list[dict[str, float]]] = {step: [] for step in GATK_STEPS}

    for sample in samples:
        files = sample.get("files") if isinstance(sample.get("files"), dict) else {}
        input_gb = file_size_gb(files.get("input_bam") if isinstance(files, dict) else None)
        if not input_gb:
            continue

        for detail in sample.get("done_step_details", []):
            if not isinstance(detail, dict):
                continue
            elapsed = detail.get("elapsed_minutes")
            step = str(detail.get("step") or "")
            if step in step_values and isinstance(elapsed, (int, float)) and elapsed > 0:
                per_gb = float(elapsed) / input_gb
                step_values[step].append({"min": per_gb * 0.9, "expected": per_gb, "max": per_gb * 1.15})

        current_step = str(sample.get("current_step") or "")
        sample_estimate = sample.get("sample_estimate") if isinstance(sample.get("sample_estimate"), dict) else None
        if sample.get("status") == "running" and sample_estimate:
            step_start = parse_log_datetime(str(sample.get("current_step_started_at") or ""))
            if step_start and current_step in step_values:
                elapsed = max(0.0, (now - step_start).total_seconds() / 60.0)
                current_per_gb = {
                    "min": (elapsed + float(sample_estimate["min_minutes"])) / input_gb,
                    "expected": (elapsed + float(sample_estimate["expected_minutes"])) / input_gb,
                    "max": (elapsed + float(sample_estimate["max_minutes"])) / input_gb,
                }
                step_values[current_step].append(current_per_gb)

            sample_start = parse_log_datetime(str(sample.get("sample_started_at") or ""))
            if sample_start:
                elapsed = max(0.0, (now - sample_start).total_seconds() / 60.0)
                full_values.append(
                    {
                        "min": (elapsed + float(sample_estimate["min_minutes"])) / input_gb,
                        "expected": (elapsed + float(sample_estimate["expected_minutes"])) / input_gb,
                        "max": (elapsed + float(sample_estimate["max_minutes"])) / input_gb,
                    }
                )

        if sample.get("status") == "finished":
            sample_start = parse_log_datetime(str(sample.get("sample_started_at") or ""))
            sample_end = parse_log_datetime(str(sample.get("sample_finished_at") or ""))
            if sample_start and sample_end and sample_end > sample_start:
                minutes = (sample_end - sample_start).total_seconds() / 60.0
                per_gb = minutes / input_gb
                full_values.append({"min": per_gb * 0.9, "expected": per_gb, "max": per_gb * 1.2})

    return {
        "full_per_gb": stat_model(full_values),
        "step_per_gb": {step: stat_model(values) for step, values in step_values.items() if stat_model(values)},
    }


def scaled_duration_for_step(
    step: str,
    input_gb: float,
    size_models: dict[str, object],
    duration_stats: dict[str, dict[str, float]],
) -> dict[str, float] | None:
    step_models = size_models.get("step_per_gb") if isinstance(size_models.get("step_per_gb"), dict) else {}
    model = step_models.get(step) if isinstance(step_models, dict) else None
    if isinstance(model, dict):
        return {
            "min": float(model["min"]) * input_gb,
            "expected": float(model["expected"]) * input_gb,
            "max": float(model["max"]) * input_gb,
        }
    stats = duration_stats.get(step)
    if stats:
        return {"min": stats["min"], "expected": stats["expected"], "max": stats["max"]}
    return None


def scaled_full_duration(
    input_gb: float,
    size_models: dict[str, object],
    duration_stats: dict[str, dict[str, float]],
) -> dict[str, float] | None:
    model = size_models.get("full_per_gb")
    if isinstance(model, dict):
        return {
            "min": float(model["min"]) * input_gb,
            "expected": float(model["expected"]) * input_gb,
            "max": float(model["max"]) * input_gb,
        }
    return estimate_full_sample_duration(duration_stats)


def build_finished_sample_estimate(
    sample: dict[str, object],
    size_models: dict[str, object],
    duration_stats: dict[str, dict[str, float]],
) -> dict[str, object] | None:
    start_text = str(sample.get("sample_started_at") or "")
    end_text = str(sample.get("sample_finished_at") or "")
    start_dt = parse_log_datetime(start_text)
    end_dt = parse_log_datetime(end_text)
    if not start_dt or not end_dt or end_dt < start_dt:
        return None

    actual_minutes = (end_dt - start_dt).total_seconds() / 60.0
    files = sample.get("files") if isinstance(sample.get("files"), dict) else {}
    input_gb = file_size_gb(files.get("input_bam") if isinstance(files, dict) else None)
    estimate = scaled_full_duration(input_gb, size_models, duration_stats) if input_gb else estimate_full_sample_duration(duration_stats)
    if not estimate:
        return None

    return {
        "start": start_text,
        "end": end_text,
        "method": (
            f"input BAM {input_gb:.1f} GB; size-scaled from observed samples"
            if input_gb
            else "duration stats; input BAM size unavailable"
        ),
        "estimated_spend": {
            "min_minutes": round(float(estimate["min"]), 1),
            "exact_minutes": round(float(estimate["expected"]), 1),
            "max_minutes": round(float(estimate["max"]), 1),
            "min": fmt_duration_minutes(float(estimate["min"])),
            "exact": fmt_duration_minutes(float(estimate["expected"])),
            "max": fmt_duration_minutes(float(estimate["max"])),
        },
        "total_spend": {
            "minutes": round(actual_minutes, 1),
            "label": fmt_duration_minutes(actual_minutes),
            "deviation_from_min": fmt_signed_duration_minutes(actual_minutes - float(estimate["min"])),
            "deviation_from_exact": fmt_signed_duration_minutes(actual_minutes - float(estimate["expected"])),
            "deviation_from_max": fmt_signed_duration_minutes(actual_minutes - float(estimate["max"])),
            "deviation_minutes_from_min": round(actual_minutes - float(estimate["min"]), 1),
            "deviation_minutes_from_exact": round(actual_minutes - float(estimate["expected"]), 1),
            "deviation_minutes_from_max": round(actual_minutes - float(estimate["max"]), 1),
        },
    }


def build_pending_step_estimates(
    sample: dict[str, object],
    queue_minutes: dict[str, float],
    size_models: dict[str, object],
    duration_stats: dict[str, dict[str, float]],
    now: datetime,
) -> tuple[list[dict[str, object]], dict[str, object] | None]:
    files = sample.get("files") if isinstance(sample.get("files"), dict) else {}
    input_gb = file_size_gb(files.get("input_bam") if isinstance(files, dict) else None)
    if not input_gb:
        full_duration = estimate_full_sample_duration(duration_stats)
        if not full_duration:
            return [], None
        finish = estimate_payload(
            queue_minutes["min"] + full_duration["min"],
            queue_minutes["expected"] + full_duration["expected"],
            queue_minutes["max"] + full_duration["max"],
            now,
            "pending queue duration stats; input BAM size unavailable",
        )
        return [], finish

    step_estimates: list[dict[str, object]] = []
    cumulative = dict(queue_minutes)
    for step in GATK_STEPS:
        duration = scaled_duration_for_step(step, input_gb, size_models, duration_stats)
        if not duration:
            continue
        cumulative["min"] += duration["min"]
        cumulative["expected"] += duration["expected"]
        cumulative["max"] += duration["max"]
        finish = estimate_payload(
            cumulative["min"],
            cumulative["expected"],
            cumulative["max"],
            now,
            f"pending queue; input BAM {input_gb:.1f} GB; size-scaled from observed samples",
        )
        step_estimates.append({"step": step, "type": "pending", "finish": finish})

    sample_estimate = step_estimates[-1]["finish"] if step_estimates else None
    if sample_estimate is None:
        full_duration = scaled_full_duration(input_gb, size_models, duration_stats)
        if full_duration:
            sample_estimate = estimate_payload(
                queue_minutes["min"] + full_duration["min"],
                queue_minutes["expected"] + full_duration["expected"],
                queue_minutes["max"] + full_duration["max"],
                now,
                f"pending queue; input BAM {input_gb:.1f} GB; full-sample size model",
            )
    return step_estimates, sample_estimate


def add_pending_queue_estimates(
    samples: list[dict[str, object]],
    duration_stats: dict[str, dict[str, float]],
    size_models: dict[str, object],
) -> None:
    now = datetime.now()
    queue_minutes = {"min": 0.0, "expected": 0.0, "max": 0.0}

    for sample in samples:
        if sample.get("status") == "finished":
            continue
        if sample.get("status") == "running" and sample.get("sample_estimate"):
            estimate = sample["sample_estimate"]
            queue_minutes["min"] += float(estimate["min_minutes"])
            queue_minutes["expected"] += float(estimate["expected_minutes"])
            queue_minutes["max"] += float(estimate["max_minutes"])
            continue
        if sample.get("status") not in {"pending", "started"}:
            continue

        sample["queue_start_estimate"] = estimate_payload(
            queue_minutes["min"],
            queue_minutes["expected"],
            queue_minutes["max"],
            now,
            "queue before this sample",
        )
        step_estimates, sample_estimate = build_pending_step_estimates(
            sample,
            queue_minutes,
            size_models,
            duration_stats,
            now,
        )
        sample["step_estimates"] = step_estimates
        sample["sample_estimate"] = sample_estimate
        if sample_estimate:
            queue_minutes["min"] = float(sample_estimate["min_minutes"])
            queue_minutes["expected"] = float(sample_estimate["expected_minutes"])
            queue_minutes["max"] = float(sample_estimate["max_minutes"])


def add_finished_sample_estimates(
    samples: list[dict[str, object]],
    duration_stats: dict[str, dict[str, float]],
    size_models: dict[str, object],
) -> None:
    for sample in samples:
        if sample.get("status") != "finished":
            continue
        sample["finished_estimate"] = build_finished_sample_estimate(sample, size_models, duration_stats)


def build_run_estimate(samples: list[dict[str, object]], duration_stats: dict[str, dict[str, float]]) -> dict[str, object] | None:
    now = datetime.now()
    max_min = max_expected = max_max = 0.0
    for sample in samples:
        if sample.get("status") == "finished":
            continue
        if sample.get("sample_estimate"):
            estimate = sample["sample_estimate"]
            max_min = max(max_min, float(estimate["min_minutes"]))
            max_expected = max(max_expected, float(estimate["expected_minutes"]))
            max_max = max(max_max, float(estimate["max_minutes"]))
    if max_max <= 0:
        return None
    return estimate_payload(max_min, max_expected, max_max, now, "latest non-finished sample estimate in queue")


def parse_gatk_log(log_path: Path) -> dict[str, object]:
    text = read_text_safe(log_path, max_bytes=20_000_000)
    lines = text.splitlines()
    last_cmd = ""
    last_cmd_index = -1
    for index in range(len(lines) - 1, -1, -1):
        line = lines[index]
        if line.startswith("CMD:"):
            last_cmd = line
            last_cmd_index = index
            break
    step_records = build_step_timeline(lines)
    done_steps = [step for step in GATK_STEPS if step_records[step]["done"]]
    if "samtools index failed" in text:
        done_steps.append("samtools index failed")
    elapsed = []
    for line in lines:
        if " done. Elapsed time:" in line:
            elapsed.append(line.strip())
    done_step_details = [step_records[step] for step in GATK_STEPS if step_records[step]["done"]]
    started_at = next((str(step_records[step]["start"]) for step in GATK_STEPS if step_records[step]["start"]), "")
    finished_at = ""
    if step_records["SelectVariants"]["done"]:
        finished_at = str(step_records["SelectVariants"]["end"])
    current_step = infer_step_from_text(last_cmd)
    current_lines = lines[last_cmd_index:] if last_cmd_index >= 0 else lines
    return {
        "last_cmd": last_cmd,
        "last_step": current_step,
        "started_at": started_at,
        "finished_at": finished_at,
        "current_step_started_at": str(step_records[current_step]["start"]) if current_step in step_records else "",
        "current_progress": parse_progress_locus(current_lines),
        "done_step_details": done_step_details,
        "done_steps": done_steps,
        "elapsed": elapsed[-6:],
        "tail": tail_lines(log_path, 90),
    }


def sample_gatk_status(
    run_root: Path,
    sample: str,
    active_steps: dict[str, str],
    process_active: bool,
    log_info: dict[str, object],
    duration_stats: dict[str, dict[str, float]],
    contig_index: dict[str, object],
) -> dict[str, object]:
    vcf_dir = run_root / "vcf"
    metrics_dir = run_root / "outputs" / "metrics"
    log_path = metrics_dir / f"{sample}.gatk.log"
    files = {
        "input_bam": file_payload(find_input_bam(run_root, sample)),
        "rg_bam": file_payload(vcf_dir / f"{sample}.rg.bam"),
        "split_bam": file_payload(vcf_dir / f"{sample}.split.bam"),
        "raw_vcf": file_payload(vcf_dir / f"{sample}.raw.vcf"),
        "filtered_with_filters_vcf": file_payload(vcf_dir / f"{sample}.filtered.with_filters.vcf"),
        "filtered_vcf": file_payload(vcf_dir / f"{sample}.filtered.vcf"),
        "log": file_payload(log_path),
    }
    filtered_done = bool(files["filtered_vcf"]["exists"] and int(files["filtered_vcf"]["size_bytes"]) > 0)
    raw_done = bool(files["raw_vcf"]["exists"] and int(files["raw_vcf"]["size_bytes"]) > 0)

    if filtered_done or "SelectVariants" in log_info["done_steps"]:
        status = "finished"
    elif sample in active_steps and process_active:
        status = "running"
    elif files["log"]["exists"]:
        status = "stopped_or_failed" if not process_active else "started"
    else:
        status = "pending"

    step_estimates, sample_estimate = ([], None)
    if status == "running":
        step_estimates, sample_estimate = build_running_step_estimates(log_info, duration_stats, contig_index)

    return {
        "sample": sample,
        "status": status,
        "current_step": active_steps.get(sample) or log_info["last_step"],
        "sample_started_at": log_info["started_at"],
        "sample_finished_at": log_info["finished_at"],
        "current_step_started_at": log_info["current_step_started_at"],
        "raw_variants": vcf_record_count(vcf_dir / f"{sample}.raw.vcf") if raw_done else None,
        "pass_variants": vcf_record_count(vcf_dir / f"{sample}.filtered.vcf") if filtered_done else None,
        "files": files,
        "done_steps": log_info["done_steps"],
        "done_step_details": log_info["done_step_details"],
        "step_estimates": step_estimates,
        "sample_estimate": sample_estimate,
        "elapsed": log_info["elapsed"],
        "last_cmd": log_info["last_cmd"],
    }


def load_parallel_supervisor_state(run_root: Path) -> dict[str, object]:
    state_path = run_root / "logs" / "gatk_parallel_supervisor_state.json"
    if not state_path.exists():
        return {"exists": False, "path": str(state_path)}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"exists": True, "path": str(state_path), "error": str(exc)}
    if not isinstance(state, dict):
        return {"exists": True, "path": str(state_path), "error": "invalid JSON shape"}
    state["exists"] = True
    state["path"] = str(state_path)
    return state


def summarize_gatk_run(run_root: Path) -> dict[str, object]:
    process_state = process_snapshot_for_run(run_root)
    pid_state = latest_pid_state(run_root)
    sample_names = discover_gatk_samples(run_root)
    metrics_dir = run_root / "outputs" / "metrics"
    parsed_logs = {sample: parse_gatk_log(metrics_dir / f"{sample}.gatk.log") for sample in sample_names}
    duration_stats = build_duration_stats(parsed_logs)
    contig_index = load_contig_index(run_root)
    active_steps = {
        str(item.get("sample")): str(item.get("step"))
        for item in process_state.get("active_samples", [])
        if isinstance(item, dict) and item.get("sample") and item.get("step")
    }
    samples = [
        sample_gatk_status(
            run_root,
            sample,
            active_steps,
            bool(process_state.get("active")),
            parsed_logs[sample],
            duration_stats,
            contig_index,
        )
        for sample in sample_names
    ]
    counts = {"finished": 0, "running": 0, "pending": 0, "stopped_or_failed": 0, "started": 0}
    for sample in samples:
        status = str(sample["status"])
        counts[status] = counts.get(status, 0) + 1

    size_models = build_size_duration_models(samples)
    add_pending_queue_estimates(samples, duration_stats, size_models)
    add_finished_sample_estimates(samples, duration_stats, size_models)
    latest_logs = sorted((run_root / "logs").glob("*.log"), key=lambda p: p.stat().st_mtime if p.exists() else 0)
    disk = shutil.disk_usage(run_root) if run_root.exists() else None
    run_estimate = build_run_estimate(samples, duration_stats)
    payload = {
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "run_root": str(run_root),
        "exists": run_root.exists(),
        "pid": pid_state,
        "process": process_state,
        "parallel_supervisor": load_parallel_supervisor_state(run_root),
        "counts": counts,
        "run_estimate": run_estimate,
        "duration_stats": duration_stats,
        "size_duration_models": size_models,
        "reference_index": {"source": contig_index.get("source", ""), "total": contig_index.get("total", 0)},
        "samples": samples,
        "latest_log": str(latest_logs[-1]) if latest_logs else "",
        "latest_log_tail": tail_lines(latest_logs[-1], 80) if latest_logs else [],
        "disk_free": fmt_bytes(disk.free) if disk else "",
        "disk_total": fmt_bytes(disk.total) if disk else "",
    }
    attach_estimate_baselines(run_root, payload)
    return payload


def gatk_run_root_from_request() -> Path | None:
    raw = request.args.get("run_root") or (str(DEFAULT_GATK_RUN_ROOT) if DEFAULT_GATK_RUN_ROOT else "")
    if not raw:
        return None
    return Path(raw)


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


@app.route("/gatk")
def gatk_status_page():
    run_root = gatk_run_root_from_request()
    if run_root is None:
        return "missing run_root; pass /gatk?run_root=/path/to/run or start with --gatk-run-root", 400
    return render_template("gatk_status.html", run_root=str(run_root))


@app.route("/api/gatk-status")
def api_gatk_status():
    run_root = gatk_run_root_from_request()
    if run_root is None:
        return jsonify({"error": "missing run_root"}), 400
    return jsonify(summarize_gatk_run(run_root))


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=5556)
    ap.add_argument("--gatk-run-root", default="", help="Default GATK run folder for /gatk and /api/gatk-status")
    args = ap.parse_args()
    global DEFAULT_GATK_RUN_ROOT
    if args.gatk_run_root:
        DEFAULT_GATK_RUN_ROOT = Path(args.gatk_run_root)
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
