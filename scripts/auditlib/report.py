from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from auditlib.context import TargetForLayer2
from auditlib.severity import CheckResult, Severity

SEVERITY_ORDER = (Severity.FAIL, Severity.WARN, Severity.INFO, Severity.OK)


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _count_severities(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"ok": 0, "info": 0, "warn": 0, "fail": 0}
    for finding in findings:
        key = finding["severity"].lower()
        if key in counts:
            counts[key] += 1
    return counts


def build_report(
    *,
    tool_version: str,
    target_path: str,
    target_name: str,
    profile_name: str,
    findings_layer1: list[CheckResult],
    targets_for_layer2: list[TargetForLayer2],
    artifact_scorecard: dict[str, int],
    findings_layer2: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    findings_layer1_dicts = [r.to_dict() for r in findings_layer1]
    counts = _count_severities(findings_layer1_dicts)
    gate = "BLOCK" if any(r.severity == Severity.FAIL for r in findings_layer1) else "PASS"

    return {
        "schema_version": 2,
        "tool": "repo-audit",
        "tool_version": tool_version,
        "kind": "repo",
        "generated_at": _now_iso(),
        "target_path": target_path,
        "target_name": target_name,
        "profile": profile_name,
        "gate": gate,
        "scorecard": {
            "present": artifact_scorecard.get("present", 0),
            "total": artifact_scorecard.get("total", 0),
            **counts,
        },
        "findings_layer1": findings_layer1_dicts,
        "targets_for_layer2": [
            {"prompt_id": t.prompt_id, "prompt_file": t.prompt_file, "files": t.files} for t in targets_for_layer2
        ],
        "findings_layer2": findings_layer2 or [],
    }


def build_dashboard(*, tool_version: str, profile_name: str, repo_reports: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {"repos": len(repo_reports), "blocked": 0, "fail": 0, "warn": 0, "info": 0, "ok": 0}
    for report in repo_reports:
        if report.get("gate") == "BLOCK":
            totals["blocked"] += 1
        scorecard = report.get("scorecard", {})
        for key in ("fail", "warn", "info", "ok"):
            totals[key] += scorecard.get(key, 0)

    gate = "BLOCK" if totals["blocked"] > 0 else "PASS"

    return {
        "schema_version": 2,
        "tool": "repo-audit",
        "tool_version": tool_version,
        "kind": "dashboard",
        "generated_at": _now_iso(),
        "profile": profile_name,
        "gate": gate,
        "totals": totals,
        "repos": repo_reports,
    }


def write_report(report: dict[str, Any], json_out: str | None, prefix: str) -> str:
    if json_out:
        path = Path(json_out)
        path.parent.mkdir(parents=True, exist_ok=True)
    else:
        fd, tmp_path = tempfile.mkstemp(prefix=f"{prefix}-", suffix=".json")
        os.close(fd)
        path = Path(tmp_path)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return str(path.resolve())


def render_markdown(report: dict[str, Any]) -> str:
    lines = [f"repo-audit: {report.get('target_name', report.get('kind'))} (profile={report.get('profile')})"]
    scorecard = report.get("scorecard", {})
    if "present" in scorecard:
        lines.append(f"Polish scorecard: {scorecard.get('present', 0)} / {scorecard.get('total', 0)} artifacts present")

    findings = report.get("findings_layer1", []) + report.get("findings_layer2", [])
    by_severity: dict[str, list[dict[str, Any]]] = {sev.value: [] for sev in SEVERITY_ORDER}
    for finding in findings:
        by_severity.setdefault(finding["severity"], []).append(finding)

    for sev in SEVERITY_ORDER:
        for finding in by_severity.get(sev.value, []):
            lines.append(f"[{finding['severity']}] {finding['check']}  {finding['message']}")
            if finding.get("file"):
                location = finding["file"]
                if finding.get("line"):
                    location = f"{location}:{finding['line']}"
                lines.append(f"  -> {location}")
            if finding.get("remediation"):
                lines.append(f"  fix: {finding['remediation']}")

    counts = _count_severities(report.get("findings_layer1", []))
    lines.append(
        f"Summary: {counts['fail']} fail, {counts['warn']} warn, {counts['info']} info, "
        f"{counts['ok']} ok - {report.get('gate')}"
    )
    return "\n".join(lines)


def load_and_validate(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("schema_version") != 2:
        raise SystemExit(2)
    return data
