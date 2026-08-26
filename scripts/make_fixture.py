from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import argparse
import base64
import os
import shutil
import subprocess
from datetime import UTC, datetime, timedelta

TOOL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = TOOL_ROOT / "examples" / "clean_repo"

PORTFOLIO_NAME = "lucas-lima-s"
PORTFOLIO_EMAIL = "106186397+lucas-lima-s@users.noreply.github.com"


def _run_git(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        env=full_env,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr}")


def _copy_template_tree(out_dir: Path) -> None:
    shutil.copytree(TEMPLATE_DIR, out_dir, dirs_exist_ok=True)


def _commit(
    out_dir: Path,
    message: str,
    author_name: str,
    author_email: str,
    when: datetime,
    committer_name: str | None = None,
    committer_email: str | None = None,
    force_paths: list[str] | None = None,
) -> None:
    date_str = when.strftime("%Y-%m-%dT%H:%M:%S")
    env = {
        "GIT_AUTHOR_NAME": author_name,
        "GIT_AUTHOR_EMAIL": author_email,
        "GIT_AUTHOR_DATE": date_str,
        "GIT_COMMITTER_NAME": committer_name or author_name,
        "GIT_COMMITTER_EMAIL": committer_email or author_email,
        "GIT_COMMITTER_DATE": date_str,
    }
    _run_git(["add", "-A"], out_dir)
    if force_paths:
        _run_git(["add", "-f", *force_paths], out_dir)
    _run_git(["-c", "commit.gpgsign=false", "commit", "-m", message], out_dir, env=env)


def build_clean(out_dir: Path) -> None:
    _copy_template_tree(out_dir)
    _run_git(["init", "-b", "main"], out_dir)

    now = datetime.now(UTC)
    _commit(out_dir, "chore: scaffold clean fixture", PORTFOLIO_NAME, PORTFOLIO_EMAIL, now)

    (out_dir / "docs" / "note.md").write_text("# Notes\n\nNothing to see here.\n", encoding="utf-8")
    _commit(out_dir, "docs: add project notes", PORTFOLIO_NAME, PORTFOLIO_EMAIL, now)

    (out_dir / "tests" / "test_extra.py").write_text("def test_extra():\n    assert 1 + 1 == 2\n", encoding="utf-8")
    _commit(out_dir, "test: add extra coverage", PORTFOLIO_NAME, PORTFOLIO_EMAIL, now)


def _planted_key() -> str:
    return "AK" + "IA" + "Q" * 16


def _planted_email() -> str:
    return "dev" + "@" + "acme-corp" + ".example"


def _planted_term() -> str:
    return "acme" + "-corp"


def _high_entropy_token(length: int = 44) -> str:
    token = base64.b64encode(os.urandom(64)).decode("ascii").rstrip("=")
    return token[:length]


def build_dirty(out_dir: Path) -> None:
    _copy_template_tree(out_dir)
    _run_git(["init", "-b", "main"], out_dir)

    readme_path = out_dir / "README.md"
    readme_text = readme_path.read_text(encoding="utf-8")
    readme_text += "\n![broken](docs/missing-image.png)\n![hotlink](https://i.imgur.com/x.png)\n"
    readme_path.write_text(readme_text, encoding="utf-8")

    (out_dir / ".env").write_text(f"SECRET_KEY={_planted_key()}\n", encoding="utf-8")

    (out_dir / "config.py").write_text(f'API_TOKEN = "{_high_entropy_token()}"\n', encoding="utf-8")

    build_bat_lines = [f"echo build step {i}" for i in range(600)]
    (out_dir / "build.bat").write_text("\r\n".join(build_bat_lines) + "\r\n", encoding="utf-8")

    app_py_lines = (["def add(a, b):", "    return a + b", ""] * 10)[:30]
    app_py_path = out_dir / "src" / "app.py"
    app_py_path.parent.mkdir(parents=True, exist_ok=True)
    app_py_path.write_text("\n".join(app_py_lines) + "\n", encoding="utf-8")

    (out_dir / "tests" / "test_fail.py").write_text("def test_fail():\n    assert False\n", encoding="utf-8")

    (out_dir / "ROADMAP.md").write_text("# Roadmap\n\n## Planned\n\n- nothing yet\n", encoding="utf-8")

    term = _planted_term()
    (out_dir / "repo-audit.toml").write_text(f'[denylist]\nterms = ["{term}"]\n', encoding="utf-8")

    now = datetime.now(UTC)
    old = now - timedelta(days=800)
    _commit(
        out_dir,
        "chore: scaffold dirty fixture",
        PORTFOLIO_NAME,
        PORTFOLIO_EMAIL,
        old,
        force_paths=[".env"],
    )

    older = now - timedelta(days=799)
    (out_dir / "docs" / "notes.txt").write_text(f"internal rollout notes: {term}\n", encoding="utf-8")
    _commit(
        out_dir,
        f"chore: {term} rollout notes",
        "Corporate Dev",
        _planted_email(),
        older,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="make_fixture.py", description="Materialize a clean or dirty git fixture.")
    parser.add_argument("--kind", choices=["clean", "dirty"], required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    out_dir = Path(args.out).resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)

    if args.kind == "clean":
        build_clean(out_dir)
    else:
        build_dirty(out_dir)

    print(str(out_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
