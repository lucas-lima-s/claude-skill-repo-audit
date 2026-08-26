from __future__ import annotations

import ast
from pathlib import Path

from auditlib.context import CheckContext
from auditlib.registry import register
from auditlib.severity import CheckResult, Severity

DEPRECATED_TYPING = {"List", "Dict", "Tuple", "Set", "FrozenSet", "Type", "Optional", "Union"}
EXCLUDED_PREFIXES = ("examples/", "tests/fixtures/")


def _is_excluded(rel: str) -> bool:
    normalized = rel.replace("\\", "/")
    return any(normalized.startswith(prefix) for prefix in EXCLUDED_PREFIXES)


def _has_future_annotations(tree: ast.Module) -> bool:
    for node in tree.body:
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "__future__"
            and any(alias.name == "annotations" for alias in node.names)
        ):
            return True
    return False


@register("python_style")
def run(ctx: CheckContext) -> list[CheckResult]:
    results: list[CheckResult] = []
    base = Path(ctx.repo_path)

    for path in ctx.iter_tracked("*.py"):
        rel = str(path.relative_to(base)).replace("\\", "/")
        if _is_excluded(rel):
            continue

        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(text, filename=rel)
        except SyntaxError as exc:
            results.append(
                CheckResult(
                    check="python_style.parse",
                    severity=Severity.WARN,
                    message=f"SyntaxError: {exc.msg}",
                    file=rel,
                    line=exc.lineno,
                    remediation="fix the syntax error",
                )
            )
            continue

        if not _has_future_annotations(tree):
            severity = Severity.INFO if rel.startswith("tests/") else Severity.WARN
            results.append(
                CheckResult(
                    check="python_style.future",
                    severity=severity,
                    message="missing 'from __future__ import annotations'",
                    file=rel,
                    line=1,
                    remediation="add 'from __future__ import annotations' as the module's first statement",
                )
            )

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "typing":
                deprecated = sorted(alias.name for alias in node.names if alias.name in DEPRECATED_TYPING)
                if deprecated:
                    results.append(
                        CheckResult(
                            check="python_style.typing_aliases",
                            severity=Severity.WARN,
                            message=f"imports deprecated typing aliases: {', '.join(deprecated)}",
                            file=rel,
                            line=node.lineno,
                            remediation="use builtin generics (list, dict, tuple, set) and 'X | None' / 'X | Y'",
                        )
                    )

    return results
