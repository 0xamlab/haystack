"""GitHub App auth for the orchestrator: the zero-secret path, and every way it must fail safe.

WHY. One static GITHUB_CI_TOKEN carries this orchestrator's whole GitHub surface -- org repo
list, then actions/runs plus runs/{id}/jobs for each of 25 repos every reconcile cycle, paginated
runner listings, registration deletes -- AND every worker's gist create/flush and
registration-token fetches. Measured live on a worker at 2026-09-16T22:50:42Z:

    HTTPError 403 {"message": "API rate limit exceeded for user ID 79715912. ..."}

5000 core calls/hr is not enough for that surface, and it cost more than telemetry: a 403 on the
registration-token POST yields an empty token, config.sh fails, and the worker powers off
unregistered. An App installation token gets its OWN budget, so moving the orchestrator's calls
onto one removes the largest consumer from the shared pool.

WHAT THESE TESTS ARE MOSTLY ABOUT is the failure modes, because the risk here is not that App
auth fails to work -- it is that App auth breaks the plane. This file is deployed as a single
copy by `install -m 600` and executed by the distro /usr/bin/python3 under systemd, so a
top-level `import jwt` against a box without PyJWT is not a degraded feature, it is a
crash-looping service and zero provisioning. Hence:

  * the import is lazy and defensive, and its absence is LOGGED rather than silent;
  * every unusable-App state -- unconfigured, no PyJWT, unreadable key, failed mint, App not
    installed on the org -- falls back to GITHUB_CI_TOKEN;
  * a TRANSIENT mint failure cools down and recovers, while a permanent one (bad key file)
    disables for the process lifetime and says so once;
  * workers keep the static token, because the gist sink needs the `gist` OAuth scope that an
    installation token cannot carry. Migrating them is a separate step with a separate plan.

The RS256 signing itself is tested end to end against a real generated key, not mocked: a JWT
that does not verify against its own public key would fail in production with a 401 from GitHub
and nothing on ci-orch explaining why.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import time
import urllib.error
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOL = REPO_ROOT / "infra" / "ci" / "az_orchestrator.py"
_CLOUD_INIT = REPO_ROOT / "infra" / "ci" / "orchestrator-cloud-init.yaml"

_APP_ID = "123456"
_STATIC = "static-ci-token-value"


def _load(monkeypatch, *, app_id="", key_path="", static=_STATIC, org="thyn-ai"):
    """Import the module fresh, with env set BEFORE import.

    GITHUB_APP_ID / GITHUB_APP_PRIVATE_KEY_PATH are read at module scope, so a test that wants
    them configured has to set them before exec_module rather than patching afterwards -- and
    reading them at import is itself the behaviour under test (it is what makes an unset App
    inert rather than merely unused).
    """
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "00000000-0000-0000-0000-000000000000")
    monkeypatch.setenv("AZURE_TENANT_ID", "00000000-0000-0000-0000-000000000000")
    monkeypatch.setenv("GITHUB_CI_TOKEN", static)
    monkeypatch.setenv("GITHUB_APP_ID", app_id)
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY_PATH", key_path)
    monkeypatch.setenv("GITHUB_ORG", org)
    spec = importlib.util.spec_from_file_location(
        f"az_orch_app_auth_{abs(hash((app_id, key_path, org)))}", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    with patch("os.makedirs"):
        spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "log", lambda m: mod._test_logs.append(m))
    mod._test_logs = []
    return mod


# --------------------------------------------------------------------- inert until configured


def test_the_app_path_is_inert_when_nothing_is_configured(monkeypatch) -> None:
    """THE load-bearing safety property.

    Deploying this file to a box whose /etc/az-orchestrator.env has no GITHUB_APP_* must change
    nothing at all: same token, same calls, no new failure mode. Anything else would mean the
    zero-secret work could break a working plane by being merged.
    """
    mod = _load(monkeypatch)
    assert mod.app_configured() is False
    assert mod.app_enabled() is False
    assert mod.github_token() == _STATIC
    assert mod._test_logs == [], mod._test_logs


def test_a_half_configured_app_is_still_inert(monkeypatch, tmp_path) -> None:
    """An id with no key (or a key with no id) is an operator mid-setup, not a broken App.
    Guessing here would mean attempting a mint that cannot succeed."""
    key = tmp_path / "key.pem"
    key.write_text("not-a-key")
    for kwargs in ({"app_id": _APP_ID}, {"key_path": str(key)}):
        mod = _load(monkeypatch, **kwargs)
        assert mod.app_configured() is False, kwargs
        assert mod.app_enabled() is False, kwargs
        assert mod.github_token() == _STATIC


def test_no_module_scope_jwt_import(monkeypatch) -> None:
    """The crash-loop guard, pinned at the source level.

    A top-level `import jwt` would raise ImportError while systemd is starting the unit, so the
    service would restart forever and provisioning would be zero -- the whole plane down because
    of an optional feature. The import has to stay inside _load_pyjwt().
    """
    src = _TOOL.read_text()
    head = src[:src.index("def log(")]  # imports + constants, before any function body
    assert "import jwt" not in head, (
        "jwt is imported at module scope; move it into _load_pyjwt() or a box without PyJWT "
        "crash-loops the orchestrator"
    )
    assert "except ImportError" in src, "the jwt import is not defensive"


def test_a_missing_pyjwt_falls_back_and_says_so_once(monkeypatch) -> None:
    """Degrade, and put the reason in the journal.

    Silent fallback is how the gist sink stayed dead for weeks (#1002): the feature did not work
    and nothing said so. Here the operator gets one line naming the missing dependency AND the
    file to fix -- and only one line, not one per call.
    """
    key = "/etc/az-orchestrator/app-key.pem"
    mod = _load(monkeypatch, app_id=_APP_ID, key_path=key)
    monkeypatch.setattr(mod, "_pyjwt_checked", True)
    monkeypatch.setattr(mod, "_pyjwt", None)  # simulate ImportError having already happened
    assert mod.app_enabled() is False
    assert mod.github_token() == _STATIC

    mod2 = _load(monkeypatch, app_id=_APP_ID, key_path=key)
    import builtins
    real_import = builtins.__import__

    def no_jwt(name, *a, **k):
        if name == "jwt":
            raise ImportError("No module named 'jwt'")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_jwt)
    assert mod2._load_pyjwt() is None
    assert mod2.app_enabled() is False
    assert mod2.github_token() == _STATIC
    notes = [l for l in mod2._test_logs if "PyJWT is NOT importable" in l]
    assert len(notes) == 1, mod2._test_logs
    assert "deploy_orchestrator.sh" in notes[0], notes[0]
    # and repeated calls must not repeat the log
    mod2.github_token()
    mod2.github_token()
    assert len([l for l in mod2._test_logs if "PyJWT" in l]) == 1, mod2._test_logs


def test_the_deploy_declares_the_dependencies_it_needs() -> None:
    """PyJWT being present on ci-orch today is an accident of that box's history, not a
    guarantee. Declaring it is what makes the zero-secret path reachable on a REBUILT box instead
    of silently inert -- and python3-yaml is declared alongside because `import yaml` at module
    scope has the same undeclared-dependency problem, only fatal rather than degrading."""
    import yaml

    doc = yaml.safe_load(_CLOUD_INIT.read_text())
    assert "python3-jwt" in doc["packages"], doc["packages"]
    assert "python3-yaml" in doc["packages"], doc["packages"]


# ----------------------------------------------------------------------- real RS256 round trip


def _rsa_key(tmp_path):
    """A real RSA key pair, so the JWT is actually signed and actually verified."""
    jwt_mod = pytest.importorskip("jwt")
    crypto = pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pub = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    path = tmp_path / "app-key.pem"
    path.write_text(priv)
    path.chmod(0o600)
    return jwt_mod, path, pub


def _stub_github(mod, monkeypatch, *, installations=None, token="ghs_MINTED", expires_in=3600,
                 clock=None):
    """Replace _gh_raw with a recorder that answers the two App endpoints."""
    calls: list[tuple[str, str]] = []
    now = (clock or time.time)()
    exp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + expires_in))
    if installations is None:
        installations = [
            {"id": 111, "account": {"login": "some-other-org"}},
            {"id": 222, "account": {"login": mod.ORG}},
        ]

    def fake(path, tok, method="GET"):
        calls.append((method, path))
        if path == "app/installations":
            return installations
        if path.endswith("/access_tokens"):
            return {"token": token, "expires_at": exp, "permissions": {"self_hosted_runners": "write"}}
        raise AssertionError(f"unexpected App call: {method} {path}")

    monkeypatch.setattr(mod, "_gh_raw", fake)
    return calls


def test_the_app_jwt_is_rs256_and_verifies_against_its_own_public_key(monkeypatch, tmp_path) -> None:
    """End to end, with a real key: sign, then verify the claims GitHub actually checks.

    Mocking jwt.encode would prove only that we call it. A malformed claim set fails in production
    as a 401 from GitHub with nothing on ci-orch saying why, so the payload is the thing to test.
    """
    jwt_mod, key_path, pub = _rsa_key(tmp_path)
    mod = _load(monkeypatch, app_id=_APP_ID, key_path=str(key_path))
    assert mod.app_enabled() is True

    token = mod._app_jwt()
    claims = jwt_mod.decode(token, pub, algorithms=["RS256"])
    assert claims["iss"] == _APP_ID, claims
    assert claims["exp"] - claims["iat"] == 600, (
        f"the App JWT lifetime is {claims['exp'] - claims['iat']}s; GitHub rejects anything over "
        f"10 minutes, and the 60s back-dating is for clock skew"
    )
    header = jwt_mod.get_unverified_header(token)
    assert header["alg"] == "RS256", header
    # iat must be back-dated, not "now": a host whose clock is seconds fast gets its JWT rejected.
    assert claims["iat"] <= int(time.time()), claims


def test_the_installation_is_resolved_by_org_login_not_by_position(monkeypatch, tmp_path) -> None:
    """The listing carries every installation the App has. Taking the first one would mint a token
    for some other org -- which would then fail closed on every call, or worse, succeed against
    the wrong account."""
    jwt_mod, key_path, _ = _rsa_key(tmp_path)
    mod = _load(monkeypatch, app_id=_APP_ID, key_path=str(key_path), org="thyn-ai")
    calls = _stub_github(mod, monkeypatch)
    assert mod._installation_id() == 222
    assert mod.app_token() == "ghs_MINTED"
    assert calls[0] == ("GET", "app/installations")
    assert calls[1] == ("POST", "app/installations/222/access_tokens")


def test_an_app_not_installed_on_the_org_falls_back(monkeypatch, tmp_path) -> None:
    """The owner has not created the App yet, so this is the state a too-early deploy lands in.
    It must degrade to the static token, not wedge."""
    jwt_mod, key_path, _ = _rsa_key(tmp_path)
    mod = _load(monkeypatch, app_id=_APP_ID, key_path=str(key_path))
    _stub_github(mod, monkeypatch, installations=[{"id": 1, "account": {"login": "elsewhere"}}])
    assert mod.github_token() == _STATIC
    assert any("token mint failed" in l for l in mod._test_logs), mod._test_logs
    assert mod.app_enabled() is False, "a failed mint must cool the App path down"


def test_the_token_is_cached_and_refreshed_before_it_expires(monkeypatch, tmp_path) -> None:
    """One mint per hour, not one per call -- gh() runs hundreds of times per cycle, and minting
    each time would spend the App's own budget as fast as the static one was spent."""
    jwt_mod, key_path, _ = _rsa_key(tmp_path)
    mod = _load(monkeypatch, app_id=_APP_ID, key_path=str(key_path))
    calls = _stub_github(mod, monkeypatch, expires_in=3600)
    clock = {"t": time.time()}
    monkeypatch.setattr(mod.time, "time", lambda: clock["t"])

    first = mod.app_token()
    for _ in range(5):
        assert mod.app_token() == first
    mints = [c for c in calls if c[1].endswith("access_tokens")]
    assert len(mints) == 1, calls
    installs = [c for c in calls if c[1] == "app/installations"]
    assert len(installs) == 1, "the installation id was re-resolved; it is stable for the process"

    # Cross the refresh-safety window and the next call must mint again.
    clock["t"] += 3600 - mod._APP_REFRESH_SAFETY_S + 1
    assert mod.app_token() == "ghs_MINTED"
    assert len([c for c in calls if c[1].endswith("access_tokens")]) == 2, calls


def test_the_expiry_comes_from_github_not_from_a_hardcoded_hour(monkeypatch, tmp_path) -> None:
    """`expires_at` is parsed, so a shortened token lifetime is honoured. Assuming 3600 would mean
    presenting an expired token and relying on the 401 retry to notice."""
    jwt_mod, key_path, _ = _rsa_key(tmp_path)
    mod = _load(monkeypatch, app_id=_APP_ID, key_path=str(key_path))
    calls = _stub_github(mod, monkeypatch, expires_in=400)  # shorter than the safety margin
    clock = {"t": time.time()}
    monkeypatch.setattr(mod.time, "time", lambda: clock["t"])
    mod.app_token()
    clock["t"] += 200
    mod.app_token()
    assert len([c for c in calls if c[1].endswith("access_tokens")]) == 2, (
        "a token expiring inside the refresh margin was served from cache"
    )


def test_an_unparseable_expiry_degrades_to_an_hour(monkeypatch, tmp_path) -> None:
    """A missing or odd expires_at must not raise -- the 401 retry in gh() is the backstop."""
    jwt_mod, key_path, _ = _rsa_key(tmp_path)
    mod = _load(monkeypatch, app_id=_APP_ID, key_path=str(key_path))
    monkeypatch.setattr(mod, "_gh_raw", lambda p, t, method="GET": (
        [{"id": 5, "account": {"login": mod.ORG}}] if p == "app/installations"
        else {"token": "ghs_X"}))  # no expires_at at all
    assert mod.app_token() == "ghs_X"
    assert mod._app_state["exp"] > time.time()


# ------------------------------------------------------------------- permanent vs transient


def test_an_unreadable_key_disables_permanently_and_says_so_once(monkeypatch, tmp_path) -> None:
    """A missing or unreadable key file will not fix itself while the process runs, so retrying it
    on every call would add a failing open() to each of hundreds of calls per cycle. Disable, log
    once, and name the fix."""
    mod = _load(monkeypatch, app_id=_APP_ID, key_path=str(tmp_path / "absent.pem"))
    assert mod.github_token() == _STATIC
    assert mod.app_enabled() is False
    notes = [l for l in mod._test_logs if "DISABLED" in l]
    assert len(notes) == 1, mod._test_logs
    assert "restart az-orchestrator" in notes[0], notes[0]
    mod.github_token()
    mod.github_token()
    assert len([l for l in mod._test_logs if "DISABLED" in l]) == 1, mod._test_logs


def test_a_transient_mint_failure_cools_down_then_recovers(monkeypatch, tmp_path) -> None:
    """A GitHub 5xx or a network blip must NOT permanently disable the App path -- that would
    quietly revert the fleet to the token whose budget is the whole problem, and stay reverted
    until somebody restarted the service."""
    jwt_mod, key_path, _ = _rsa_key(tmp_path)
    mod = _load(monkeypatch, app_id=_APP_ID, key_path=str(key_path))
    clock = {"t": time.time()}
    monkeypatch.setattr(mod.time, "time", lambda: clock["t"])

    def fail_once(path, tok, method="GET"):
        raise OSError("connection reset by peer")

    monkeypatch.setattr(mod, "_gh_raw", fail_once)
    assert mod.github_token() == _STATIC
    assert mod._app_state["disabled"] is None, "a transient failure disabled the App permanently"
    assert mod.app_enabled() is False, "the cooldown is not in effect"

    clock["t"] += mod._APP_RETRY_COOLDOWN_S + 1
    _stub_github(mod, monkeypatch)
    assert mod.app_enabled() is True
    assert mod.github_token() == "ghs_MINTED"


# ------------------------------------------------------------------------------- gh() wiring


def test_gh_authenticates_with_the_minted_token(monkeypatch, tmp_path) -> None:
    jwt_mod, key_path, _ = _rsa_key(tmp_path)
    mod = _load(monkeypatch, app_id=_APP_ID, key_path=str(key_path))
    _stub_github(mod, monkeypatch)
    seen = []

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        seen.append((req.full_url, req.get_header("Authorization"), timeout))
        return _Resp(json.dumps({"ok": True}).encode())

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    assert mod.gh("orgs/thyn-ai/actions/runners") == {"ok": True}
    assert seen and seen[0][1] == "Bearer ghs_MINTED", seen
    assert seen[0][2] == 15, "the per-call timeout was lost in the rewrite"


def test_a_401_reauths_once_and_retries_with_the_new_token(monkeypatch) -> None:
    """An installation token expires hourly and this process runs for weeks, so a 401 is routine.
    Raising instead would fail a reconcile cycle every hour, forever."""
    mod = _load(monkeypatch)
    tokens = iter(["expired-token", "fresh-token"])
    headers: list[str] = []
    invalidated: list[str] = []
    monkeypatch.setattr(mod, "app_enabled", lambda: True)
    monkeypatch.setattr(mod, "github_token", lambda: next(tokens))
    monkeypatch.setattr(mod, "invalidate_app_token", lambda why: invalidated.append(why))

    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        headers.append(req.get_header("Authorization"))
        if calls["n"] == 1:
            raise urllib.error.HTTPError(req.full_url, 401, "Bad credentials", {}, None)
        return _BytesResp(json.dumps({"ok": True}).encode())

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    assert mod.gh("orgs/thyn-ai/actions/runners") == {"ok": True}
    assert calls["n"] == 2, calls
    assert headers == ["Bearer expired-token", "Bearer fresh-token"], headers
    assert invalidated and "401" in invalidated[0], invalidated


def test_a_second_401_is_raised_not_retried_forever(monkeypatch) -> None:
    """Exactly one re-auth. An unbounded retry loop on a rejected credential would spin."""
    mod = _load(monkeypatch)
    monkeypatch.setattr(mod, "app_enabled", lambda: True)
    monkeypatch.setattr(mod, "github_token", lambda: "always-bad")
    monkeypatch.setattr(mod, "invalidate_app_token", lambda why: None)

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 401, "Bad credentials", {}, None)

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(urllib.error.HTTPError) as exc:
        mod.gh("orgs/thyn-ai/actions/runners")
    assert exc.value.code == 401


