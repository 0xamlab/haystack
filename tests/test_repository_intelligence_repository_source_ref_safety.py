"""Ref-safety unit tests for repository_intelligence_repository_source.

These cover the taint-disconnection helpers introduced to keep an untrusted
``ref`` out of every git argv (CodeQL py/command-line-injection): shape
validation, ls-remote matching (values returned come from git stdout), and the
stdin-based object-id resolution. Network/clone behaviour is not exercised here;
the pure parsing/validation logic is.
"""
from __future__ import annotations

import pytest

from apps.api_server.services import repository_intelligence_repository_source as rs
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)

_OID = "0123456789abcdef0123456789abcdef01234567"
_OID2 = "89abcdef0123456789abcdef0123456789abcdef"
_LISTING = (
    f"{_OID}\trefs/heads/main\n"
    f"{_OID2}\trefs/heads/feature/x-1\n"
    f"{_OID}\tHEAD\n"
    f"{_OID2}\trefs/tags/v1.2.3\n"
)


@pytest.mark.parametrize("bad", ["--upload-pack=x", "-x", "a;rm -rf /", "../etc", "a b", "v1..2", "a|b", "a$b"])
def test_validate_ref_shape_rejects_dangerous(bad: str) -> None:
    with pytest.raises(RepositoryIntelligenceError) as exc:
        rs._validate_ref_shape(bad)
    assert exc.value.status_code == 422


@pytest.mark.parametrize("good", ["main", "feature/x-1", "v1.2.3", "release/2024.01", _OID])
def test_validate_ref_shape_allows_legitimate(good: str) -> None:
    rs._validate_ref_shape(good)  # must not raise


def test_match_remote_ref_branch_returns_stdout_short_name() -> None:
    kind, value = rs._match_remote_ref(_LISTING, "main")
    assert (kind, value) == ("branch", "main")
    kind, value = rs._match_remote_ref(_LISTING, "feature/x-1")
    assert (kind, value) == ("branch", "feature/x-1")


def test_match_remote_ref_tag() -> None:
    assert rs._match_remote_ref(_LISTING, "v1.2.3") == ("tag", "v1.2.3")


def test_match_remote_ref_sha_tip() -> None:
    # A ref equal to an advertised tip sha resolves to that (stdout) sha.
    assert rs._match_remote_ref(_LISTING, _OID2) == ("sha", _OID2)


def test_match_remote_ref_unknown_raises() -> None:
    with pytest.raises(RepositoryIntelligenceError) as exc:
        rs._match_remote_ref(_LISTING, "nope-not-here")
    assert exc.value.status_code == 422


def test_match_remote_ref_validates_shape_first() -> None:
    with pytest.raises(RepositoryIntelligenceError):
        rs._match_remote_ref(_LISTING, "--upload-pack=evil")


def test_resolve_git_ref_parses_oid_from_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    # cat-file --batch-check returns "<oid> <type> <size>"; we take the oid only.
    monkeypatch.setattr(rs, "_git_command", lambda *a, **k: f"{_OID} commit 234")
    assert rs._resolve_git_ref(__import__("pathlib").Path("/x"), "main") == _OID


def test_resolve_git_ref_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rs, "_git_command", lambda *a, **k: "main missing")
    with pytest.raises(RepositoryIntelligenceError) as exc:
        rs._resolve_git_ref(__import__("pathlib").Path("/x"), "main")
    assert exc.value.status_code == 422


def test_no_ref_token_reaches_git_argv() -> None:
    """Invariant: the module never passes a bare ``ref`` into a git argv list."""
    import inspect
    import re as _re

    src = inspect.getsource(rs.resolved_repository_source)
    # No argv list element is the bare `ref` variable; only resolved oids / stdout
    # short-names / constants are allowed. (Matches e.g. `"git", ... ref` patterns.)
    assert not _re.search(r'"git"[^\]]*,\s*ref\b', src), "ref must never appear in a git argv"
