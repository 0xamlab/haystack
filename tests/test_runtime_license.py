from __future__ import annotations

import importlib
import io
import json
import sys
import urllib.error
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from apps.api_server.config import get_settings
from apps.api_server.services.device_service import _issue_license_jwt
from apps.runtime.license import _parse_token


def _reload_runtime_license():
    module_name = "apps.runtime.license"
    if module_name in sys.modules:
        return importlib.reload(sys.modules[module_name])
    return importlib.import_module(module_name)


def _rsa_keypair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_text = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_text = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_text, public_text


def test_parse_control_plane_license_with_explicit_signing_secret(monkeypatch):
    # plan="developer" is a Codna-style unprefixed plan, and Codna's runtime is the ONE product
    # that still verifies HS256 by deliberate, already-reviewed design (rs256_license=False) — so
    # this test's runtime identifies itself as codna, matching a real Codna deployment.
    monkeypatch.setenv("ALGENTA_RUNTIME_PRODUCT", "codna")
    monkeypatch.setenv("LICENSE_SIGNING_SECRET", "local-license-secret")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    get_settings.cache_clear()

    token = _issue_license_jwt(
        device_id="device-1234567890",
        api_key_prefix="de_live_test",
        plan="developer",
        device_limit=5,
        org_id="org_test",
    )

    parsed = _parse_token(token, "de_live_test_key")
    assert parsed is not None
    assert parsed.valid is True
    assert parsed.plan == "developer"
    assert parsed.device_id == "device-1234567890"
    assert parsed.device_limit == 5
    assert parsed.source == "control-plane"

    get_settings.cache_clear()


def test_parse_offline_local_license_with_public_key(monkeypatch):
    monkeypatch.setenv("ALGENTA_REQUIRE_LOCAL_LICENSE", "1")
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    private_key, public_key = _rsa_keypair()
    monkeypatch.setenv("ALGENTA_LOCAL_LICENSE_PUBLIC_KEY", public_key)

    token = importlib.import_module("jwt").encode(
        {
            "api_key_prefix": "offline",
            "device_id": "device-offline-rs256",
            "plan": "enterprise",
            "device_limit": 0,
            "permitted_modules": ["*"],
            "issued_at": 1_900_000_000,
            "expires_at": 1_999_999_999,
            "key_expires_at": 1_999_999_999,
            "grace_days": 14,
            "iss": "algenta-offline-license",
            "sub": "device-license",
            "ver": 2,
        },
        private_key,
        algorithm="RS256",
    )

    parsed = _reload_runtime_license()._parse_token(token, "")
    assert parsed is not None
    assert parsed.valid is True
    assert parsed.device_id == "device-offline-rs256"
    assert parsed.source == "offline-local"

    get_settings.cache_clear()


def test_parse_control_plane_license_with_derived_jwt_secret(monkeypatch):
    # See the comment on test_parse_control_plane_license_with_explicit_signing_secret above:
    # plan="developer" is Codna-style, the one product still verifying HS256 by design.
    monkeypatch.setenv("ALGENTA_RUNTIME_PRODUCT", "codna")
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET", "jwt-signing-seed")
    get_settings.cache_clear()

    token = _issue_license_jwt(
        device_id="device-abcdefghij",
        api_key_prefix="de_live_test",
        plan="developer",
        device_limit=5,
        org_id="org_test",
    )

    parsed = _parse_token(token, "de_live_test_key")
    assert parsed is not None
    assert parsed.valid is True
    assert parsed.source == "control-plane"

    get_settings.cache_clear()


