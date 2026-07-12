# Embedded public trust anchors

This directory holds the **public** RS256 verification keys the offline loader trusts. They are force-
included into the wheel (`pyproject.toml` → `artifacts = ["algenta/_keys/*_pub.pem", …]`) past the repo-wide
`*.pem` gitignore. Only `*_pub.pem` ever lives here — **never a private key**.

Two pinned public keys are committed here and packaged into every public release:

- `algenta_release_pub.pem` — verifies the **runtime manifest** signature (the native lib's integrity).
  The matching private key is the CI signing key (`ALGENTA_SIGNING_KEY` in build-runtime.yml).
- `algenta_license_pub.pem` — verifies the **offline license** (`products.algenta`). This MUST be the
  **shared platform license public key** — the same keypair the license-signer Worker + the OEM minter use
  (key continuity across codna/telys/algenta). See the licensing control-plane runbook.

Override for rotation / air-gapped operators: `ALGENTA_RELEASE_PUBKEY[_FILE]` / `ALGENTA_LICENSE_PUBKEY[_FILE]`.

Tests supply ephemeral keys via those env overrides, so the suite runs without the real keys present.
