from __future__ import annotations

import base64
from dataclasses import replace

from auditlib.privacy import collapse_encoded_paths, concatenated_strings, identity_blobs
from auditlib.severity import Severity
from checks import content_denylist


def test_collapse_encoded_paths_turns_regex_class_into_slash() -> None:
    slash_class = "[" + ("\\" * 2) + "/]+"
    line = 'pattern = r"C:' + slash_class + "Users" + slash_class + 'someone"'
    collapsed = collapse_encoded_paths(line)
    assert "c:/users/someone" in collapsed


def test_concatenated_strings_joins_plus_and_pattern_helper() -> None:
    plus_line = '"wibble" + "zot"'
    helper_line = '_pattern("wibble", "zot")'
    assert "wibblezot" in concatenated_strings(plus_line)
    assert "wibblezot" in concatenated_strings(helper_line)


def test_identity_blobs_decode_base64_payload() -> None:
    token = base64.b64encode(b"wibblezot-extra-padding!!").decode()
    line = f'payload = "{token}"'
    assert "wibblezot-extra-padding!!" in identity_blobs(line)


def test_denylist_reconstructed_from_split_literals(tmp_path, git_repo_factory, ctx_factory) -> None:
    term = "wibble" + "zot"
    repo = git_repo_factory(
        tmp_path / "repo",
        {"tests/test_hygiene.py": '_pattern("wibble", "zot")\n'},
    )
    ctx = ctx_factory(repo)
    ctx.config.denylist = replace(ctx.config.denylist, terms=(term,), regexes=())
    results = content_denylist.run(ctx)
    reconstructed = [r for r in results if r.check == "content.denylist_reconstructed"]
    assert reconstructed
    assert all(term not in r.message for r in reconstructed)


def test_denylist_contiguous_term_still_fails(tmp_path, git_repo_factory, ctx_factory) -> None:
    term = "wibble" + "zot"
    repo = git_repo_factory(tmp_path / "repo", {"README.md": f"do not mention {term} here\n"})
    ctx = ctx_factory(repo)
    ctx.config.denylist = replace(ctx.config.denylist, terms=(term,), regexes=())
    results = content_denylist.run(ctx)
    assert any(r.check == "content.denylist_term" and r.severity == Severity.FAIL for r in results)