def test_issue_control_plane_license_uses_api_key_expiry_when_present(monkeypatch):
    # plan="developer" is Codna-style, the one product still verifying HS256 by design.
    monkeypatch.setenv("ALGENTA_RUNTIME_PRODUCT", "codna")
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET", "jwt-signing-seed")
    get_settings.cache_clear()

    # Use an api-key expiry INSIDE the rolling renewal window so the license honors it directly.
    # (A far-future key expiry is deliberately capped to now + _LICENSE_RENEWAL_TTL_DAYS to close
    # "pay once and leave" — see test_issue_control_plane_license_caps_far_future_expiry below.)
    expires_at = datetime.now(UTC) + timedelta(days=10)
    token = _issue_license_jwt(
        device_id="device-expiry-bound-123",
        api_key_prefix="de_live_test",
        plan="developer",
        device_limit=5,
        org_id="org_test",
        api_key_expires_at=expires_at,
    )

    parsed = _parse_token(token, "de_live_test_key")
    assert parsed is not None
    assert parsed.valid is True
    assert parsed.expires_at == int(expires_at.timestamp())
    assert parsed.key_expires_at == int(expires_at.timestamp())

    get_settings.cache_clear()


def test_issue_control_plane_license_caps_far_future_expiry(monkeypatch):
    """A far-future api-key expiry is capped to the rolling renewal window on the license
    (``expires_at``), while ``key_expires_at`` still records the true key expiry — this is the
    "pay once and leave" defense: the license must be renewed within the window regardless."""
    from apps.api_server.services.device_service import _LICENSE_RENEWAL_TTL_DAYS

    # plan="developer" is Codna-style, the one product still verifying HS256 by design.
    monkeypatch.setenv("ALGENTA_RUNTIME_PRODUCT", "codna")
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET", "jwt-signing-seed")
    get_settings.cache_clear()

    expires_at = datetime.now(UTC) + timedelta(days=730)
    token = _issue_license_jwt(
        device_id="device-farfuture-123",
        api_key_prefix="de_live_test",
        plan="developer",
        device_limit=5,
        org_id="org_test",
        api_key_expires_at=expires_at,
    )

    parsed = _parse_token(token, "de_live_test_key")
    assert parsed is not None and parsed.valid is True
    # expires_at is capped to the rolling window (not the 730-day key expiry)...
    window_ceiling = int(datetime.now(UTC).timestamp()) + _LICENSE_RENEWAL_TTL_DAYS * 86400
    assert parsed.expires_at <= window_ceiling + 5  # small clock-skew tolerance
    assert parsed.expires_at < int(expires_at.timestamp())
    # ...but the true backing key expiry is still recorded.
    assert parsed.key_expires_at == int(expires_at.timestamp())

    get_settings.cache_clear()


def test_load_license_prefers_stored_control_plane_token_when_offline(monkeypatch, tmp_path):
    # plan="developer" is Codna-style, the one product still verifying HS256 by design.
    monkeypatch.setenv("ALGENTA_RUNTIME_PRODUCT", "codna")
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET", "jwt-signing-seed")
    get_settings.cache_clear()

    license_mod = _reload_runtime_license()
    token = _issue_license_jwt(
        device_id="device-offline-123",
        api_key_prefix="de_live_test",
        plan="developer",
        device_limit=5,
        org_id="org_test",
    )
    license_mod._save_license(token)

    with patch.object(
        license_mod,
        "_exchange_api_key_for_license",
        side_effect=AssertionError("stored license path must not hit control plane"),
    ):
        parsed = license_mod.load_license("de_live_test_key")

    assert parsed.valid is True
    assert parsed.device_id == "device-offline-123"
    assert parsed.source == "control-plane"

    get_settings.cache_clear()


def test_load_license_without_stored_token_blocks_first_time_offline(monkeypatch, tmp_path):
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("ALGENTA_RUNTIME_DEV_MODE", raising=False)
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET", "jwt-signing-seed")
    get_settings.cache_clear()

    license_mod = _reload_runtime_license()
    with patch.object(license_mod, "_exchange_api_key_for_license", return_value=None):
        parsed = license_mod.load_license("de_live_test_key")

    assert parsed.valid is False
    assert "control plane" in parsed.message.lower()
    assert "reachable control plane" in parsed.message.lower()

    get_settings.cache_clear()


