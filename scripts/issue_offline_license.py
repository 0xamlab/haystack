#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import jwt

# The anti-fleet-abuse guardrail lives next to this script (pure stdlib). Import it whether this file is run
# as ``python scripts/issue_offline_license.py`` (sys.path[0] = scripts/) or imported as
# ``scripts.issue_offline_license`` (repo root on sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from scripts.license_mint_guard import (
        ACTIVE_NODE_CAP_ENFORCE_ENV,
        LicenseMintGuardError,
        assert_paid_selfhost_claims,
    )
except ImportError:  # run-as-script fallback (scripts/ dir on the path, not the repo root)
    from license_mint_guard import (  # type: ignore[no-redef]
        ACTIVE_NODE_CAP_ENFORCE_ENV,
        LicenseMintGuardError,
        assert_paid_selfhost_claims,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Issue an offline Algenta local license. This script signs license claims only "
            "and never reads customer data, schema data, or runtime payloads."
        )
    )
    parser.add_argument("--device-id", required=True, help="Target runtime device identifier.")
    parser.add_argument("--plan", required=True, help="License plan label, for example enterprise.")
    parser.add_argument("--output", required=True, help="Path to write the signed license JWT.")
    parser.add_argument(
        "--private-key-file",
        default=os.environ.get("ALGENTA_LOCAL_LICENSE_PRIVATE_KEY_FILE", "").strip(),
        help="PEM file containing the RSA private key used to sign the license.",
    )
    parser.add_argument("--api-key-prefix", default="", help="Display-only API key prefix claim.")
    parser.add_argument("--org-id", default="", help="Optional organization identifier claim.")
    parser.add_argument(
        "--device-limit",
        type=int,
        default=0,
        help="Device limit claim. Use 0 for unlimited.",
    )
    parser.add_argument(
        "--expires-at",
        type=int,
        default=0,
        help="Unix epoch expiry for the local entitlement. Use 0 for no expiry.",
    )
    parser.add_argument(
        "--key-expires-at",
        type=int,
        default=None,
        help="Unix epoch expiry for the underlying commercial key. Defaults to expires-at.",
    )
    parser.add_argument(
        "--grace-days",
        type=int,
        default=14,
        help="Offline grace period after expiry before hard block.",
    )
    parser.add_argument(
        "--permitted-module",
        action="append",
        default=[],
        help="Repeat to restrict permitted modules. Defaults to '*'.",
    )
    parser.add_argument(
        "--message",
        default="",
        help="Optional operator note embedded in the license payload.",
    )
    # ── v2 commercial-capacity + product entitlement claims (v2 is the only format) ──
    parser.add_argument("--license-id", default="", help="License identifier claim (v2).")
    parser.add_argument("--activation-id", default="", help="Per-device activation id claim (v2).")
    parser.add_argument(
        "--entitlement-version", type=int, default=0,
        help="Monotonic entitlement version (v2); signer rejects regressions.",
    )
    parser.add_argument(
        "--deployment-class", default="",
        help="v2: desktop | server | ci | airgapped | oem.",
    )
    parser.add_argument(
        "--device-pubkey-thumbprint", default="",
        help="v2: device public-key thumbprint to bind the license to.",
    )
    parser.add_argument(
        "--products-file", default="",
        help='v2: JSON file mapping {product: {"tier": str, "features": [str, ...]}}.',
    )
    parser.add_argument(
        "--product-entitlement", action="append", default=[],
        help="v2: repeatable 'product:tier:feat1,feat2' (alternative to --products-file).",
    )
    parser.add_argument("--named-seat-limit", type=int, default=0, help="v2 capacity claim.")
    parser.add_argument("--active-node-limit", type=int, default=0, help="v2 capacity claim.")
    parser.add_argument("--concurrent-worker-limit", type=int, default=0, help="v2 capacity claim.")
    parser.add_argument(
        "--device-allowance-per-seat", type=int, default=0, help="v2 capacity claim.",
    )
    parser.add_argument("--commercial-use", action="store_true", help="v2: commercial-use grant.")
    parser.add_argument(
        "--redistribution-allowed", action="store_true", help="v2: redistribution grant.",
    )
    parser.add_argument("--offline-grace-days", type=int, default=0, help="v2 offline grace claim.")
    # ── server/enterprise DEPLOYMENT scope (Compute Units) ──
    parser.add_argument(
        "--license-scope", default="device", choices=["device", "deployment"],
        help="v2: 'device' (personal) or 'deployment' (org server pool). deployment activates "
        "the Compute-Unit enforcement path.",
    )
    parser.add_argument("--deployment-id", default="", help="v2: deployment identity (deployment scope).")
    parser.add_argument(
        "--max-concurrent-units", type=int, default=0,
        help="v2: Compute-Unit pool ceiling (deployment scope). The enforceable server cap.",
    )
    parser.add_argument(
        "--max-effective-vcpu", type=int, default=0,
        help="v2: per-node workstation effective-vCPU ceiling (0 = unspecified).",
    )
    parser.add_argument(
        "--vcpu-per-unit", type=int, default=0,
        help="v2: measurement policy — effective vCPU per Compute Unit (0 = runtime default 4).",
    )
    parser.add_argument("--measurement-policy-version", default="", help="v2: names the vCPU→unit rules.")
    parser.add_argument("--grace-policy-id", default="", help="v2: names the lapse/grace/Community-floor policy.")
    parser.add_argument(
        "--paid-selfhost",
        action="store_true",
        help=(
            "Enforce the paid self-host anti-fleet-abuse guardrail before signing: reject OEM / "
            "redistribution / uncapped (all-zero-cap) claims, require commercial_use, and require an "
            "air-gapped mint to be device-bound with a finite worker cap. Use this for EVERY paying "
            "self-host customer so one license can't run across a whole fleet."
        ),
    )
    return parser


