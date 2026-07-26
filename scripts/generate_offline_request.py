#!/usr/bin/env python3
"""Air-gap ceremony, step 1 (node-side): generate an offline license REQUEST file.

Run on the air-gapped deployment node. Collects the device-key thumbprint (the response binds to
it), the measured effective vCPU + host evidence (so the operator can right-size and fraud-review),
and a fresh nonce, then writes a request JSON to carry out to the vendor portal:

    python3 scripts/generate_offline_request.py --product algenta --deployment-id prod-us \\
        --requested-units 16 --output request.json

Grants nothing — it is a request, not a license. The operator mints the response with
``scripts/issue_offline_response.py``.
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apps.runtime.offline_ceremony import build_offline_request  # noqa: E402


def _device_thumbprint(explicit: str) -> str:
    if explicit:
        return explicit
    try:
        from apps.runtime.device_keypair import public_key_thumbprint

        return public_key_thumbprint()
    except Exception:  # noqa: BLE001 — allow explicit override on hosts without a keypair yet
        return ""


def _measured_vcpu() -> float:
    try:
        from apps.runtime.capacity import measure_effective_vcpu

        return measure_effective_vcpu().effective_vcpu
    except Exception:  # noqa: BLE001
        return 0.0


def _host_evidence() -> dict:
    try:
        from apps.runtime.host_class import collect_host_evidence

        ev = collect_host_evidence()
        return {
            "platform": ev.platform,
            "cloud_vendor": ev.cloud_vendor,
            "is_container": ev.is_container,
            "is_kubernetes": ev.is_kubernetes,
            "logical_cpu_count": ev.logical_cpu_count,
            "risk_signals": ev.risk_signals(),
        }
    except Exception:  # noqa: BLE001
        return {}


def main() -> int:
    p = argparse.ArgumentParser(description="Generate an air-gap offline license request.")
    p.add_argument("--product", required=True)
    p.add_argument("--deployment-id", required=True)
    p.add_argument("--requested-units", type=int, required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--org-id", default="")
    p.add_argument("--device-pubkey-thumbprint", default="",
                   help="Override the device key thumbprint (defaults to this node's key).")
    args = p.parse_args()

    thumb = _device_thumbprint(args.device_pubkey_thumbprint)
    if not thumb:
        sys.stderr.write("no device key thumbprint available; pass --device-pubkey-thumbprint\n")
        return 2

    request = build_offline_request(
        product=args.product,
        deployment_id=args.deployment_id,
        device_pubkey_thumbprint=thumb,
        requested_units=args.requested_units,
        nonce=secrets.token_hex(16),
        generated_at=int(time.time()),
        effective_vcpu=_measured_vcpu(),
        host_evidence=_host_evidence(),
        org_id=args.org_id,
    )
    out = Path(args.output).expanduser()
    out.write_text(json.dumps(request, indent=2), encoding="utf-8")
    sys.stdout.write(json.dumps({"status": "ok", "output": str(out),
                                 "device_pubkey_thumbprint": thumb}) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
