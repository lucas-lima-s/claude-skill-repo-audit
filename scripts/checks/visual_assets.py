from __future__ import annotations

import fnmatch
from pathlib import Path

from auditlib.context import CheckContext
from auditlib.registry import register
from auditlib.severity import CheckResult, Severity


def _auto_detected(ctx: CheckContext) -> bool:
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


@register("visual_assets")
def run(ctx: CheckContext) -> list[CheckResult]:
    required = ctx.config.visual.required
    auto = _auto_detected(ctx)
    if not required and not auto:
        return []

    globs = ctx.config.visual.asset_globs
    matched = [
        tracked.replace("\\", "/")
        for tracked in ctx.tracked_files
        if any(fnmatch.fnmatch(tracked.replace("\\", "/"), g) for g in globs)
    ]

    readme = ctx.read_text("README.md") or ""
    referenced = [m for m in matched if m in readme or Path(m).name in readme]

    if referenced:
        return [
            CheckResult(
                check="visual.asset_present",
                severity=Severity.OK,
                message=f"visual asset present and referenced from README: {referenced[0]}",
                file=referenced[0],
            )
        ]

    severity = Severity.FAIL if required else Severity.INFO
    return [
        CheckResult(
            check="visual.asset_present",
            severity=severity,
            message="no visual asset under docs/assets/screenshots is referenced from README.md",
            remediation="add a screenshot or a synthetic, clearly-labelled mockup under docs/ and link it from "
            "README.md; a live capture is not required",
        )
    ]
