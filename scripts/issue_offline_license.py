#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import jwt


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
    return parser


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
    return {
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
        "ver": 1,
        "message": args.message,
    }


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        private_key = _read_private_key(args.private_key_file)
        claims = _build_claims(args)
        token = jwt.encode(claims, private_key, algorithm="RS256")
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"{token}\n", encoding="utf-8")
        try:
            output_path.chmod(0o600)
        except OSError:
            pass
        sys.stdout.write(
            json.dumps(
                {
                    "status": "ok",
                    "output": str(output_path),
                    "device_id": args.device_id,
                    "plan": args.plan,
                    "algorithm": "RS256",
                }
            )
            + "\n"
        )
        return 0
    except Exception as exc:
        sys.stderr.write(f"{exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
