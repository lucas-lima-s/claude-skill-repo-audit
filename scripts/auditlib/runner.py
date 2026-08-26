from __future__ import annotations

from pathlib import Path

from auditlib import registry
from auditlib.config import Profile
from auditlib.context import CheckContext, TargetForLayer2
from auditlib.severity import CheckResult, Severity, cap_severity


def run_layer1(ctx: CheckContext, profile: Profile) -> list[CheckResult]:
    results: list[CheckResult] = []
    for check_id in profile.enabled_checks:
        spec = registry.CHECKS.get(check_id)
        if spec is None:
            results.append(
                CheckResult(
                    check=f"{check_id}.unknown_check",
                    severity=Severity.WARN,
                    message=f"enabled check '{check_id}' is not registered",
                )
            )
            continue
        try:
            check_results = spec.run(ctx)
        except Exception as exc:
            results.append(
                CheckResult(
                    check=f"{check_id}.internal_error",
                    severity=Severity.WARN,
                    message=f"check '{check_id}' raised {type(exc).__name__}: {exc}",
                )
            )
            continue
        for result in check_results:
            result = _apply_policy(result, profile)
            results.append(result)
    return results


def _apply_policy(result: CheckResult, profile: Profile) -> CheckResult:
    severity = result.severity
    if profile.downgrade_warn_to_info and severity == Severity.WARN:
        severity = Severity.INFO
    ceiling_name = profile.overrides.get(result.check)
    if ceiling_name is not None:
        severity = cap_severity(severity, Severity(ceiling_name))
    if severity != result.severity:
        result.severity = severity
    return result


def build_layer2_targets(
    ctx: CheckContext,
    profile: Profile,
    prompt_dirs: list[Path],
) -> list[TargetForLayer2]:
    targets: list[TargetForLayer2] = []
    for prompt_id in profile.layer2_prompts:
        prompt_file = _resolve_prompt_file(prompt_dirs, prompt_id)
        if prompt_file is None:
            continue
        inputs = _parse_inputs_header(prompt_file)
        files = [rel for rel in inputs if ctx.exists(rel)]
        targets.append(
            TargetForLayer2(
                prompt_id=prompt_id,
                prompt_file=str(prompt_file.resolve()),
                files=[str(ctx.path(rel).resolve()) for rel in files],
            )
        )
    return targets


def _resolve_prompt_file(prompt_dirs: list[Path], prompt_id: str) -> Path | None:
    for directory in prompt_dirs:
        candidate = directory / f"{prompt_id}.md"
        if candidate.exists():
            return candidate
    return None


def _parse_inputs_header(prompt_file: Path) -> list[str]:
    text = prompt_file.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("<!-- inputs:") and stripped.endswith("-->"):
            body = stripped[len("<!-- inputs:") : -len("-->")]
            return [item.strip() for item in body.split(",") if item.strip()]
    return []