def test_load_license_in_strict_local_mode_rejects_legacy_control_plane_token(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("ALGENTA_REQUIRE_LOCAL_LICENSE", "1")
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET", "jwt-signing-seed")
    get_settings.cache_clear()

    license_mod = _reload_runtime_license()
    token = _issue_license_jwt(
        device_id="device-hmac-legacy",
        api_key_prefix="de_live_test",
        plan="developer",
        device_limit=5,
        org_id="org_test",
    )
    license_mod._save_license(token)

    parsed = license_mod.load_license("de_live_test_key")

    assert parsed.valid is False
    assert "local signed license" in parsed.message.lower()

    get_settings.cache_clear()


def test_issue_and_store_rejects_hosted_registration_when_local_license_required(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("ALGENTA_REQUIRE_LOCAL_LICENSE", "1")
    get_settings.cache_clear()

    parsed = _reload_runtime_license().issue_and_store("de_live_test_key")

    assert parsed.valid is False
    assert "issue_offline_license.py" in parsed.message

    get_settings.cache_clear()


class _FakeHTTPResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeHTTPResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self) -> bytes:
        return self._payload


def test_exchange_api_key_retries_retryable_failures_with_stable_idempotency_key(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET", "jwt-signing-seed")
    get_settings.cache_clear()

    license_mod = _reload_runtime_license()
    token = _issue_license_jwt(
        device_id="device-retry-123456",
        api_key_prefix="de_live_test",
        plan="developer",
        device_limit=5,
        org_id="org_test",
    )
    payload = json.dumps(
        {
            "license_token": token,
            "plan": "developer",
            "device_count": 1,
            "device_limit": 5,
            "credits_granted": 25,
            "credits_billing_period": "2026-04",
            "credits_expires_at": 4_000_000_000,
        }
    ).encode("utf-8")

    attempts: list[tuple[str, float, str]] = []
    sleep_calls: list[float] = []

    class _Store:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def initialize_sync(
            self,
            *,
            credits_granted: int,
            billing_period: str,
            ttl_seconds: int,
        ) -> None:
            self.calls.append(
                {
                    "credits_granted": credits_granted,
                    "billing_period": billing_period,
                    "ttl_seconds": ttl_seconds,
                }
            )

    store = _Store()

    def fake_urlopen(req, timeout):  # noqa: ANN001
        idempotency_key = next(
            value for key, value in req.header_items() if key.lower() == "idempotency-key"
        )
        attempts.append((req.full_url, timeout, idempotency_key))
        if len(attempts) == 1:
            raise TimeoutError("timed out")
        if len(attempts) == 2:
            raise urllib.error.HTTPError(
                req.full_url,
                409,
                "Conflict",
                hdrs=None,
                fp=io.BytesIO(
                    json.dumps(
                        {
                            "error": {
                                "code": "resource_write_conflict",
                                "message": "Another write is already in progress.",
                            }
                        }
                    ).encode("utf-8")
                ),
            )
        return _FakeHTTPResponse(payload)

    with (
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
        patch("apps.runtime.credits.get_store", return_value=store),
        patch.object(license_mod.time, "sleep", side_effect=sleep_calls.append),
    ):
        returned = license_mod._exchange_api_key_for_license(
            "de_live_test_key",
            {
                "device_id": "device-retry-123456",
                "platform": "darwin",
                "platform_version": "15.0",
                "hostname_hash": "hosthash",
                "sdk_version": "1.0.0",
            },
        )

    assert returned == token
    assert len(attempts) == 3
    assert all(timeout == license_mod._CONTROL_PLANE_TIMEOUT_SECONDS for _, timeout, _ in attempts)
    assert attempts[0][2] == attempts[1][2] == attempts[2][2]
    assert attempts[0][2].startswith("device-register:")
    assert sleep_calls == [
        license_mod._license_retry_delay_seconds(1),
        license_mod._license_retry_delay_seconds(2),
    ]
    assert len(store.calls) == 1
    assert store.calls[0]["credits_granted"] == 25
    assert store.calls[0]["billing_period"] == "2026-04"
    assert store.calls[0]["ttl_seconds"] > 0

    get_settings.cache_clear()


def test_exchange_api_key_records_trusted_server_time(monkeypatch, tmp_path):
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET", "jwt-signing-seed")
    get_settings.cache_clear()

    license_mod = _reload_runtime_license()
    token = _issue_license_jwt(
        device_id="device-trusted-time-123",
        api_key_prefix="de_live_test",
        plan="developer",
        device_limit=5,
        org_id="org_test",
    )
    server_time = 2_200_000_000.0
    payload = json.dumps(
        {
            "license_token": token,
            "plan": "developer",
            "device_count": 1,
            "device_limit": 5,
            "credits_granted": 1,
            "credits_billing_period": "2026-04",
            "credits_expires_at": server_time + 3600,
            "server_time": server_time,
        }
    ).encode("utf-8")

    with (
        patch("urllib.request.urlopen", return_value=_FakeHTTPResponse(payload)),
        patch("apps.runtime.credits.get_store"),
    ):
        returned = license_mod._exchange_api_key_for_license(
            "de_live_test_key",
            {
                "device_id": "device-trusted-time-123",
                "platform": "darwin",
                "platform_version": "15.0",
                "hostname_hash": "hosthash",
                "sdk_version": "1.0.0",
            },
        )

    assert returned == token
    trusted_time_path = tmp_path / "trusted_time.json"
    assert trusted_time_path.exists()
    state = json.loads(trusted_time_path.read_text())
    assert state["trusted_epoch"] == server_time
    assert state["source"] == "control-plane-register"

    get_settings.cache_clear()


def test_license_store_follows_runtime_dir_changes_without_module_reload(
    monkeypatch,
    tmp_path,
):
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET", "jwt-signing-seed")
    get_settings.cache_clear()

    runtime_dir_a = tmp_path / "runtime-a"
    runtime_dir_b = tmp_path / "runtime-b"

    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(runtime_dir_a))
    license_mod = _reload_runtime_license()
    token_a = _issue_license_jwt(
        device_id="device-runtime-dir-a",
        api_key_prefix="de_live_test",
        plan="developer",
        device_limit=5,
        org_id="org_test",
    )
    license_mod._save_license(token_a)

    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(runtime_dir_b))
    token_b = _issue_license_jwt(
        device_id="device-runtime-dir-b",
        api_key_prefix="de_live_test",
        plan="developer",
        device_limit=5,
        org_id="org_test",
    )
    license_mod._save_license(token_b)

    assert license_mod._load_raw_token(runtime_dir_a) == token_a
    assert license_mod._load_raw_token(runtime_dir_b) == token_b
    assert license_mod._load_raw_token() == token_b

    get_settings.cache_clear()


