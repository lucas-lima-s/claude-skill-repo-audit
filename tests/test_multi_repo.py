from __future__ import annotations

from pathlib import Path

from auditlib.report import build_dashboard
from scan import _audit_one


def test_audit_one_missing_repo_is_synthetic_fail(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    report = _audit_one(str(missing), "portfolio", None, True, False)
    assert report["gate"] == "BLOCK"
    checks = [f["check"] for f in report["findings_layer1"]]
    assert checks == ["runner.missing_repo"]


def test_audit_one_clean_fixture_passes(clean_repo: Path) -> None:
    report = _audit_one(str(clean_repo), "portfolio", None, True, False)
    assert report["gate"] == "PASS"
    assert report["scorecard"]["fail"] == 0


def test_audit_one_dirty_fixture_blocks(dirty_repo: Path) -> None:
    report = _audit_one(str(dirty_repo), "portfolio", None, True, False)
    assert report["gate"] == "BLOCK"
    assert report["scorecard"]["fail"] > 0


def test_build_dashboard_totals(clean_repo: Path, dirty_repo: Path) -> None:
    clean_report = _audit_one(str(clean_repo), "portfolio", None, True, False)
    dirty_report = _audit_one(str(dirty_repo), "portfolio", None, True, False)

    dashboard = build_dashboard(
        tool_version="0.1.0", profile_name="portfolio", repo_reports=[clean_report, dirty_report]
    )

    assert dashboard["kind"] == "dashboard"
    assert dashboard["schema_version"] == 2
    assert dashboard["totals"]["repos"] == 2
    assert dashboard["totals"]["blocked"] == 1
    assert dashboard["gate"] == "BLOCK"
    assert len(dashboard["repos"]) == 2