def test_a_403_is_not_retried(monkeypatch) -> None:
    """403 is the RATE LIMIT on this token -- the measured production failure. Retrying it spends
    more of the budget that is already exhausted, which is the opposite of what is wanted, and
    hides the diagnosis behind a retry loop."""
    mod = _load(monkeypatch)
    monkeypatch.setattr(mod, "github_token", lambda: _STATIC)
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        raise urllib.error.HTTPError(req.full_url, 403, "rate limit exceeded", {}, None)

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(urllib.error.HTTPError) as exc:
        mod.gh("orgs/thyn-ai/actions/runners")
    assert exc.value.code == 403
    assert calls["n"] == 1, f"a 403 was retried {calls['n']} times"


def test_a_network_stall_still_retries_three_times(monkeypatch) -> None:
    """The pre-existing bound must survive the rewrite: a hung read is retried, not raised on the
    first failure, and the whole thing is still capped."""
    mod = _load(monkeypatch)
    monkeypatch.setattr(mod, "github_token", lambda: _STATIC)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        raise TimeoutError("timed out")

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(TimeoutError):
        mod.gh("orgs/thyn-ai/actions/runners")
    assert calls["n"] == 3, calls


# ------------------------------------------------------------------- the worker-token boundary


def test_workers_keep_the_static_token_even_in_app_mode(monkeypatch, tmp_path) -> None:
    """THE migration boundary, pinned.

    An installation token can POST a runner registration-token but CANNOT create or patch a gist:
    the gists API is scoped to a user's `gist` OAuth scope, which installation tokens do not
    carry. Handing a worker an installation token today would keep registration working while
    silently killing the boot-log sink -- the same class of silent loss #1002 exists to prevent,
    and worse here because it would look like the App migration succeeded.
    """
    jwt_mod, key_path, _ = _rsa_key(tmp_path)
    mod = _load(monkeypatch, app_id=_APP_ID, key_path=str(key_path))
    _stub_github(mod, monkeypatch)
    assert mod.github_token() == "ghs_MINTED", "the orchestrator should be on the App token"
    assert mod.worker_github_token() == _STATIC, (
        "a worker would receive an installation token and lose its gist telemetry"
    )


