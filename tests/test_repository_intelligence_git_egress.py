"""B10: repository git-transport egress must be fail-closed.

B10 routed the HTTP/SDK egress (LLM chokepoint, PR/MR create, control-plane, S3) through the
egress guard, but the git-protocol subprocesses — ``git ls-remote``/``clone``/``fetch`` during
ingestion and the ``git push`` of the apply REMOTE_PR path — reached the customer-configured git
host with NO guard. These tests pin the fix: the guard runs BEFORE any git subprocess opens a
socket, and the policy/audit destination is the cleartext repository_url host (never the
token-bearing auth URL).
"""
from __future__ import annotations

import inspect
import uuid
from types import SimpleNamespace

import pytest

from apps.api_server.config import get_settings
from apps.api_server.services import repository_intelligence_execution_workflow as ew
from apps.api_server.services import repository_intelligence_repository_source as rs
from apps.api_server.services.egress_guard import EgressPolicyDeniedError

_REPO_URL = "https://github.example.com/acme/widget.git"
_HOST = "github.example.com"
_TOKEN = "ghs-supersecret-token"
_OID = "0123456789abcdef0123456789abcdef01234567"


def _connector() -> SimpleNamespace:
    return SimpleNamespace(
        org_id=uuid.uuid4(),
        id=uuid.uuid4(),
        connector_type=SimpleNamespace(value="github_repo"),
    )


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _noop_egress_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    # The egress audit ledger is DB-bound; keep these unit tests hermetic (no session/FK).
    async def _noop(**_kwargs: object) -> None:
        return None

    monkeypatch.setattr(
        "apps.api_server.services.egress_guard.record_service_egress_event", _noop
    )


def test_clone_egress_denied_before_any_git_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "")
    get_settings.cache_clear()

    def _git_must_not_run(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("git subprocess ran despite egress being denied")

    monkeypatch.setattr(rs, "_git_command", _git_must_not_run)

    config = {"repository_url": _REPO_URL, "access_token": _TOKEN}
    with pytest.raises(EgressPolicyDeniedError) as exc:
        with rs.resolved_repository_source(connector=_connector(), config=config, ref="main"):
            pass
    # Denied on the dedicated git-clone surface, before auth_url is even constructed.
    assert exc.value.decision.surface == "repository_git_clone"


def test_clone_egress_allows_allowlisted_host_and_excludes_token_from_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", _HOST)
    get_settings.cache_clear()

    seen: dict[str, object] = {}
    real_enforce = rs.enforce_connector_destination

    def _spy(destination: str, **kwargs: object) -> object:
        seen["destination"] = destination
        seen["surface"] = kwargs.get("surface")
        return real_enforce(destination, **kwargs)

    monkeypatch.setattr(rs, "enforce_connector_destination", _spy)

    git_calls: list[list[str]] = []

    def _fake_git(args: list[str], **_kwargs: object) -> str:
        git_calls.append(list(args))
        return _OID if args[:2] == ["git", "rev-parse"] else ""

    monkeypatch.setattr(rs, "_git_command", _fake_git)

    config = {"repository_url": _REPO_URL, "access_token": _TOKEN}
    with rs.resolved_repository_source(connector=_connector(), config=config, ref=None) as src:
        assert src.repository_url == _REPO_URL

    # The guard saw the cleartext host only — no token, no scheme, no path.
    assert seen["destination"] == _HOST
    assert _TOKEN not in str(seen["destination"])
    assert seen["surface"] == "repository_git_clone"
    # ...yet the actual git clone still authenticated with the token-bearing URL.
    clone = next(c for c in git_calls if c[:2] == ["git", "clone"])
    assert any(_TOKEN in part for part in clone), "clone must still authenticate with the token"


def test_apply_remote_pr_push_is_egress_guarded_before_the_push() -> None:
    """Structural guarantee for the apply REMOTE_PR push (mirrors the ref-safety inspect test):
    the enforce_connector_destination for repository_git_push must precede the push git argv."""
    src = inspect.getsource(ew)
    push_pos = src.index('"push", push_url')
    guard_pos = src.index('surface="repository_git_push"')
    assert guard_pos < push_pos, "the git push must be egress-guarded before it runs"