def _parse_products(args: argparse.Namespace) -> dict[str, dict[str, object]]:
    """Build the v2 ``products`` blob from --products-file and/or --product-entitlement."""
    products: dict[str, dict[str, object]] = {}
    if args.products_file:
        data = json.loads(Path(args.products_file).expanduser().read_text(encoding="utf-8"))
        if isinstance(data, dict):
            for name, spec in data.items():
                if isinstance(spec, dict):
                    feats = [str(f) for f in (spec.get("features") or []) if str(f).strip()]
                    products[str(name)] = {"tier": str(spec.get("tier", "")), "features": feats}
    for entry in args.product_entitlement:
        parts = entry.split(":", 2)
        if len(parts) < 2 or not parts[0]:
            raise ValueError(
                f"--product-entitlement must be 'product:tier[:feat1,feat2]', got: {entry}"
            )
        feats = [f.strip() for f in (parts[2].split(",") if len(parts) == 3 else []) if f.strip()]
        products[parts[0]] = {"tier": parts[1], "features": feats}
    return products


def _read_private_key(path_value: str) -> str:
    if not path_value:
        raise ValueError(
            "--private-key-file is required or ALGENTA_LOCAL_LICENSE_PRIVATE_KEY_FILE must be set."
        )
    path = Path(path_value).expanduser()
    if not path.is_file():
        raise ValueError(f"Private key file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def _build_claims(args: argparse.Namespace) -> dict[str, object]:
    issued_at = int(time.time())
    expires_at = max(0, int(args.expires_at))
    key_expires_at = expires_at if args.key_expires_at is None else max(0, int(args.key_expires_at))
    permitted_modules = args.permitted_module if args.permitted_module else ["*"]
    claims: dict[str, object] = {
        "api_key_prefix": args.api_key_prefix,
        "device_id": args.device_id,
        "plan": args.plan,
        "device_limit": max(0, int(args.device_limit)),
        "org_id": args.org_id,
        "permitted_modules": permitted_modules,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "key_expires_at": key_expires_at,
        "grace_days": max(0, int(args.grace_days)),
        "iss": "algenta-offline-license",
        "sub": "device-license",
        "ver": 2,
        "message": args.message,
        "license_id": args.license_id,
        "activation_id": args.activation_id,
        "entitlement_version": max(0, int(args.entitlement_version)),
        "deployment_class": args.deployment_class,
        "device_pubkey_thumbprint": args.device_pubkey_thumbprint,
        "products": _parse_products(args),
        "named_seat_limit": max(0, int(args.named_seat_limit)),
        "active_node_limit": max(0, int(args.active_node_limit)),
        "concurrent_worker_limit": max(0, int(args.concurrent_worker_limit)),
        "device_allowance_per_seat": max(0, int(args.device_allowance_per_seat)),
        "commercial_use": bool(args.commercial_use),
        "redistribution_allowed": bool(args.redistribution_allowed),
        "offline_grace_days": max(0, int(args.offline_grace_days)),
    }
    # Server/enterprise deployment-scope claims — emitted only for deployment scope so device
    # licenses keep their exact claim shape.
    if str(getattr(args, "license_scope", "device")) == "deployment":
        claims["license_scope"] = "deployment"
        claims["deployment_id"] = args.deployment_id
        claims["max_concurrent_units"] = max(0, int(args.max_concurrent_units))
        if int(args.max_effective_vcpu) > 0:
            claims["max_effective_vcpu"] = int(args.max_effective_vcpu)
        if int(args.vcpu_per_unit) > 0:
            claims["vcpu_per_unit"] = int(args.vcpu_per_unit)
        if args.measurement_policy_version:
            claims["measurement_policy_version"] = args.measurement_policy_version
        if args.grace_policy_id:
            claims["grace_policy_id"] = args.grace_policy_id
    return claims


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        private_key = _read_private_key(args.private_key_file)
        claims = _build_claims(args)
        if args.paid_selfhost:
            # A paid, metered self-host license must lapse so it's renewal-gated — a perpetual
            # (no-expiry) paid license re-opens "pay once and leave". Enforce a finite expiry at
            # the ISSUANCE layer (the entitlement-claims guard stays expiry-agnostic).
            if int(args.expires_at) <= 0:
                raise LicenseMintGuardError(
                    "paid self-host mint rejected: --expires-at must be a finite future epoch "
                    "(a perpetual paid license never lapses / is not renewal-gated)."
                )
            # Fails closed (raises) if these claims would be an abusable paid self-host license.
            assert_paid_selfhost_claims(claims)
        token = jwt.encode(claims, private_key, algorithm="RS256")
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"{token}\n", encoding="utf-8")
        try:
            output_path.chmod(0o600)
        except OSError:
            pass
        result: dict[str, object] = {
            "status": "ok",
            "output": str(output_path),
            "device_id": args.device_id,
            "plan": args.plan,
            "algorithm": "RS256",
        }
        if args.paid_selfhost:
            result["paid_selfhost_guard"] = "passed"
            result["active_node_limit"] = int(args.active_node_limit)
            result["concurrent_worker_limit"] = int(args.concurrent_worker_limit)
            # Enforcement is deployment-side: the cap only binds when the customer runs with this on.
            result["reminder"] = (
                f"Connected self-host must run with {ACTIVE_NODE_CAP_ENFORCE_ENV}=1 for the active-node-cap "
                "to bind; otherwise the node count is not enforced."
            )
        sys.stdout.write(json.dumps(result) + "\n")
        return 0
    except LicenseMintGuardError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    except Exception as exc:
        sys.stderr.write(f"{exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