def test_render_userdata_embeds_the_worker_token_not_the_app_token(monkeypatch, tmp_path) -> None:
    """The customData payload is what actually reaches a worker, so the boundary has to hold at
    the render, not just in the function that computes it."""
    jwt_mod, key_path, _ = _rsa_key(tmp_path)
    mod = _load(monkeypatch, app_id=_APP_ID, key_path=str(key_path), static=_STATIC)
    _stub_github(mod, monkeypatch)
    out = tmp_path / "worker.yml"
    mod.render_userdata(mod.CLOUD_INIT_FAST, "ci-az-1-2", str(out))
    doc = out.read_text()
    assert _STATIC in doc, "the worker did not receive the static token"
    assert "ghs_MINTED" not in doc, "an installation token leaked into a worker's cloud-init"


# ------------------------------------------------------------------- no regression in behaviour


def test_the_org_runner_listing_still_paginates_under_app_auth(monkeypatch, tmp_path) -> None:
    """all_runners() is the pagination-safe path the busy protection depends on. Rewiring auth
    must not touch it: a truncated listing is how a busy runner went missing from the busy set
    once already, and a busy runner missing from that set is one the reapers will delete mid-job."""
    jwt_mod, key_path, _ = _rsa_key(tmp_path)
    mod = _load(monkeypatch, app_id=_APP_ID, key_path=str(key_path))
    _stub_github(mod, monkeypatch)
    runners = [{"name": f"ci-az-9-{i}", "id": i, "busy": i == 149} for i in range(150)]
    paths: list[str] = []

    def fake(path, method="GET", body=None):
        paths.append(path)
        import re as _re
        page = int(_re.search(r"[&?]page=(\d+)", path).group(1))
        return {"runners": runners[(page - 1) * 100: page * 100]}

    monkeypatch.setattr(mod, "gh", fake)
    assert len(mod.all_runners()) == 150
    assert mod.busy_runner_names() == {"ci-az-9-149"}, (
        "the busy runner on page 2 was not seen; it is now reapable mid-job"
    )
    assert len([p for p in paths if "page=2" in p]) >= 1, paths


