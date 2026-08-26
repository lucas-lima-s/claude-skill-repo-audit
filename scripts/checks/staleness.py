from __future__ import annotations

from datetime import UTC, datetime

from auditlib import gitutil
from auditlib.context import CheckContext
from auditlib.registry import register
from auditlib.severity import CheckResult, Severity


@register("staleness")
def run(ctx: CheckContext) -> list[CheckResult]:
    if not ctx.is_git_repo:
        return []

    iso = gitutil.last_commit_iso(ctx.repo_path)
    if not iso:
        return []

    last_commit = datetime.fromisoformat(iso)
    now = datetime.now(UTC)
    age_days = max(0, int((now - last_commit).total_seconds() // 86400))

    fail_days = ctx.config.staleness.fail_days
    warn_days = ctx.config.staleness.warn_days

    evidence = {"last_commit_iso": iso, "age_days": age_days}

    if fail_days and age_days >= fail_days:
        severity = Severity.FAIL
    elif age_days >= warn_days:
        severity = Severity.WARN
    else:
        severity = Severity.OK

    message = f"last commit was {age_days} day(s) ago"
    remediation = None if severity == Severity.OK else "make a real commit, or archive the repo if it is finished"

    return [
        CheckResult(
            check="staleness.last_commit",
            severity=severity,
            message=message,
            remediation=remediation,
            evidence=evidence,
        )
    ]
