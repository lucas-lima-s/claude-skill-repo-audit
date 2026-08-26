from __future__ import annotations

import re
from urllib.parse import urlparse

from auditlib.context import CheckContext
from auditlib.registry import register
from auditlib.severity import CheckResult, Severity

IMAGE_MD_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
IMAGE_HTML_RE = re.compile(r"<img\b[^>]*\bsrc=[\"\']([^\"\']+)[\"\']", re.IGNORECASE)
SOURCE_SRCSET_RE = re.compile(r"<source\b[^>]*\bsrcset=[\"\']([^\"\']+)[\"\']", re.IGNORECASE)
LINK_MD_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")

BADGE_ALLOWLIST = {
    "img.shields.io",
    "shields.io",
    "github.com",
    "raw.githubusercontent.com",
    "user-images.githubusercontent.com",
    "codecov.io",
}


def _is_external(src: str) -> bool:
    return src.startswith(("http://", "https://"))


def _resolves(ctx: CheckContext, rel_target: str) -> bool:
    target = rel_target.split("#", 1)[0]
    if not target:
        return True
    return ctx.exists(target)


@register("readme_links")
def run(ctx: CheckContext) -> list[CheckResult]:
    text = ctx.read_text("README.md")
    if text is None:
        return []

    results: list[CheckResult] = []

    for lineno, line in enumerate(text.splitlines(), start=1):
        srcs = IMAGE_MD_RE.findall(line) + IMAGE_HTML_RE.findall(line)
        for srcset in SOURCE_SRCSET_RE.findall(line):
            srcs.append(srcset.split(",")[0].strip().split(" ")[0])

        for src in srcs:
            if _is_external(src):
                host = urlparse(src).netloc.lower()
                if host not in BADGE_ALLOWLIST:
                    results.append(
                        CheckResult(
                            check="readme.hotlinked_image",
                            severity=Severity.WARN,
                            message=f"hotlinked image will rot; commit the asset under docs/ instead of {host}",
                            file="README.md",
                            line=lineno,
                            remediation="download the asset and reference it as a relative path under docs/",
                        )
                    )
            elif not _resolves(ctx, src):
                results.append(
                    CheckResult(
                        check="readme.broken_relative_image",
                        severity=Severity.FAIL,
                        message=f"relative image does not resolve: {src}",
                        file="README.md",
                        line=lineno,
                        remediation=f"fix the path or add the missing file at {src}",
                    )
                )

        for target in LINK_MD_RE.findall(line):
            if _is_external(target) or target.startswith("#"):
                continue
            if not _resolves(ctx, target):
                results.append(
                    CheckResult(
                        check="readme.broken_relative_link",
                        severity=Severity.WARN,
                        message=f"relative link does not resolve: {target}",
                        file="README.md",
                        line=lineno,
                        remediation=f"fix the path or add the missing file at {target}",
                    )
                )

    return results
