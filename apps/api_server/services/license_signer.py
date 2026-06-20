"""Pluggable license signing (P1 of the licensing control plane).

The control plane issues device licenses. To keep the private signing key OUT of
the application / Fly secrets, signing is pluggable via ``license_signer_backend``:

- ``dev_hmac``  — HS256 with a shared secret. The legacy single-node behavior; the
                  default so existing deployments are unchanged until configured.
- ``pem``       — RS256 with a configured RSA private key. For operator / air-gapped
                  issuance (the key lives on an operator box, never on Fly).
- ``cf_worker`` — delegate signing to a restricted Cloudflare Worker that holds the
                  private key and enforces issuance policy. The application holds only
                  a service token to call the Worker — never the private key. This is
                  the launch posture for the hosted control plane (the Worker itself +
                  its policy enforcement + JWKS/CRL publication are deployed in P4).

The runtime verifier already enforces RS256-only when a local license is required
(``apps/runtime/license.py`` skips the HS256 branch in strict mode), so switching the
backend to ``pem``/``cf_worker`` is what makes production licenses asymmetrically signed.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Protocol

import jwt


class LicenseSignerError(Exception):
    """Raised when a signer is misconfigured or signing fails."""


class LicenseSigner(Protocol):
    backend: str

    def sign(self, claims: dict[str, Any]) -> str:
        """Return a compact signed JWT for the given claims."""
        ...


class DevHmacSigner:
    """HS256 with a shared secret — dev / single-node control plane only."""

    backend = "dev_hmac"

    def __init__(self, secret: str) -> None:
        if not secret:
            raise LicenseSignerError("dev_hmac signer requires a non-empty secret")
        self._secret = secret

    def sign(self, claims: dict[str, Any]) -> str:
        return jwt.encode(claims, self._secret, algorithm="HS256")


class LocalPemSigner:
    """RS256 with a locally-held RSA private key (operator / air-gapped issuance)."""

    backend = "pem"

    def __init__(self, private_key_pem: str, *, kid: str = "") -> None:
        if not private_key_pem:
            raise LicenseSignerError("pem signer requires an RSA private key")
        self._key = private_key_pem
        self._kid = kid

    def sign(self, claims: dict[str, Any]) -> str:
        headers = {"kid": self._kid} if self._kid else None
        return jwt.encode(claims, self._key, algorithm="RS256", headers=headers)


class CloudflareWorkerSigner:
    """Delegate signing to a restricted Cloudflare Worker that holds the private key.

    The application never sees the private key: it POSTs the claims + a service token
    and receives a compact RS256 JWS. The Worker is responsible for enforcing issuance
    policy (caps ≤ entitlement, known products/features, monotonic entitlement_version,
    unique jti, idempotent issuance, audit) — built + deployed in P4.
    """

    backend = "cf_worker"

    def __init__(self, sign_url: str, auth_token: str, *, timeout: float = 10.0) -> None:
        if not sign_url or not auth_token:
            raise LicenseSignerError("cf_worker signer requires sign_url + auth_token")
        self._url = sign_url
        self._token = auth_token
        self._timeout = timeout

    def sign(self, claims: dict[str, Any]) -> str:
        # Route through the approved egress wrapper (SSRF/egress fail-closed boundary) —
        # never raw urllib/httpx (enforced by scripts.reliability_guards). The signer
        # endpoint is Algenta-owned control-plane infra.
        from apps.api_server.services import egress_guard

        try:
            resp = egress_guard.sync_http_request(
                method="POST",
                url=self._url,
                surface="license_signer",
                egress_class="algenta_cloud",
                explicit_configured=True,
                headers={
                    "content-type": "application/json",
                    "authorization": f"Bearer {self._token}",
                },
                json={"claims": claims},
                client_kwargs={"timeout": self._timeout},
            )
        except egress_guard.EgressPolicyDeniedError as exc:
            raise LicenseSignerError(
                f"license signer egress denied: {exc.decision.reason}"
            ) from exc
        except Exception as exc:  # noqa: BLE001 — transport/timeout
            raise LicenseSignerError(f"license signer unreachable: {exc}") from exc
        if resp.status_code >= 400:
            raise LicenseSignerError(
                f"license signer rejected request: HTTP {resp.status_code}"
            )
        try:
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise LicenseSignerError("license signer returned invalid JSON") from exc
        token = payload.get("token") if isinstance(payload, dict) else None
        if not isinstance(token, str) or not token:
            raise LicenseSignerError("license signer returned no token")
        return token


def dev_hmac_secret(settings: Any) -> str:
    """The HS256 license secret (same derivation as device_service._get_license_secret)."""
    secret = getattr(settings, "license_signing_secret", None)
    if secret:
        return str(secret)
    return hashlib.sha256((settings.jwt_secret + ":license-signing").encode()).hexdigest()


def _read_private_key_pem(settings: Any) -> str:
    pem = getattr(settings, "license_signing_private_key", None)
    if pem:
        return str(pem)
    path_value = getattr(settings, "license_signing_private_key_file", None)
    if path_value:
        return Path(str(path_value)).expanduser().read_text(encoding="utf-8")
    raise LicenseSignerError(
        "pem signer requires license_signing_private_key or license_signing_private_key_file"
    )


def get_license_signer() -> LicenseSigner:
    """Resolve the active signer from settings. Defaults to dev_hmac (legacy HS256)."""
    from apps.api_server.config import get_settings

    settings = get_settings()
    backend = (getattr(settings, "license_signer_backend", None) or "dev_hmac").strip().lower()
    if backend == "cf_worker":
        return CloudflareWorkerSigner(
            str(getattr(settings, "license_signer_url", "") or ""),
            str(getattr(settings, "license_signer_auth_token", "") or ""),
        )
    if backend == "pem":
        return LocalPemSigner(
            _read_private_key_pem(settings),
            kid=str(getattr(settings, "license_signer_kid", "") or ""),
        )
    if backend not in ("dev_hmac", ""):
        raise LicenseSignerError(f"unknown license_signer_backend: {backend!r}")
    return DevHmacSigner(dev_hmac_secret(settings))
