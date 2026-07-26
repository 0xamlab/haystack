#!/usr/bin/env python3
"""Air-gap ceremony, step 2 (operator/portal-side): mint the RESPONSE for an offline request.

Reads the request JSON generated on the node, and mints a strict-profile deployment license bound
to the request's device-key thumbprint, carrying the APPROVED Compute-Unit ceiling (defaults to the
requested amount; the operator may cap it). Writes the response (the signed license) to carry back
into the air gap, where the node loads it via ``ALGENTA_LICENSE_JWT``.

    python3 scripts/issue_offline_response.py --request request.json \\
        --private-key-file control-plane.pem --org-id org-acme --output response.jwt

The response is a normal deployment license (RS256, strict profile) — the runtime verifies it with
its public key and enforces the device binding + Compute-Unit ceiling offline.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apps.runtime.offline_ceremony import OfflineRequestError, parse_offline_request  # noqa: E402


def _read_private_key(path_value: str) -> str:
    path = Path(path_value).expanduser()
    if not path.is_file():
        raise ValueError(f"private key file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def main() -> int:
    p = argparse.ArgumentParser(description="Mint the offline license response for a request.")
    p.add_argument("--request", required=True, help="Path to the node's request JSON.")
    p.add_argument("--private-key-file", required=True, help="Control-plane RS256 signing key (PEM).")
    p.add_argument("--org-id", required=True)
    p.add_argument("--output", required=True, help="Path to write the signed response license.")
    p.add_argument("--approved-units", type=int, default=0,
                   help="Units to grant (0 = honor the requested amount; may cap it lower).")
    p.add_argument("--ttl-days", type=int, default=365)
    p.add_argument("--kid", default="")
    args = p.parse_args()

    try:
        request = parse_offline_request(Path(args.request).expanduser().read_text(encoding="utf-8"))
    except (OfflineRequestError, OSError) as exc:
        sys.stderr.write(f"invalid request: {exc}\n")
        return 2

    product = str(request["product"])
    approved = int(args.approved_units) or int(request["requested_units"])
    if approved < 1:
        sys.stderr.write("approved units must be >= 1\n")
        return 2

    # Resolve the server entitlement for the product at the approved unit ceiling, then mint a
    # deployment license bound to the request's device thumbprint.
    from apps.api_server.services.entitlement_service import resolve_entitlement, to_license_claims
    from apps.runtime.license import mint_deployment_token

    record = resolve_entitlement(f"{product}_server", overrides={"max_concurrent_units": approved})
    if not record.is_deployment_scope():
        sys.stderr.write(f"product {product!r} has no server (deployment) entitlement tier\n")
        return 2
    claims = to_license_claims(record)

    token = mint_deployment_token(
        org_id=args.org_id,
        product=product,
        edition="server",
        deployment_id=str(request["deployment_id"]),
        license_claims=claims,
        device_pubkey_thumbprint=str(request["device_pubkey_thumbprint"]),
        ttl_days=int(args.ttl_days),
        kid=args.kid,
        private_key_pem=_read_private_key(args.private_key_file),
    )
    out = Path(args.output).expanduser()
    out.write_text(f"{token}\n", encoding="utf-8")
    try:
        out.chmod(0o600)
    except OSError:
        pass
    sys.stdout.write(json.dumps({
        "status": "ok", "output": str(out), "product": product,
        "deployment_id": request["deployment_id"], "approved_units": approved,
        "bound_thumbprint": request["device_pubkey_thumbprint"],
    }) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