def test_a_key_file_that_is_not_an_rsa_key_disables_permanently(monkeypatch, tmp_path) -> None:
    """The other permanent case: the path exists and is readable but holds something PyJWT cannot
    sign with (a truncated copy, a public key, an SSH-format key). Same handling as an absent
    file, because retrying cannot help -- and the log must name the file."""
    bad = tmp_path / "app-key.pem"
    bad.write_text("-----BEGIN PRIVATE KEY-----\nnotactuallyakey\n-----END PRIVATE KEY-----\n")
    mod = _load(monkeypatch, app_id=_APP_ID, key_path=str(bad))
    assert mod.github_token() == _STATIC
    notes = [l for l in mod._test_logs if "DISABLED" in l]
    assert len(notes) == 1, mod._test_logs
    assert str(bad) in notes[0], notes[0]


# ------------------------------------------------- the repo-listing endpoint switch (activation)


def test_repo_listing_uses_the_org_endpoint_on_the_static_token(monkeypatch) -> None:
    """Unchanged behaviour while the App is not configured."""
    mod = _load(monkeypatch)
    paths: list[str] = []
    monkeypatch.setattr(mod, "gh", lambda p, **k: paths.append(p) or [])
    assert mod.served_repos() == []
    assert paths == [f"orgs/{mod.ORG}/repos?per_page=100&page=1&type=all"], paths