def test_stored_offline_entitlement_tracks_active_runtime_dir_without_reload(
    monkeypatch,
    tmp_path,
):
    # plan="developer" is Codna-style, the one product still verifying HS256 by design.
    monkeypatch.setenv("ALGENTA_RUNTIME_PRODUCT", "codna")
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET", "jwt-signing-seed")
    get_settings.cache_clear()

    runtime_dir_a = tmp_path / "runtime-a"
    runtime_dir_b = tmp_path / "runtime-b"

    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(runtime_dir_a))
    license_mod = _reload_runtime_license()
    token = _issue_license_jwt(
        device_id="device-runtime-dir-a",
        api_key_prefix="de_live_test",
        plan="developer",
        device_limit=5,
        org_id="org_test",
        api_key_expires_at=datetime.now(UTC) + timedelta(days=730),
    )
    license_mod._save_license(token)

    assert license_mod.stored_offline_execution_entitlement() is True

    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(runtime_dir_b))
    assert license_mod.stored_offline_execution_entitlement() is False

    get_settings.cache_clear()


# ── P0: v2 product/capacity license schema ──────────────────────────────────


def test_parse_v2_license_carries_product_and_capacity_claims(monkeypatch):
    monkeypatch.setenv("ALGENTA_REQUIRE_LOCAL_LICENSE", "1")
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    private_key, public_key = _rsa_keypair()
    monkeypatch.setenv("ALGENTA_LOCAL_LICENSE_PUBLIC_KEY", public_key)

    token = importlib.import_module("jwt").encode(
        {
            "api_key_prefix": "offline",
            "device_id": "device-v2",
            "plan": "enterprise",
            "issued_at": 1_900_000_000,
            "expires_at": 1_999_999_999,
            "key_expires_at": 1_999_999_999,
            "grace_days": 14,
            "iss": "algenta-offline-license",
            "sub": "device-license",
            "ver": 2,
            "org_id": "org_test",
            "license_id": "lic_test",
            "activation_id": "act_test",
            "entitlement_version": 7,
            "deployment_class": "server",
            "device_pubkey_thumbprint": "thumb123",
            "products": {
                "codna": {"tier": "pro", "features": ["repo_graph", "triage"]},
                "cohenta": {"tier": "team", "features": ["campaigns"]},
            },
            "named_seat_limit": 25,
            "active_node_limit": 3,
            "concurrent_worker_limit": 12,
            "device_allowance_per_seat": 3,
            "commercial_use": True,
            "redistribution_allowed": False,
            "offline_grace_days": 3,
        },
        private_key,
        algorithm="RS256",
    )

    parsed = _reload_runtime_license()._parse_token(token, "")
    assert parsed is not None and parsed.valid is True
    assert parsed.license_version == 2
    assert parsed.org_id == "org_test"
    assert parsed.activation_id == "act_test"
    assert parsed.entitlement_version == 7
    assert parsed.deployment_class == "server"
    assert parsed.device_pubkey_thumbprint == "thumb123"
    assert parsed.named_seat_limit == 25
    assert parsed.active_node_limit == 3
    assert parsed.concurrent_worker_limit == 12 and parsed.worker_limit() == 12
    assert parsed.device_allowance_per_seat == 3
    assert parsed.commercial_use is True and parsed.redistribution_allowed is False
    assert parsed.offline_grace_days == 3
    # product gating: granted → allowed; absent under a v2 license → denied
    assert parsed.has_product("codna") is True
    assert parsed.product_tier("codna") == "pro"
    assert parsed.product_features("codna") == frozenset({"repo_graph", "triage"})
    assert parsed.has_product("cohenta") is True
    assert parsed.has_product("decimas") is False
    assert parsed.product_features("decimas") == frozenset()

    get_settings.cache_clear()



