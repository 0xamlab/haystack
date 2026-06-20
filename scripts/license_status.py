#!/usr/bin/env python3
"""Report the installed Algenta license — the P5.1 "active + v2" gate.

Before any irreversible fail-closed flip (P5.3–P5.7), every internal deployment
(Mission / Codna / Cohenta / CI / …) must already carry a valid v2 license. Run
this on each machine and confirm it prints ``OK`` (exit 0) before flipping a
deployment's ``ALGENTA_ENFORCE_LICENSE_VALIDATION`` / removing the env bypass.

Reads the installed token (``~/.algenta/runtime/license.jwt`` by default) via the
same ``load_license`` path the runtime uses — so this verifies exactly what the
engine would see. No secrets, no network, no mutation.

    python3 scripts/license_status.py            # human-readable, exit 0 iff valid+v2
    python3 scripts/license_status.py --json      # machine-readable
    python3 scripts/license_status.py --allow-v1  # don't fail on a valid v1 token

Exit codes: 0 = gate satisfied · 1 = not satisfied (invalid / expired / v1 when v2 required).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _gather() -> dict[str, object]:
    from apps.runtime.license import load_license

    api_key = os.environ.get("ALGENTA_API_KEY", "") or os.environ.get("DE_API_KEY", "")
    lic = load_license(api_key)
    return {
        "valid": bool(lic.valid),
        "license_version": int(lic.license_version),
        "is_v2": lic.license_version >= 2,
        "source": lic.source,
        "plan": lic.plan,
        "message": lic.message,
        "deployment_class": lic.deployment_class,
        "org_id": lic.org_id,
        "license_id": lic.license_id,
        "activation_id": lic.activation_id,
        "entitlement_version": lic.entitlement_version,
        "expires_at": lic.expires_at,
        "is_expired": lic.is_expired(),
        "is_in_grace": lic.is_in_grace(),
        "is_hard_expired": lic.is_hard_expired(),
        "grace_days": lic.grace_days,
        "offline_grace_days": lic.offline_grace_days,
        "commercial_use": lic.commercial_use,
        "named_seat_limit": lic.named_seat_limit,
        "active_node_limit": lic.active_node_limit,
        "concurrent_worker_limit": lic.concurrent_worker_limit,
        "products": {
            name: {"tier": ent.tier, "features": sorted(ent.features)}
            for name, ent in lic.products.items()
        },
    }


def _satisfied(info: dict[str, object], *, allow_v1: bool) -> bool:
    if not info["valid"]:
        return False
    if info["is_hard_expired"]:
        return False
    if not allow_v1 and not info["is_v2"]:
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--allow-v1", action="store_true", help="treat a valid v1 token as satisfying the gate"
    )
    args = parser.parse_args(argv)

    try:
        info = _gather()
    except Exception as exc:  # pragma: no cover - defensive
        if args.json:
            print(json.dumps({"valid": False, "error": str(exc)}))
        else:
            print(f"FAIL  could not load license: {exc}")
        return 1

    ok = _satisfied(info, allow_v1=args.allow_v1)

    if args.json:
        print(json.dumps({**info, "gate_satisfied": ok}, indent=2, sort_keys=True))
        return 0 if ok else 1

    status = "OK" if ok else "FAIL"
    print(f"{status}  license valid={info['valid']} version={info['license_version']} "
          f"source={info['source']} plan={info['plan']}")
    if info["deployment_class"]:
        print(f"      deployment_class={info['deployment_class']} "
              f"commercial_use={info['commercial_use']}")
    if info["products"]:
        for name, ent in info["products"].items():  # type: ignore[union-attr]
            print(f"      product {name}: tier={ent['tier']} features={','.join(ent['features'])}")
    print(f"      caps: seats={info['named_seat_limit']} nodes={info['active_node_limit']} "
          f"workers={info['concurrent_worker_limit']}")
    print(f"      expiry: expires_at={info['expires_at']} expired={info['is_expired']} "
          f"in_grace={info['is_in_grace']} hard_expired={info['is_hard_expired']}")
    if not ok:
        if not info["valid"]:
            print(f"      → not valid: {info['message'] or 'no installed license'}")
        elif info["is_hard_expired"]:
            print("      → past grace; runtime would block")
        elif not info["is_v2"]:
            print("      → legacy v1; mint+install a v2 license before the fail-closed flip")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