def test_repo_listing_switches_to_the_installation_endpoint_under_app_auth(monkeypatch, tmp_path) -> None:
    """THE ACTIVATION BLOCKER.

    `GET /orgs/{org}/repos` is a user-token call. An installation token is not the org, it is an
    app installed on the org, and its listing is `GET /installation/repositories`. Migrating the
    credential without migrating this call would fail every repo scan, served_repos() would keep
    serving its stale-then-empty cache, no queued job would ever be found, and nothing would
    provision -- with the service still reading "active". That is a dark plane, not a degraded
    one, and it would look exactly like the 2026-09-16 outage.
    """
    jwt_mod, key_path, _ = _rsa_key(tmp_path)
    mod = _load(monkeypatch, app_id=_APP_ID, key_path=str(key_path))
    _stub_github(mod, monkeypatch)
    paths: list[str] = []

    def fake(p, method="GET", body=None):
        paths.append(p)
        if p.startswith("installation/repositories"):
            return {"total_count": 2, "repository_selection": "all",
                    "repositories": [{"full_name": "thyn-ai/algenta"},
                                     {"full_name": "thyn-ai/codna"}]}
        raise AssertionError(f"installation token used a user-token endpoint: {p}")

    monkeypatch.setattr(mod, "gh", fake)
    assert mod.served_repos() == ["thyn-ai/algenta", "thyn-ai/codna"]
    assert all(p.startswith("installation/repositories") for p in paths), paths


