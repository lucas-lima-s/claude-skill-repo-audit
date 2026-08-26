from __future__ import annotations

from pathlib import Path

from auditlib.context import CheckContext
from auditlib.registry import register
from auditlib.severity import CheckResult, Severity


def _looks_visual(ctx: CheckContext) -> bool:
    if ctx.exists("index.html"):
        return True
    if any(True for _ in ctx.iter_tracked("*.unity", "*.godot", "*.love")):
        return True
    top_dirs: set[str] = set()
    for tracked in ctx.tracked_files:
        parts = Path(tracked).parts
        if len(parts) > 1:
            top_dirs.add(parts[0].lower())
    return bool(top_dirs & {"game", "ui", "frontend"})


def _predicate_ok(name: str | None, ctx: CheckContext) -> bool:
    if name is None or name == "none":
        return True
    if name == "python_code":
        return any(True for _ in ctx.iter_tracked("*.py"))
    if name == "git_repo":
        return ctx.is_git_repo
    if name == "visual":
        return _looks_visual(ctx)
    return True


def _slug(key: str) -> str:
    return key.lower().replace(" ", "_").replace(".", "_")


@register("artifacts")
def run(ctx: CheckContext) -> list[CheckResult]:
    results: list[CheckResult] = []
    for key, rule in ctx.profile.artifacts.items():
        if not _predicate_ok(rule.requires, ctx):
            continue
        check_id = f"artifacts.{_slug(key)}"
        if ctx.exists(rule.path):
            results.append(CheckResult(check=check_id, severity=Severity.OK, message=f"{key} present", file=rule.path))
        else:
            results.append(
                CheckResult(
                    check=check_id,
                    severity=rule.missing,
                    message=f"{key} is missing",
                    file=rule.path,
                    remediation=f"add {rule.path}",
                )
            )
    return results


def scorecard(results: list[CheckResult]) -> dict[str, int]:
    total = len(results)
    present = sum(1 for r in results if r.severity == Severity.OK)
    return {"present": present, "total": total}
