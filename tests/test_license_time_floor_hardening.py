"""Time-floor hardening (GAP-1): the lapse floor can never re-validate a lapsed paid license.

Threat (tested on algenta-ent-a100, battery T8b): apps/runtime/trusted_time.py keeps a
non-decreasing lapse floor in $ALGENTA_RUNTIME_DIR/trusted_time.json. Deleting that file and
rolling the wall clock back made a hard-expired paid deployment license validate as fully paid
again. This suite pins the closure:

  * the floor is HMAC-protected by a 0600 runtime-dir secret (``time_floor_key``);
  * a license whose floor is missing/tampered either re-seeds the floor from its vendor-signed
    ``signed_epoch`` claim (RS256 already covers it) or settles to the Community floor — the
    engine never stops, but a lapsed paid license never re-validates;
  * the lapse settle is DURABLE across reboots (the floor settles past the token's hard-deny
    boundary, anchored to vendor-signed claims, never the host clock);
  * first-boot air-gapped activation keeps working (no floor yet + signed_epoch → paid).

Fixture style mirrors tests/test_runtime_license.py: ephemeral RSA keys +
ALGENTA_LOCAL_LICENSE_PUBLIC_KEY (legacy offline RS256 path) and, for the strict-profile cases,
ALGENTA_LICENSE_TRUST_BUNDLE.
"""

from __future__ import annotations

import importlib
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def _rsa_keypair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_text = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_text = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return private_text, public_text


def _reload_modules():
    tt = importlib.import_module("apps.runtime.trusted_time")
    lic = importlib.import_module("apps.runtime.license")
    return importlib.reload(tt), importlib.reload(lic)


def _reboot(tt) -> None:
    """Drop the in-process trusted-clock session so the next load behaves like a fresh daemon
    start (the attack reboots the engine; the monotonic session clock must not paper over it)."""
    tt._SESSION_RUNTIME_DIR = None
    tt._SESSION_MONOTONIC_BASE = None
    tt._SESSION_TRUSTED_BASE = None


def _offline_token(priv: str, **overrides) -> str:
    now = int(time.time())
    claims = {
        "api_key_prefix": "offline",
        "device_id": "device-floor-hardening",
        "plan": "enterprise",
        "device_limit": 0,
        "permitted_modules": ["*"],
        "issued_at": now,
        "expires_at": now + 30 * 86400,
        "key_expires_at": now + 30 * 86400,
        "grace_days": 14,
        "iss": "algenta-offline-license",
        "sub": "device-license",
        "ver": 2,
    }
    claims.update(overrides)
    return jwt.encode(claims, priv, algorithm="RS256")


@pytest.fixture()
def offline_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("ALGENTA_RUNTIME_DEV_MODE", raising=False)
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    priv, pub = _rsa_keypair()
    monkeypatch.setenv("ALGENTA_LOCAL_LICENSE_PUBLIC_KEY", pub)
    return priv


# ── trusted_time: HMAC floor integrity ─────────────────────────────────────────


def test_floor_starts_missing_then_ok_after_first_write(offline_env) -> None:
    tt, _ = _reload_modules()
    assert tt.floor_integrity() == "missing"
    assert tt._read_state() == (None, "missing")

    tt.observe_time(1_900_000_000.0, source="control-plane-register")
    assert tt.floor_integrity() == "ok"
    state, integrity = tt._read_state()
    assert integrity == "ok" and state is not None
    assert state.trusted_epoch == 1_900_000_000.0

    # the HMAC key is auto-created in the runtime dir, owner-only
    from apps.runtime.trusted_time import _time_floor_key_file

    key_file = _time_floor_key_file()
    assert key_file.exists()
    assert key_file.stat().st_mode & 0o777 == 0o600


