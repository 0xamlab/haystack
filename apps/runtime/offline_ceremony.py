"""Air-gapped licensing ceremony — the request half (node-side).

For a fully offline deployment the node generates a signed REQUEST file (this module), an operator
carries it out to the vendor portal, and the portal mints a RESPONSE (the signed deployment
license bound to the request's device key — see ``scripts/issue_offline_response.py``). The node
then loads the response like any offline license (``ALGENTA_LICENSE_JWT``).

This module is runtime-safe (no control-plane / api_server imports): it only BUILDS and PARSES the
request document. The request carries the device-key thumbprint the response must bind to, the
measured capacity + host evidence (so the operator can right-size + fraud-review), and a nonce
(anti-replay). It is not a license and grants nothing.
"""
from __future__ import annotations

import json
from typing import Any

OFFLINE_REQUEST_VERSION = 1
_REQUIRED_FIELDS = (
    "algenta_offline_request",
    "product",
    "deployment_id",
    "device_pubkey_thumbprint",
    "requested_units",
    "nonce",
)


class OfflineRequestError(ValueError):
    """The offline request document is malformed or missing required fields."""


def build_offline_request(
    *,
    product: str,
    deployment_id: str,
    device_pubkey_thumbprint: str,
    requested_units: int,
    nonce: str,
    generated_at: int,
    effective_vcpu: float = 0.0,
    host_evidence: dict[str, Any] | None = None,
    org_id: str = "",
    runtime_version: str = "",
) -> dict[str, Any]:
    """Build the offline request document (a plain dict; the CLI serializes it to JSON)."""
    if not product or not deployment_id:
        raise OfflineRequestError("product and deployment_id are required")
    if not device_pubkey_thumbprint:
        raise OfflineRequestError("device_pubkey_thumbprint is required (the response binds to it)")
    if requested_units < 1:
        raise OfflineRequestError("requested_units must be >= 1")
    if not nonce:
        raise OfflineRequestError("nonce is required (anti-replay)")
    return {
        "algenta_offline_request": OFFLINE_REQUEST_VERSION,
        "org_id": org_id,
        "product": product,
        "deployment_id": deployment_id,
        "device_pubkey_thumbprint": device_pubkey_thumbprint,
        "requested_units": int(requested_units),
        "effective_vcpu": float(effective_vcpu),
        "host_evidence": host_evidence or {},
        "nonce": nonce,
        "generated_at": int(generated_at),
        "runtime_version": runtime_version,
    }


def parse_offline_request(data: dict[str, Any] | str) -> dict[str, Any]:
    """Validate + normalize an offline request document (from a dict or JSON string). Raises
    :class:`OfflineRequestError` on any missing/invalid field."""
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, ValueError) as exc:
            raise OfflineRequestError("request is not valid JSON") from exc
    if not isinstance(data, dict):
        raise OfflineRequestError("request must be a JSON object")
    missing = [f for f in _REQUIRED_FIELDS if not data.get(f)]
    if missing:
        raise OfflineRequestError(f"request missing required fields: {', '.join(missing)}")
    if int(data.get("algenta_offline_request", 0)) != OFFLINE_REQUEST_VERSION:
        raise OfflineRequestError("unsupported offline request version")
    if int(data.get("requested_units", 0)) < 1:
        raise OfflineRequestError("requested_units must be >= 1")
    return data
