#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import glob
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from run_autonomous_pipeline import (
    REPO_ROOT,
    STATUS_CONFIG,
    STATUS_SCRIPT,
    ensure_python_packages,
    ensure_python_packages_wsl,
    ensure_reference_defaults,
    ensure_whitelist,
    log_status,
    run,
    run_wsl,
    stage_definitions,
    start_status_server,
    try_install_external,
    try_install_external_wsl,
)


AGENTIC_CONFIG = REPO_ROOT / "config" / "agentic_pipeline_config.json"
STAGE_CONTRACTS = REPO_ROOT / "config" / "agentic_stage_contracts.json"


class StageFailure(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def resolve_repo_path(raw_path: str | Path) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else (REPO_ROOT / path)


def open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def role_config(agent_cfg: dict[str, Any], role_name: str) -> dict[str, Any]:
    return dict(agent_cfg.get("roles", {}).get(role_name, {}))


def stage_artifact_dir(stage_id: str) -> Path:
    return REPO_ROOT / stage_id / "outputs" / "agentic"


def safe_rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def tool_exists(tool: str, use_wsl: bool) -> bool:
    if use_wsl and os.name == "nt":
        proc = subprocess.run(
            ["wsl.exe", "-e", "bash", "-lc", f"command -v '{tool}' >/dev/null 2>&1"],
            cwd=REPO_ROOT,
            check=False,
        )
        return proc.returncode == 0
    return shutil.which(tool) is not None


def status_event(stage_id: str, event_type: str, message: str = "") -> None:
    subprocess.run(
        [
            sys.executable,
            str(STATUS_SCRIPT),
            "event",
            "--stage",
            stage_id,
            "--type",
            event_type,
            "--message",
            message,
        ],
        cwd=REPO_ROOT,
        check=False,
    )


def inspect_path(spec: dict[str, Any]) -> dict[str, Any]:
    raw_path = str(spec.get("path", ""))
    resolved = resolve_repo_path(raw_path)
    expected_kind = str(spec.get("kind", "") or "")
    exists = resolved.exists()
    actual_kind = "missing"
    size_bytes = None
    entry_count = None
    if exists:
        if resolved.is_dir():
            actual_kind = "dir"
            entry_count = sum(1 for _ in resolved.iterdir())
        elif resolved.is_file():
            actual_kind = "file"
            size_bytes = resolved.stat().st_size
        else:
            actual_kind = "other"

    min_entries = spec.get("min_entries")
    passed = True
    if spec.get("required", True) and not exists:
        passed = False
    if exists and expected_kind and actual_kind != expected_kind:
        passed = False
    if exists and actual_kind == "dir" and min_entries is not None and int(entry_count or 0) < int(min_entries):
        passed = False
    return {
        "path": raw_path,
        "resolved": str(resolved),
        "description": spec.get("description", ""),
        "required": bool(spec.get("required", True)),
        "exists": exists,
        "expected_kind": expected_kind,
        "actual_kind": actual_kind,
        "size_bytes": size_bytes,
        "entry_count": entry_count,
        "min_entries": min_entries,
        "passed": passed,
    }


def inspect_glob(spec: dict[str, Any]) -> dict[str, Any]:
    pattern = str(spec.get("pattern", ""))
    resolved_pattern = str(resolve_repo_path(pattern))
    matches = [Path(path) for path in glob.glob(resolved_pattern, recursive=True)]
    min_matches = int(spec.get("min_matches", 1))
    return {
        "pattern": pattern,
        "resolved_pattern": resolved_pattern,
        "description": spec.get("description", ""),
        "min_matches": min_matches,
        "match_count": len(matches),
        "matches": [str(path) for path in matches[:25]],
        "passed": len(matches) >= min_matches,
    }


def collect_stage_files(scan_paths: list[str]) -> list[Path]:
    files: list[Path] = []
    seen: set[str] = set()
    for raw_path in scan_paths:
        resolved = resolve_repo_path(raw_path)
        candidates = resolved.rglob("*") if resolved.is_dir() else [resolved]
        for candidate in candidates:
            if candidate.is_file():
                key = str(candidate.resolve())
                if key not in seen:
                    seen.add(key)
                    files.append(candidate)
    files.sort(key=lambda path: str(path).lower())
    return files


def summarize_table(path: Path, max_rows: int = 200) -> dict[str, Any] | None:
    name = path.name.lower()
    if not any(ext in name for ext in (".tsv", ".csv", ".txt")):
        return None
    delimiter = "\t" if ".tsv" in name else ","
    try:
        with open_text(path) as handle:
            reader = csv.reader(handle, delimiter=delimiter)
            header = next(reader, [])
            row_count = 0
            truncated = False
            for _row_count, _ in enumerate(reader, start=1):
                row_count = _row_count
                if row_count >= max_rows:
                    truncated = True
                    break
        return {
            "path": safe_rel(path),
            "columns": len(header),
            "header": header[:8],
            "rows_sampled": row_count,
            "truncated": truncated,
        }
    except Exception as exc:
        return {
            "path": safe_rel(path),
            "error": str(exc),
        }


def render_checks(checks: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for check in checks:
        status = "PASS" if check.get("passed") else "FAIL"
        parts = [f"- `{check.get('path')}`: {status}"]
        if check.get("description"):
            parts.append(f"({check['description']})")
        if check.get("exists") and check.get("actual_kind") == "file":
            parts.append(f"size={check.get('size_bytes', 0)} bytes")
        if check.get("exists") and check.get("actual_kind") == "dir":
            parts.append(f"entries={check.get('entry_count', 0)}")
        if not check.get("exists"):
            parts.append("missing")
        lines.append(" ".join(parts))
    return lines


def build_prompt(
    stage_id: str,
    role_name: str,
    contract: dict[str, Any],
    payload: dict[str, Any],
) -> str:
    return "\n".join(
        [
            f"# {stage_id} {role_name}",
            "",
            f"Stage: `{stage_id}`",
            f"Description: {contract.get('description', '')}",
            f"Role: `{role_name}`",
            "",
            "Payload:",
            "```json",
            json.dumps(payload, indent=2),
            "```",
            "",
            "Give a short PASS/FAIL style assessment with the main rationale.",
        ]
    )


def run_optional_provider(
    stage_id: str,
    role_name: str,
    prompt_text: str,
    agent_cfg: dict[str, Any],
) -> dict[str, Any]:
    artifact_dir = stage_artifact_dir(stage_id)
    prompt_path = artifact_dir / f"{stage_id}.{role_name}.prompt.md"
    response_path = artifact_dir / f"{stage_id}.{role_name}.response.txt"
    write_text(prompt_path, prompt_text)

    role_cfg = dict(agent_cfg.get("roles", {}).get(role_name, {}))
    provider_name = str(role_cfg.get("provider", ""))
    provider_cfg = dict(agent_cfg.get("providers", {}).get(provider_name, {}))
    required_for_advance = bool(role_cfg.get("required_for_advance", False))

    result = {
        "role": role_name,
        "provider": provider_name,
        "required_for_advance": required_for_advance,
        "enabled": bool(provider_cfg.get("enabled", False)),
        "prompt_path": safe_rel(prompt_path),
        "response_path": safe_rel(response_path),
        "status": "prompt_written",
        "approved": not required_for_advance,
    }

    if not provider_cfg.get("enabled", False):
        return result

    command_template = str(provider_cfg.get("command_template", "")).strip()
    if not command_template:
        result["status"] = "adapter_disabled_no_command"
        return result

    command = command_template.format(
        prompt_file=str(prompt_path),
        response_file=str(response_path),
        stage_id=stage_id,
        role=role_name,
        repo_root=str(REPO_ROOT),
    )
    exec_cmd = (
        ["powershell", "-NoProfile", "-Command", command]
        if os.name == "nt"
        else ["bash", "-lc", command]
    )
    proc = subprocess.run(
        exec_cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if not response_path.exists():
        response_text = proc.stdout or ""
        if proc.stderr:
            response_text = (response_text + "\n" + proc.stderr).strip()
        write_text(response_path, response_text)

    response_text = response_path.read_text(encoding="utf-8") if response_path.exists() else ""
    approval_regex = str(provider_cfg.get("approval_regex", "") or "")
    approved = True
    if required_for_advance and approval_regex:
        approved = re.search(approval_regex, response_text, flags=re.IGNORECASE) is not None
    result.update(
        {
            "status": "executed" if proc.returncode == 0 else "adapter_error",
            "return_code": proc.returncode,
            "approved": approved,
        }
    )
    return result


def run_preflight(
    stage_id: str,
    contract: dict[str, Any],
    command: list[str],
    use_wsl: bool,
    agent_cfg: dict[str, Any],
) -> dict[str, Any]:
    status_event(stage_id, "preflight", "running preflight validation")
    checks = [inspect_path(spec) for spec in contract.get("inputs", [])]
    tool_checks = [
        {
            "tool": tool,
            "passed": tool_exists(tool, use_wsl),
        }
        for tool in contract.get("required_tools", [])
    ]
    passed = all(check["passed"] for check in checks) and all(check["passed"] for check in tool_checks)
    payload = {
        "stage": stage_id,
        "description": contract.get("description", ""),
        "timestamp": time.time(),
        "command": [str(part) for part in command],
        "input_checks": checks,
        "tool_checks": tool_checks,
        "passed": passed,
    }
    provider_payload = {
        "stage": stage_id,
        "description": contract.get("description", ""),
        "input_checks": checks,
        "tool_checks": tool_checks,
        "decision": "PASS" if passed else "FAIL",
    }
    provider_result = run_optional_provider(
        stage_id,
        "stage_preflight_agent",
        build_prompt(stage_id, "stage_preflight_agent", contract, provider_payload),
        agent_cfg,
    )
    payload["provider_result"] = provider_result
    if provider_result.get("required_for_advance") and not provider_result.get("approved"):
        payload["passed"] = False
        payload["provider_gate_failed"] = True
    write_json(stage_artifact_dir(stage_id) / f"{stage_id}.preflight.json", payload)
    status_event(stage_id, "preflight_pass" if payload["passed"] else "preflight_fail", contract.get("description", ""))
    if not payload["passed"]:
        raise StageFailure(f"{stage_id} preflight validation failed")
    return payload


def run_execution(
    stage_id: str,
    contract: dict[str, Any],
    command: list[str],
    stage_runner,
    agent_cfg: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "stage": stage_id,
        "description": contract.get("description", ""),
        "executor": role_config(agent_cfg, "stage_execution_agent"),
        "command": [str(part) for part in command],
        "started_at": time.time(),
        "status": "running",
    }
    write_json(stage_artifact_dir(stage_id) / f"{stage_id}.execution.json", payload)
    status_event(stage_id, "execute", "stage command started")
    try:
        stage_runner(command, cwd=REPO_ROOT)
        payload["status"] = "finished"
        payload["return_code"] = 0
    except Exception as exc:
        payload["status"] = "error"
        payload["error"] = str(exc)
        payload["finished_at"] = time.time()
        write_json(stage_artifact_dir(stage_id) / f"{stage_id}.execution.json", payload)
        raise
    payload["finished_at"] = time.time()
    payload["duration_seconds"] = payload["finished_at"] - payload["started_at"]
    write_json(stage_artifact_dir(stage_id) / f"{stage_id}.execution.json", payload)
    status_event(stage_id, "execute_done", "stage command finished")
    return payload


def run_review(
    stage_id: str,
    contract: dict[str, Any],
    scan_paths: list[str],
    agent_cfg: dict[str, Any],
) -> dict[str, Any]:
    status_event(stage_id, "review", "reviewing outputs")
    checks = [inspect_path(spec) for spec in contract.get("outputs", [])]
    glob_checks = [inspect_glob(spec) for spec in contract.get("output_globs", [])]
    files = collect_stage_files(scan_paths)
    file_listing = [
        {
          "path": safe_rel(path),
          "size_bytes": path.stat().st_size,
        }
        for path in files[:50]
    ]
    table_summaries = []
    for path in files:
        summary = summarize_table(path)
        if summary is not None:
            table_summaries.append(summary)
        if len(table_summaries) >= 6:
            break

    passed = all(check["passed"] for check in checks) and all(check["passed"] for check in glob_checks)
    provider_payload = {
        "stage": stage_id,
        "description": contract.get("description", ""),
        "output_checks": checks,
        "glob_checks": glob_checks,
        "file_listing": file_listing[:20],
        "table_summaries": table_summaries,
        "decision": "PASS" if passed else "FAIL",
    }
    provider_result = run_optional_provider(
        stage_id,
        "stage_review_agent",
        build_prompt(stage_id, "stage_review_agent", contract, provider_payload),
        agent_cfg,
    )
    payload = {
        "stage": stage_id,
        "description": contract.get("description", ""),
        "timestamp": time.time(),
        "output_checks": checks,
        "glob_checks": glob_checks,
        "output_file_count": len(files),
        "files": file_listing,
        "table_summaries": table_summaries,
        "review_focus": contract.get("review_focus", []),
        "provider_result": provider_result,
        "passed": passed,
    }
    if provider_result.get("required_for_advance") and not provider_result.get("approved"):
        payload["passed"] = False
        payload["provider_gate_failed"] = True
    write_json(stage_artifact_dir(stage_id) / f"{stage_id}.review.json", payload)
    status_event(stage_id, "review_pass" if payload["passed"] else "review_fail", contract.get("description", ""))
    if not payload["passed"]:
        raise StageFailure(f"{stage_id} output review failed")
    return payload


def create_stage_report(
    stage_id: str,
    contract: dict[str, Any],
    preflight: dict[str, Any],
    execution: dict[str, Any],
    review: dict[str, Any],
    agent_cfg: dict[str, Any],
) -> dict[str, Any]:
    status_event(stage_id, "report", "writing mini report")
    artifact_dir = stage_artifact_dir(stage_id)
    report_path = artifact_dir / f"{stage_id}.mini_report.md"
    report_json_path = artifact_dir / f"{stage_id}.mini_report.json"

    summary_lines = [
        f"# {stage_id} Mini Report",
        "",
        f"- Stage description: {contract.get('description', '')}",
        f"- Preflight: {'PASS' if preflight.get('passed') else 'FAIL'}",
        f"- Execution: {execution.get('status', 'unknown')}",
        f"- Review: {'PASS' if review.get('passed') else 'FAIL'}",
        f"- Output files scanned: {review.get('output_file_count', 0)}",
        "",
        "## Input Validation",
        *render_checks(preflight.get("input_checks", [])),
        "",
        "## Execution",
        f"- Command: `{' '.join(str(part) for part in execution.get('command', []))}`",
        f"- Duration (s): {execution.get('duration_seconds', 0):.1f}" if execution.get("duration_seconds") is not None else "- Duration (s): n/a",
        "",
        "## Output Review",
        *render_checks(review.get("output_checks", [])),
    ]
    if review.get("glob_checks"):
        summary_lines.extend(["", "## Output Globs"])
        for item in review["glob_checks"]:
            summary_lines.append(
                f"- `{item['pattern']}`: {'PASS' if item['passed'] else 'FAIL'} (matches={item['match_count']}, expected>={item['min_matches']})"
            )
    if review.get("table_summaries"):
        summary_lines.extend(["", "## Table Snapshots"])
        for item in review["table_summaries"]:
            if item.get("error"):
                summary_lines.append(f"- `{item['path']}`: unreadable ({item['error']})")
            else:
                header = ", ".join(item.get("header", []))
                rows_text = f">={item['rows_sampled']}" if item.get("truncated") else str(item.get("rows_sampled", 0))
                summary_lines.append(
                    f"- `{item['path']}`: columns={item.get('columns', 0)}, sampled_rows={rows_text}, header={header}"
                )
    summary_lines.extend(
        [
            "",
            "## Mini Interpretation",
            *[f"- {item}" for item in contract.get("report_focus", [])],
            f"- Stage `{stage_id}` is {'ready' if review.get('passed') else 'not ready'} for downstream progression.",
        ]
    )
    write_text(report_path, "\n".join(summary_lines))

    payload = {
        "stage": stage_id,
        "description": contract.get("description", ""),
        "report_path": safe_rel(report_path),
        "created_at": time.time(),
        "preflight_passed": preflight.get("passed", False),
        "review_passed": review.get("passed", False),
        "report_focus": contract.get("report_focus", []),
    }
    provider_result = run_optional_provider(
        stage_id,
        "stage_report_agent",
        build_prompt(stage_id, "stage_report_agent", contract, payload),
        agent_cfg,
    )
    payload["provider_result"] = provider_result
    write_json(report_json_path, payload)
    status_event(stage_id, "report_done", safe_rel(report_path))
    return payload


def create_main_agent_decision(
    stage_id: str,
    next_stage_id: str | None,
    contract: dict[str, Any],
    preflight: dict[str, Any],
    execution: dict[str, Any],
    review: dict[str, Any],
    report: dict[str, Any],
    agent_cfg: dict[str, Any],
) -> dict[str, Any]:
    artifact_path = stage_artifact_dir(stage_id) / f"{stage_id}.main_agent_decision.json"
    can_advance = bool(preflight.get("passed")) and execution.get("status") == "finished" and bool(review.get("passed"))
    payload = {
        "stage": stage_id,
        "description": contract.get("description", ""),
        "decision_made_at": time.time(),
        "decision_by": "main_agent",
        "preflight_passed": bool(preflight.get("passed")),
        "execution_status": execution.get("status"),
        "review_passed": bool(review.get("passed")),
        "mini_report_path": report.get("report_path"),
        "next_stage_candidate": next_stage_id,
        "can_advance": can_advance,
        "reason": "all subordinate stage checks passed" if can_advance else "at least one subordinate stage check failed",
    }
    provider_result = run_optional_provider(
        stage_id,
        "main_agent",
        build_prompt(stage_id, "main_agent", contract, payload),
        agent_cfg,
    )
    payload["provider_result"] = provider_result
    write_json(artifact_path, payload)
    status_event(stage_id, "advance" if can_advance else "advance_blocked", payload["reason"])
    if not can_advance:
        raise StageFailure(f"{stage_id} main agent blocked advancement")
    return payload


def summarize_bundle(bundle_dir: Path) -> dict[str, int]:
    counts = {"total_files": 0, "figure_files": 0, "table_files": 0, "report_files": 0}
    figure_suffixes = {".png", ".jpg", ".jpeg", ".svg", ".pdf"}
    table_suffixes = {".tsv", ".csv", ".xlsx", ".xls"}
    report_suffixes = {".md", ".txt"}
    for path in bundle_dir.rglob("*"):
        if not path.is_file():
            continue
        counts["total_files"] += 1
        suffix = path.suffix.lower()
        if suffix in figure_suffixes:
            counts["figure_files"] += 1
        if suffix in table_suffixes:
            counts["table_files"] += 1
        if suffix in report_suffixes:
            counts["report_files"] += 1
    return counts


def build_final_report(
    stage_order: list[str],
    stage_results: dict[str, dict[str, Any]],
    agent_cfg: dict[str, Any],
    completed_all: bool,
) -> None:
    final_dir = REPO_ROOT / "12_integrated_interpretation" / "outputs" / "agentic"
    bundle_dir = REPO_ROOT / "for_report"
    bundle_reports_dir = bundle_dir / "agentic_stage_reports"
    final_dir.mkdir(parents=True, exist_ok=True)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    bundle_reports_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = bundle_dir / "agentic_stage_manifest.tsv"
    final_md_path = final_dir / "final_report.md"
    final_json_path = final_dir / "final_report.json"
    bundle_final_md_path = bundle_dir / "agentic_final_report.md"

    lines = [
        "# Agentic Final Report",
        "",
        f"- Workflow: `{agent_cfg.get('workflow_id', 'legacy_01_12_agentic')}`",
        f"- Finalized by: `main_agent`",
        f"- Completed all stages: {'yes' if completed_all else 'no'}",
        f"- Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Scientific Priority",
        "- Stages `01..10` are enabling layers that produce the validated inputs needed for interpretation.",
        "- Stage `11_correlation` is the primary integration stage for mutation-linked and expression-linked summaries.",
        "- Stage `12_integrated_interpretation` must compare the observed relationships with other studies and distinguish association from causation.",
        "",
        "## Stage Summary",
    ]

    manifest_rows = []
    for stage_id in stage_order:
        result = stage_results.get(stage_id)
        if not result:
            continue
        report_path = resolve_repo_path(result["report"]["report_path"])
        copied_report = bundle_reports_dir / report_path.name
        if report_path.exists():
            shutil.copy2(report_path, copied_report)
        manifest_rows.append(
            {
                "stage": stage_id,
                "description": result["contract"].get("description", ""),
                "preflight_passed": "yes" if result["preflight"].get("passed") else "no",
                "review_passed": "yes" if result["review"].get("passed") else "no",
                "output_file_count": str(result["review"].get("output_file_count", 0)),
                "stage_report": safe_rel(copied_report),
            }
        )
        lines.extend(
            [
                f"### {stage_id}",
                f"- Description: {result['contract'].get('description', '')}",
                f"- Preflight: {'PASS' if result['preflight'].get('passed') else 'FAIL'}",
                f"- Review: {'PASS' if result['review'].get('passed') else 'FAIL'}",
                f"- Output files: {result['review'].get('output_file_count', 0)}",
                f"- Stage report: `{safe_rel(copied_report)}`",
                "",
            ]
        )

    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["stage", "description", "preflight_passed", "review_passed", "output_file_count", "stage_report"])
        for row in manifest_rows:
            writer.writerow(
                [
                    row["stage"],
                    row["description"],
                    row["preflight_passed"],
                    row["review_passed"],
                    row["output_file_count"],
                    row["stage_report"],
                ]
            )

    bundle_summary = summarize_bundle(bundle_dir)
    lines.extend(
        [
            "## Final Bundle Summary",
            f"- Total bundle files: {bundle_summary['total_files']}",
            f"- Figures: {bundle_summary['figure_files']}",
            f"- Tables: {bundle_summary['table_files']}",
            f"- Reports: {bundle_summary['report_files']}",
            "",
        ]
    )

    payload = {
        "workflow_id": agent_cfg.get("workflow_id", "legacy_01_12_agentic"),
        "completed_all_stages": completed_all,
        "generated_at": time.time(),
        "generated_by": "main_agent",
        "stage_count": len(manifest_rows),
        "manifest_path": safe_rel(manifest_path),
        "bundle_final_report": safe_rel(bundle_final_md_path),
        "bundle_summary": bundle_summary,
    }
    provider_result = run_optional_provider(
        "12_integrated_interpretation",
        "main_agent",
        build_prompt("12_integrated_interpretation", "main_agent", {"description": "Final integrated report and bundle assembly"}, payload),
        agent_cfg,
    )
    payload["provider_result"] = provider_result
    write_text(final_md_path, "\n".join(lines))
    write_text(bundle_final_md_path, "\n".join(lines))
    write_json(final_json_path, payload)

    subprocess.run(
        [
            sys.executable,
            str(STATUS_SCRIPT),
            "scan",
            "--stage",
            "12_integrated_interpretation",
            "--paths",
            str(final_dir),
            str(bundle_dir),
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    status_event("12_integrated_interpretation", "final_report_done", safe_rel(bundle_final_md_path))


def write_agentic_brief() -> None:
    write_text(
        REPO_ROOT / "docs" / "AGENTIC_AGENT_QUICKSTART.md",
        "\n".join(
            [
                "# Agentic Agent Quickstart",
                "",
                "Canonical start command:",
                "- `python scripts/run_agentic_pipeline.py --auto-install --start-status --use-wsl`",
                "- `./zapusti_analiz.ps1`",
                "",
                "The runner uses one main agent plus subordinate stage agents or skills for preflight, execution, review, mini reports, and final aggregation.",
            ]
        ),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Agentic orchestration layer for the legacy 01..12 pipeline.")
    ap.add_argument("--auto-install", action="store_true", help="Attempt to install missing dependencies")
    ap.add_argument("--start-status", action="store_true", help="Start the Flask status server")
    ap.add_argument("--status-port", type=int, default=5556)
    ap.add_argument("--from-stage", default="01_input_data")
    ap.add_argument("--end-stage", default="")
    ap.add_argument("--use-wsl", action="store_true", help="Run stage commands inside WSL while keeping status UI local")
    ap.add_argument("--contracts", default=str(STAGE_CONTRACTS))
    ap.add_argument("--agent-config", default=str(AGENTIC_CONFIG))
    args = ap.parse_args()

    agent_cfg = load_json(resolve_repo_path(args.agent_config))
    agent_cfg.setdefault("workflow_id", "legacy_01_12_agentic")
    contracts_cfg = load_json(resolve_repo_path(args.contracts))
    contract_map = {str(item["id"]): item for item in contracts_cfg.get("stages", [])}

    write_agentic_brief()
    subprocess.run([sys.executable, str(STATUS_SCRIPT), "init", "--config", str(STATUS_CONFIG)], cwd=REPO_ROOT, check=False)
    subprocess.run([sys.executable, str(STATUS_SCRIPT), "reset"], cwd=REPO_ROOT, check=False)

    if args.start_status:
        start_status_server(args.status_port)

    ensure_reference_defaults()
    ensure_whitelist()
    if args.auto_install:
        if args.use_wsl:
            ensure_python_packages_wsl()
            try_install_external_wsl(["STAR", "samtools", "gatk", "cellsnp-lite"])
        else:
            ensure_python_packages()
            try_install_external(["STAR", "samtools", "gatk", "cellsnp-lite"])

    stage_defs = stage_definitions(python_cmd="python3" if args.use_wsl else sys.executable)
    stage_ids = [stage_id for stage_id, _command, _scan_paths in stage_defs]
    if args.from_stage not in stage_ids:
        raise ValueError(f"Unknown from-stage: {args.from_stage}")
    if args.end_stage and args.end_stage not in stage_ids:
        raise ValueError(f"Unknown end-stage: {args.end_stage}")

    stage_runner = run_wsl if args.use_wsl else run
    started = False
    stage_results: dict[str, dict[str, Any]] = {}
    completed_all = True

    for idx, (stage_id, command, scan_paths) in enumerate(stage_defs):
        if stage_id == args.from_stage:
            started = True
        if not started:
            continue

        contract = contract_map.get(stage_id)
        if contract is None:
            raise ValueError(f"Missing stage contract for {stage_id}")

        try:
            preflight = run_preflight(stage_id, contract, command, args.use_wsl, agent_cfg)
            log_status("start", "--stage", stage_id, "--message", "agentic_stage_start")
            execution = run_execution(stage_id, contract, command, stage_runner, agent_cfg)
            if scan_paths:
                log_status("scan", "--stage", stage_id, "--paths", *scan_paths)
            review = run_review(stage_id, contract, scan_paths, agent_cfg)
            report = create_stage_report(stage_id, contract, preflight, execution, review, agent_cfg)
            next_stage_id = stage_defs[idx + 1][0] if idx + 1 < len(stage_defs) else None
            decision = create_main_agent_decision(
                stage_id,
                next_stage_id,
                contract,
                preflight,
                execution,
                review,
                report,
                agent_cfg,
            )
            log_status("finish", "--stage", stage_id, "--message", "agentic_stage_success")
            stage_results[stage_id] = {
                "contract": contract,
                "preflight": preflight,
                "execution": execution,
                "review": review,
                "report": report,
                "decision": decision,
            }
        except Exception as exc:
            completed_all = False
            log_status("error", "--stage", stage_id, "--message", str(exc))
            raise

        if args.end_stage and stage_id == args.end_stage:
            completed_all = stage_id == stage_ids[-1]
            break

    build_final_report(stage_ids, stage_results, agent_cfg, completed_all and bool(stage_results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