def test_tampered_floor_is_detected_and_never_contributes(offline_env) -> None:
    tt, _ = _reload_modules()
    tt.observe_time(1_900_000_000.0, source="control-plane-register")

    # Attacker forges an old-format floor with a lowered epoch (no HMAC).
    from apps.runtime.trusted_time import _trusted_time_file

    _trusted_time_file().write_text(
        json.dumps({"version": 1, "trusted_epoch": 1_000_000_000.0, "source": "local"})
    )
    assert tt.floor_integrity() == "tampered"
    state, integrity = tt._read_state()
    assert integrity == "tampered" and state is not None

    # The tampered epoch contributes NOTHING to the floor — an observe re-seeds from scratch.
    tt.observe_time(1_950_000_000.0, source="signed-epoch")
    state, integrity = tt._read_state()
    assert integrity == "ok"
    assert state.trusted_epoch == 1_950_000_000.0  # NOT max(1_000_000_000, ...)


def test_deleted_floor_reads_missing(offline_env) -> None:
    tt, _ = _reload_modules()
    tt.observe_time(1_900_000_000.0, source="control-plane-register")
    from apps.runtime.trusted_time import _trusted_time_file

    _trusted_time_file().unlink()
    assert tt.floor_integrity() == "missing"
    assert tt._read_state() == (None, "missing")


# ── (a) THE attack: expired license + deleted floor + rolled-back clock ─────────


def test_expired_license_deleted_floor_rolled_back_clock_settles_community(
    monkeypatch, offline_env
) -> None:
    tt, lic = _reload_modules()
    real_now = int(time.time())

    # Hard-expired legacy license (no signed_epoch — the worst case), grace already exhausted.
    expired_at = real_now - 10 * 86400
    token = _offline_token(
        offline_env,
        issued_at=expired_at - 30 * 86400,
        expires_at=expired_at,
        key_expires_at=expired_at,
        grace_days=0,
    )
    lic._save_license(token)
    # The deployment ran while paid: a signed floor exists at the real time.
    tt.observe_time(float(real_now), source="control-plane-register")

    # Attack: reboot, delete the floor, roll the wall clock back before expiry.
    _reboot(tt)
    from apps.runtime.trusted_time import _trusted_time_file

    _trusted_time_file().unlink()
    rolled_back = float(expired_at - 86400)
    monkeypatch.setattr(time, "time", lambda: rolled_back)

    result = lic.load_license("")
    assert result.valid is True  # the engine never stops...
    assert result.plan == "algenta_free"  # ...but at the Community floor, NEVER paid
    assert result.source == "community-fallback"
    assert result.concurrent_worker_limit == 1
    assert "time-floor-unverifiable" in result.message

    # Durable: the floor settled PAST the hard-deny boundary (vendor-signed claims, not the host
    # clock), so a second reboot under the same rolled-back clock still settles to Community.
    floor = json.loads(_trusted_time_file().read_text())
    assert floor["trusted_epoch"] >= expired_at + 1
    assert tt.floor_integrity() == "ok"
    _reboot(tt)
    again = lic.load_license("")
    assert again.plan == "algenta_free"
    assert again.source == "community-fallback"


# ── (b) tampered floor → Community ──────────────────────────────────────────────


def test_tampered_floor_settles_valid_license_to_community(monkeypatch, offline_env) -> None:
    tt, lic = _reload_modules()
    real_now = int(time.time())

    token = _offline_token(offline_env, expires_at=real_now + 30 * 86400)
    lic._save_license(token)
    tt.observe_time(float(real_now), source="control-plane-register")

    # Attacker rewrites the floor (unsigned forgery — the HMAC no longer matches).
    _reboot(tt)
    from apps.runtime.trusted_time import _trusted_time_file

    _trusted_time_file().write_text(
        json.dumps({"version": 1, "trusted_epoch": 1.0, "source": "local"})
    )

    result = lic.load_license("")
    assert result.valid is True
    assert result.plan == "algenta_free"
    assert result.source == "community-fallback"
    assert "time-floor-unverifiable" in result.message


# ── (c) signed_epoch re-seeds a deleted floor → paid validates ─────────────────


