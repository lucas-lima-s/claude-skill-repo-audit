from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from auditlib.context import TargetForLayer2
from auditlib.layer2 import merge_layer2
from auditlib.report import build_dashboard, build_report, load_and_validate, render_markdown, write_report
from auditlib.severity import CheckResult, Severity


def _sample_findings() -> list[CheckResult]:
    return [
        CheckResult(check="artifacts.readme_md", severity=Severity.OK, message="README.md present", file="README.md"),
        CheckResult(
            check="secrets.pattern", severity=Severity.FAIL, message="possible secret", file="config.py", line=3
        ),
        CheckResult(check="gitignore.coverage", severity=Severity.WARN, message="missing .env"),
    ]


def test_build_report_schema_v2_shape(tmp_path: Path) -> None:
    report = build_report(
        tool_version="0.1.0",
        target_path=str(tmp_path),
        target_name=tmp_path.name,
        profile_name="portfolio",
        findings_layer1=_sample_findings(),
        targets_for_layer2=[TargetForLayer2(prompt_id="readme_quality", prompt_file="/x/readme_quality.md", files=[])],
        artifact_scorecard={"present": 1, "total": 1},
    )
    assert report["schema_version"] == 2
    assert report["kind"] == "repo"
    assert report["tool"] == "repo-audit"
    assert report["gate"] == "BLOCK"
    assert report["scorecard"]["fail"] == 1
    assert report["scorecard"]["warn"] == 1
    assert report["scorecard"]["ok"] == 1
    assert report["findings_layer2"] == []
    assert report["targets_for_layer2"][0]["prompt_id"] == "readme_quality"


def test_build_report_pass_gate_when_no_fail(tmp_path: Path) -> None:
    findings = [CheckResult(check="a", severity=Severity.WARN, message="m")]
    report = build_report(
        tool_version="0.1.0",
        target_path=str(tmp_path),
        target_name=tmp_path.name,
        profile_name="public",
        findings_layer1=findings,
        targets_for_layer2=[],
        artifact_scorecard={"present": 0, "total": 0},
    )
    assert report["gate"] == "PASS"


def test_build_dashboard_gate_block_when_any_repo_blocked() -> None:
    pass_report = {"gate": "PASS", "scorecard": {"fail": 0, "warn": 1, "info": 0, "ok": 5}}
    block_report = {"gate": "BLOCK", "scorecard": {"fail": 2, "warn": 0, "info": 0, "ok": 3}}
    dashboard = build_dashboard(
        tool_version="0.1.0", profile_name="portfolio", repo_reports=[pass_report, block_report]
    )
    assert dashboard["kind"] == "dashboard"
    assert dashboard["gate"] == "BLOCK"
    assert dashboard["totals"] == {"repos": 2, "blocked": 1, "fail": 2, "warn": 1, "info": 0, "ok": 8}


def test_write_report_and_load_and_validate_round_trip(tmp_path: Path) -> None:
    report = build_report(
        tool_version="0.1.0",
        target_path=str(tmp_path),
        target_name=tmp_path.name,
        profile_name="portfolio",
        findings_layer1=[],
        targets_for_layer2=[],
        artifact_scorecard={"present": 0, "total": 0},
    )
    out_path = write_report(report, str(tmp_path / "out.json"), prefix="repo-audit")
    assert Path(out_path).exists()
    loaded = load_and_validate(out_path)
    assert loaded["gate"] == "PASS"


def test_load_and_validate_rejects_wrong_schema_version(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    with pytest.raises(SystemExit) as exc_info:
        load_and_validate(str(path))
    assert exc_info.value.code == 2


def test_render_markdown_contains_gate_and_findings(tmp_path: Path) -> None:
    report = build_report(
        tool_version="0.1.0",
        target_path=str(tmp_path),
        target_name="my-repo",
        profile_name="portfolio",
        findings_layer1=_sample_findings(),
        targets_for_layer2=[],
        artifact_scorecard={"present": 1, "total": 1},
    )
    markdown = render_markdown(report)
    assert "my-repo" in markdown
    assert "BLOCK" in markdown
    assert "[FAIL] secrets.pattern" in markdown
    assert "Summary:" in markdown


def test_merge_layer2_caps_fail_at_warn() -> None:
    report = {"findings_layer1": [], "findings_layer2": []}
    finding = {
        "source": "layer2",
        "check": "readme_quality",
        "severity": "FAIL",
        "message": "x",
        "file": None,
        "line": None,
    }
    out = merge_layer2(report, [finding])
    assert out["findings_layer2"][0]["severity"] == "WARN"
    assert out["gate"] == "PASS"


def test_merge_layer2_missing_required_key_raises() -> None:
    with pytest.raises(ValueError, match="missing required keys"):
        merge_layer2({"findings_layer1": [], "findings_layer2": []}, [{"check": "x", "severity": "WARN"}])


def test_merge_layer2_gate_still_reflects_layer1_fail() -> None:
    report = {
        "findings_layer1": [{"check": "secrets.pattern", "severity": "FAIL"}],
        "findings_layer2": [],
    }
    out = merge_layer2(report, [])
    assert out["gate"] == "BLOCK"


def test_self_audit_dogfood_passes(repo_root: Path) -> None:
    argv = [
        sys.executable,
        str(repo_root / "scripts" / "audit.py"),
        str(repo_root),
        "--profile",
        "portfolio",
        "--offline",
        "--no-run-tests",
    ]
    proc = subprocess.run(argv, cwd=repo_root, capture_output=True, text=True, check=False)
    last_line = proc.stdout.strip().splitlines()[-1]
    assert last_line.startswith("JSON_PATH=")
    json_path = last_line.split("=", 1)[1]
    report = json.loads(Path(json_path).read_text(encoding="utf-8"))
    fails = [f for f in report["findings_layer1"] if f["severity"] == "FAIL"]
    assert fails == [], f"self-audit should have zero FAIL findings, got: {fails}"
    assert report["gate"] == "PASS"
    assert proc.returncode == 0
