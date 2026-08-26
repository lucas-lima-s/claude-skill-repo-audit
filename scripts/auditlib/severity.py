from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    OK = "OK"
    INFO = "INFO"
    WARN = "WARN"
    FAIL = "FAIL"

    @property
    def rank(self) -> int:
        return {"OK": 0, "INFO": 1, "WARN": 2, "FAIL": 3}[self.value]


@dataclass
class CheckResult:
    check: str
    severity: Severity
    message: str
    file: str | None = None
    line: int | None = None
    remediation: str | None = None
    source: str = "layer1"
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "severity": self.severity.value,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "remediation": self.remediation,
            "source": self.source,
            "evidence": self.evidence,
        }


def cap_severity(sev: Severity, ceiling: Severity) -> Severity:
    return sev if sev.rank <= ceiling.rank else ceiling


def worst(results: list[CheckResult]) -> Severity:
    worst_sev = Severity.OK
    for r in results:
        if r.severity.rank > worst_sev.rank:
            worst_sev = r.severity
    return worst_sev