def test_signed_epoch_reseeds_deleted_floor_and_paid_validates(monkeypatch, offline_env) -> None:
    tt, lic = _reload_modules()
    real_now = int(time.time())

    token = _offline_token(
        offline_env,
        expires_at=real_now + 30 * 86400,
        signed_epoch=real_now,  # the vendor-signed mint time (new minters emit it)
    )
    lic._save_license(token)
    tt.observe_time(float(real_now), source="control-plane-register")

    # Attack attempt: reboot, delete the floor, roll the clock back.
    _reboot(tt)
    from apps.runtime.trusted_time import _trusted_time_file

    _trusted_time_file().unlink()
    monkeypatch.setattr(time, "time", lambda: float(real_now - 20 * 86400))

    result = lic.load_license("")
    assert result.valid is True
    assert result.plan == "enterprise"  # paid validates — the floor came from the signature
    assert result.source == "offline-local"

    # The floor is re-seeded at the vendor-signed epoch and is now integrity-checked ok.
    assert tt.floor_integrity() == "ok"
    state, integrity = tt._read_state()
    assert integrity == "ok" and state is not None
    assert state.trusted_epoch >= real_now
    assert state.source == "signed-epoch"
    assert int(tt.trusted_now_epoch()) >= real_now  # rolled-back clock can't drag time down


# ── (d) first boot (no floor at all) + signed_epoch → paid validates ───────────


def test_first_boot_airgap_license_with_signed_epoch_validates(offline_env) -> None:
    tt, lic = _reload_modules()
    real_now = int(time.time())

    # First boot of an air-gapped activation: license stored, NO floor file yet.
    token = _offline_token(
        offline_env,
        expires_at=real_now + 30 * 86400,
        signed_epoch=real_now,
    )
    lic._save_license(token)

    result = lic.load_license("")
    assert result.valid is True
    assert result.plan == "enterprise"
    assert result.source == "offline-local"
    # ...and the ceremony left a signed floor behind for every later boot.
    assert tt.floor_integrity() == "ok"
    state, _ = tt._read_state()
    assert state.trusted_epoch >= real_now


def test_first_boot_airgap_without_signed_epoch_fails_closed_to_community(offline_env) -> None:
    tt, lic = _reload_modules()
    real_now = int(time.time())

    # A legacy token (no signed_epoch) with NO floor cannot prove its lapse state — fail closed.
    token = _offline_token(offline_env, expires_at=real_now + 30 * 86400)
    lic._save_license(token)

    result = lic.load_license("")
    assert result.valid is True  # engine never stops
    assert result.plan == "algenta_free"
    assert result.source == "community-fallback"


# ── (e) regressions: normal lifecycle untouched ────────────────────────────────


def test_normal_valid_license_unaffected(offline_env) -> None:
    tt, lic = _reload_modules()
    real_now = int(time.time())

    token = _offline_token(offline_env, expires_at=real_now + 30 * 86400, signed_epoch=real_now)
    lic._save_license(token)
    tt.observe_time(float(real_now), source="signed-epoch")
    _reboot(tt)

    result = lic.load_license("")
    assert result.valid is True
    assert result.plan == "enterprise"
    assert result.source == "offline-local"


def test_normal_grace_window_still_grace(offline_env) -> None:
    tt, lic = _reload_modules()
    real_now = int(time.time())

    expires_at = real_now - 86400  # expired yesterday
    token = _offline_token(
        offline_env,
        issued_at=expires_at - 30 * 86400,
        expires_at=expires_at,
        key_expires_at=expires_at,
        grace_days=14,  # still inside the 14-day grace window
        signed_epoch=expires_at - 30 * 86400,
    )
    lic._save_license(token)
    tt.observe_time(float(real_now), source="signed-epoch")  # floor at the honest wall clock
    _reboot(tt)

    result = lic.load_license("")
    assert result.valid is True
    assert result.plan == "enterprise"  # grace keeps the paid plan running
    assert result.source == "offline-local"
    assert "grace" in result.message.lower()


