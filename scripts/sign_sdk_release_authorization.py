"""Signs a release-authorization record for the public algenta-sdk repo.

This is the one artifact that lets `thyn-ai/algenta-sdk`'s release.yml verify
a version was actually approved by the engine repo's full private test suite,
without the engine repo ever running `npm publish`/`twine upload` itself. See
the approved SDK-repo extraction plan's Step 4 amendment for the full model.

Usage:
    python scripts/sign_sdk_release_authorization.py \\
        --version 1.2.0 \\
        --sdk-checkout /path/to/a/clean/checkout/of/thyn-ai/algenta-sdk/at/the/exact/commit \\
        --private-key-file /path/to/sdk_release_signing_private.pem \\
        --out release-authorization.json

The private key must NEVER be committed anywhere, in either repo. It lives
only as a GitHub Actions secret (SDK_RELEASE_SIGNING_PRIVATE_KEY) in this
(the engine) repo. Only the public half is embedded in algenta-sdk's
release.yml for verification.

The contract digest is computed from --sdk-checkout, not accepted as a raw
string argument, and must use the IDENTICAL algorithm as
algenta-sdk/scripts/verify_release_authorization.py's compute_contract_digest
(same file list, same order, same hashing approach) -- keep the two in sync
by hand if either changes; a signer/verifier disagreement here just looks
like every release being silently rejected, which is a bad way to discover it.

Canonical JSON note: the signed message is `json.dumps(payload, sort_keys=True,
separators=(",", ":"))`. This exact serialization (sorted keys, no whitespace)
must be reproduced byte-for-byte by the verifier -- confirmed cross-language
compatible with Node's `JSON.stringify(obj, Object.keys(obj).sort())` during
development, since either language could plausibly end up doing the verifying
or signing side of this depending on which workflow needs it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from base64 import b64encode
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

SDK_REPO = "thyn-ai/algenta-sdk"
SCHEMA_VERSION = 1

# Must match algenta-sdk/scripts/verify_release_authorization.py's CONTRACT_FILES exactly.
CONTRACT_FILES = (
    "packages/python-sdk/decision_engine/_contract.py",
    "packages/ts-sdk/src/contract.ts",
)


def canonical_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_contract_digest(sdk_checkout: Path) -> str:
    """Must match algenta-sdk/scripts/verify_release_authorization.py's
    compute_contract_digest byte-for-byte: same file list, same order, same algorithm."""
    hasher = hashlib.sha256()
    for rel_path in CONTRACT_FILES:
        hasher.update((sdk_checkout / rel_path).read_bytes())
    return hasher.hexdigest()


def git_head(repo_root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True, check=True
    ).stdout.strip()


def build_authorization(
    *, version: str, sdk_commit: str, contract_sha256: str, key_id: str
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "version": version,
        "sdk_repo": SDK_REPO,
        "sdk_commit": sdk_commit,
        "contract_sha256": contract_sha256,
        "signature_algorithm": "Ed25519",
        "key_id": key_id,
        "authorized_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def sign(authorization: dict, private_key: Ed25519PrivateKey) -> str:
    signature = private_key.sign(canonical_bytes(authorization))
    return b64encode(signature).decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument(
        "--sdk-checkout",
        required=True,
        type=Path,
        help="Path to a clean checkout of thyn-ai/algenta-sdk at the exact commit being authorized "
        "(its git rev-parse HEAD becomes sdk_commit; its contract files are hashed for contract_sha256)",
    )
    parser.add_argument("--key-id", default="sdk-release-2026-08", help="Identifies which embedded public key to verify against, for future rotation")
    parser.add_argument("--private-key-file", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    private_key = load_pem_private_key(args.private_key_file.read_bytes(), password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise SystemExit(f"{args.private_key_file} is not an Ed25519 private key")

    sdk_commit = git_head(args.sdk_checkout)
    contract_sha256 = compute_contract_digest(args.sdk_checkout)

    authorization = build_authorization(
        version=args.version,
        sdk_commit=sdk_commit,
        contract_sha256=contract_sha256,
        key_id=args.key_id,
    )
    authorization["signature"] = sign(authorization, private_key)

    args.out.write_text(json.dumps(authorization, indent=2, sort_keys=True) + "\n")
    print(f"Wrote signed authorization for {args.version} @ {sdk_commit} to {args.out}")


if __name__ == "__main__":
    main()