def test_offline_issuer_emits_v2_product_and_capacity_claims():
    import importlib.util
    from pathlib import Path as _Path

    spec = importlib.util.spec_from_file_location(
        "_issue_offline_license_under_test",
        _Path(__file__).resolve().parents[1] / "scripts" / "issue_offline_license.py",
    )
    issuer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(issuer)

    args = issuer._build_parser().parse_args(
        [
            "--device-id", "device-x",
            "--plan", "enterprise",
            "--output", "/dev/null",
            "--deployment-class", "server",
            "--product-entitlement", "codna:pro:repo_graph,triage,apply",
            "--active-node-limit", "3",
            "--concurrent-worker-limit", "12",
            "--commercial-use",
        ]
    )
    claims = issuer._build_claims(args)
    assert claims["ver"] == 2
    assert claims["deployment_class"] == "server"
    assert claims["active_node_limit"] == 3
    assert claims["concurrent_worker_limit"] == 12
    assert claims["commercial_use"] is True
    assert claims["products"]["codna"]["tier"] == "pro"
    assert claims["products"]["codna"]["features"] == ["repo_graph", "triage", "apply"]

    # round-trip the issued claims through the runtime parser → DeviceLicense
    runtime_license = importlib.import_module("apps.runtime.license")
    lic = runtime_license._device_license_from_payload(
        claims, source="offline-local", api_key="", default_plan="enterprise"
    )
    assert lic.license_version == 2
    assert lic.has_product("codna")
    assert lic.product_features("codna") == frozenset({"repo_graph", "triage", "apply"})