def test_normal_hard_expiry_still_settles_community_with_expiry_message(offline_env) -> None:
    tt, lic = _reload_modules()
    real_now = int(time.time())

    expires_at = real_now - 30 * 86400
    token = _offline_token(
        offline_env,
        issued_at=expires_at - 30 * 86400,
        expires_at=expires_at,
        key_expires_at=expires_at,
        grace_days=0,
        signed_epoch=expires_at - 30 * 86400,
    )
    lic._save_license(token)
    tt.observe_time(float(real_now), source="signed-epoch")  # honest clock, intact floor
    _reboot(tt)

    result = lic.load_license("")
    assert result.valid is True  # engine keeps running
    assert result.plan == "algenta_free"
    assert result.source == "community-fallback"
    # The NORMAL expiry message — this is plain hard expiry, not a floor-integrity failure.
    assert "time-floor-unverifiable" not in result.message
    assert "expired" in result.message.lower()


def test_community_license_never_gated_by_floor(offline_env) -> None:
    # The Community floor itself never consults the lapse floor (expires_at=0), so deleting the
    # floor under an already-Community runtime changes nothing.
    _, lic = _reload_modules()
    community = lic._make_community_license(reason="lapsed")
    assert community.plan == "algenta_free" and community.expires_at == 0


# ── mint side: new minters carry signed_epoch (RS256-covered) ──────────────────


def test_mint_deployment_token_carries_signed_epoch(monkeypatch) -> None:
    from apps.runtime.license import mint_deployment_token

    priv, pub = _rsa_keypair()
    issued_at = 1_900_000_000
    token = mint_deployment_token(
        org_id="org-acme",
        product="algenta",
        edition="server",
        deployment_id="prod-us",
        license_claims={"max_concurrent_units": 8},
        ttl_days=365,
        issued_at=issued_at,
        private_key_pem=priv,
    )
    payload = jwt.decode(
        token,
        pub,
        algorithms=["RS256"],
        audience="algenta-runtime",
        # issued_at override is a deterministic test anchor — not a wall-clock claim to police
        options={"verify_exp": False, "verify_nbf": False, "verify_iat": False},
    )
    assert payload["signed_epoch"] == issued_at  # inside the RS256 signature


def test_offline_issuer_script_claims_carry_signed_epoch() -> None:
    import importlib.util
    from pathlib import Path as _Path

    spec = importlib.util.spec_from_file_location(
        "_issue_offline_license_floor_hardening",
        _Path(__file__).resolve().parents[1] / "scripts" / "issue_offline_license.py",
    )
    issuer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(issuer)

    args = issuer._build_parser().parse_args(
        ["--device-id", "device-x", "--plan", "enterprise", "--output", "/dev/null"]
    )
    claims = issuer._build_claims(args)
    assert claims["signed_epoch"] == claims["issued_at"] > 0


# ── GAP-2: the daemon re-checks the CU gate on license reload ──────────────────


def test_daemon_recheck_deployment_capacity_refuses_on_reload(monkeypatch) -> None:
    from apps.runtime import daemon

    class _OverCapLicense:
        max_concurrent_units = 1
        unit_size_val = 4

        def is_deployment_scope(self) -> bool:
            return True

        def unit_size(self) -> int:
            return self.unit_size_val

    from apps.runtime import capacity

    monkeypatch.setattr(
        capacity,
        "measure_effective_vcpu",
        lambda: capacity.CapacityMeasurement(effective_vcpu=96.0, source="test", constraints={}),
    )
    with pytest.raises(RuntimeError, match="Compute-Unit capacity gate"):
        daemon._recheck_deployment_capacity(_OverCapLicense())


def test_daemon_recheck_deployment_capacity_admits_within_pool(monkeypatch) -> None:
    from apps.runtime import capacity, daemon

    class _WithinPoolLicense:
        max_concurrent_units = 128

        def is_deployment_scope(self) -> bool:
            return True

        def unit_size(self) -> int:
            return 4

    monkeypatch.setattr(
        capacity,
        "measure_effective_vcpu",
        lambda: capacity.CapacityMeasurement(effective_vcpu=16.0, source="test", constraints={}),
    )
    daemon._recheck_deployment_capacity(_WithinPoolLicense())  # no raise