def test_the_installation_response_shape_is_unwrapped_not_iterated(monkeypatch, tmp_path) -> None:
    """The two endpoints answer differently: a bare list vs {"repositories": [...]}. Iterating the
    dict would yield its KEYS as repo names, which is a silent wrong answer rather than an error
    -- every "repo" would be a string like 'total_count' and every job lookup would fail."""
    jwt_mod, key_path, _ = _rsa_key(tmp_path)
    mod = _load(monkeypatch, app_id=_APP_ID, key_path=str(key_path))
    _stub_github(mod, monkeypatch)
    monkeypatch.setattr(mod, "gh", lambda p, **k: {
        "total_count": 1, "repositories": [{"full_name": "thyn-ai/algenta"}]})
    assert mod.served_repos() == ["thyn-ai/algenta"]


def test_a_failed_repo_scan_keeps_the_previous_list_under_app_auth(monkeypatch, tmp_path) -> None:
    """Pre-existing guarantee, re-pinned on the new branch: a transient scan failure must serve
    the stale-but-known list, because an empty served set means no job is ever dispatched."""
    jwt_mod, key_path, _ = _rsa_key(tmp_path)
    mod = _load(monkeypatch, app_id=_APP_ID, key_path=str(key_path))
    _stub_github(mod, monkeypatch)
    mod._repo_cache["value"] = ["thyn-ai/algenta"]
    mod._repo_cache["exp"] = 0.0  # expired, so the scan really runs

    def boom(p, **k):
        raise RuntimeError("502")

    monkeypatch.setattr(mod, "gh", boom)
    assert mod.served_repos() == ["thyn-ai/algenta"]
    assert any("repo scan failed" in l and "installation" in l for l in mod._test_logs), (
        mod._test_logs
    )


class _BytesResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False
