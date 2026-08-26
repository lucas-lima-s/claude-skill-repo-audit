from __future__ import annotations

import re

from auditlib import gitutil
from auditlib.context import CheckContext
from auditlib.registry import register
from auditlib.severity import CheckResult, Severity


def _email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower() if "@" in email else ""


def _collect_identities(
    identities: list[tuple[str, str, str, str]],
) -> tuple[dict[str, int], dict[str, set[str]]]:
    counts: dict[str, int] = {}
    names: dict[str, set[str]] = {}
    for author_email, author_name, committer_email, committer_name in identities:
        per_commit = {author_email: author_name, committer_email: committer_name}
        for email, name in per_commit.items():
            if not email:
                continue
            counts[email] = counts.get(email, 0) + 1
            names.setdefault(email, set()).add(name)
    return counts, names


def _passes_identity(email: str, config) -> bool:
    domain = _email_domain(email)
    denylisted_domains = {d.lower() for d in config.denylist.email_domains}
    if domain in denylisted_domains:
        return False
    if email in config.identity.allowed_author_emails:
        return True
    if domain.endswith("users.noreply.github.com"):
        return True
    public_domains = {d.lower() for d in config.denylist.public_email_domains}
    return domain in public_domains


def _redact_term(term: str) -> str:
    return term[:3] + "..." if len(term) > 3 else term


@register("git_history")
def run(ctx: CheckContext) -> list[CheckResult]:
    if not ctx.is_git_repo:
        return [
            CheckResult(
                check="history.not_a_repo",
                severity=Severity.WARN,
                message="target is not a git repository; history checks were skipped",
                remediation="run `git init` and commit the work under the portfolio identity",
            )
        ]

    results: list[CheckResult] = []
    max_commits = ctx.config.history.max_commits

    identities = gitutil.log_identities(ctx.repo_path, max_commits=max_commits)
    counts, names = _collect_identities(identities)
    for email, count in sorted(counts.items()):
        if _passes_identity(email, ctx.config):
            continue
        results.append(
            CheckResult(
                check="history.author_identity",
                severity=Severity.FAIL,
                message=f"non-portfolio author identity '{email}' appears in {count} commit(s)",
                remediation="recreate the history with the portfolio identity, or rewrite it with "
                "`git filter-repo --mailmap`",
                evidence={"email": email, "names": sorted(names.get(email, []))},
            )
        )

    terms = ctx.config.denylist.terms
    regexes = ctx.config.denylist.regexes
    soft_regexes = ctx.config.denylist.soft_regexes

    messages = gitutil.log_messages(ctx.repo_path, max_commits=max_commits)
    for message in messages:
        lowered = message.lower()
        for term in terms:
            if term.lower() in lowered:
                results.append(
                    CheckResult(
                        check="history.commit_message",
                        severity=Severity.FAIL,
                        message=f"a denylisted term ({_redact_term(term)}) appears in a commit message",
                        remediation="the history must be rewritten or recreated; a denylisted term in a commit "
                        "message cannot be edited after the fact without rewriting history",
                    )
                )
        for pattern in regexes:
            if re.search(pattern, message):
                results.append(
                    CheckResult(
                        check="history.commit_message",
                        severity=Severity.FAIL,
                        message="a denylisted pattern matches a commit message",
                        remediation="the history must be rewritten or recreated",
                    )
                )
        for pattern in soft_regexes:
            if re.search(pattern, message):
                results.append(
                    CheckResult(
                        check="history.denylist_term",
                        severity=Severity.INFO,
                        message="a soft denylist pattern matches a commit message",
                        remediation="confirm this is not an internal ticket reference before publishing",
                    )
                )

    ref_output = "\n".join(gitutil.refs(ctx.repo_path))
    lowered_refs = ref_output.lower()
    for term in terms:
        if term.lower() in lowered_refs:
            results.append(
                CheckResult(
                    check="history.ref_name",
                    severity=Severity.WARN,
                    message=f"a denylisted term ({_redact_term(term)}) appears in a ref name",
                    remediation="rename or delete the branch/tag before publishing",
                )
            )
    for pattern in regexes:
        if re.search(pattern, ref_output, re.IGNORECASE | re.MULTILINE):
            results.append(
                CheckResult(
                    check="history.ref_name",
                    severity=Severity.WARN,
                    message="a denylisted pattern matches a ref name",
                    remediation="rename or delete the branch/tag before publishing",
                )
            )

    commit_count = gitutil.commit_count(ctx.repo_path)
    if commit_count == 1:
        results.append(
            CheckResult(
                check="history.single_commit",
                severity=Severity.INFO,
                message="a single-commit history reads as a code dump",
                remediation="build a readable sequence of Conventional Commits before publishing",
            )
        )

    return results
