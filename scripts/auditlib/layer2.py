from __future__ import annotations

from typing import Any

from auditlib.severity import Severity

REQUIRED_KEYS = {"check", "severity", "message"}


def merge_layer2(report: dict[str, Any], findings: list[dict[str, Any]]) -> dict[str, Any]:
    merged: list[dict[str, Any]] = []
    for finding in findings:
        missing = REQUIRED_KEYS - finding.keys()
        if missing:
            raise ValueError(f"layer2 finding missing required keys {sorted(missing)}: {finding}")

        original_severity = Severity(finding["severity"])
        severity = original_severity if original_severity != Severity.FAIL else Severity.WARN
        message = finding["message"]
        if original_severity == Severity.FAIL:
            message = f"{message} (demoted from FAIL: layer 2 findings are capped at WARN)"

        merged.append(
            {
                "check": finding["check"],
                "severity": severity.value,
                "message": message,
                "file": finding.get("file"),
                "line": finding.get("line"),
                "remediation": finding.get("remediation"),
                "source": finding.get("source", "layer2"),
                "evidence": finding.get("evidence", {}),
            }
        )

    updated = dict(report)
    updated["findings_layer2"] = list(report.get("findings_layer2", [])) + merged
    updated["gate"] = "BLOCK" if any(f["severity"] == "FAIL" for f in report.get("findings_layer1", [])) else "PASS"
    return updated
