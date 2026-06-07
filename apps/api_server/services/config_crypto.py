"""Envelope encryption for connector ``config_json`` at rest.

Connector configs hold credentials (DSNs, passwords, tokens). They were stored as
plaintext JSON. This module encrypts them with AES-256-GCM, AAD-bound to the owning
org, and provides a deterministic fingerprint for create-or-reuse dedupe (random-IV
ciphertext can't be equality-matched).

Backward-compatible + opt-in:
  - Encryption is ON only when ALGENTA_CONFIG_ENCRYPTION_KEY is set (64-hex or any
    passphrase). When unset, writes store plaintext and reads pass through — so the
    feature can be rolled out without touching existing rows.
  - decrypt() detects the ``enc:v1:`` prefix: encrypted values are decrypted;
    legacy plaintext values are returned unchanged. So existing plaintext rows keep
    working after the key is set, and a re-encrypt backfill can run later.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import uuid
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_ENC_PREFIX = "enc:v1:"
_GCM_IV_BYTES = 12
_HEX64 = set("0123456789abcdefABCDEF")


def _kek() -> bytes | None:
    raw = (os.environ.get("ALGENTA_CONFIG_ENCRYPTION_KEY") or "").strip()
    if not raw:
        return None
    if len(raw) == 64 and all(c in _HEX64 for c in raw):
        return bytes.fromhex(raw)
    return hashlib.sha256(raw.encode()).digest()


def is_config_encryption_enabled() -> bool:
    """True when a config-encryption key is configured."""
    return _kek() is not None


def is_encrypted(value: str | None) -> bool:
    return bool(value) and value.startswith(_ENC_PREFIX)


def _aad(org_id: uuid.UUID | str) -> bytes:
    return f"data_connector:{org_id}".encode()


def config_fingerprint(config: dict[str, Any] | None) -> str:
    """Deterministic dedupe key for a connector config (HMAC-free SHA-256 of the
    canonical JSON). Stable regardless of whether encryption is enabled, so
    create-or-reuse keeps deduping across the rollout."""
    canonical = json.dumps(config or {}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def encrypt_config_json(plaintext: str | None, *, org_id: uuid.UUID | str) -> str | None:
    """Encrypt a config_json string for storage. No-op (returns plaintext) when the
    key is unset, so behavior is unchanged until encryption is enabled."""
    if plaintext is None:
        return None
    kek = _kek()
    if kek is None:
        return plaintext
    iv = os.urandom(_GCM_IV_BYTES)
    ct = AESGCM(kek).encrypt(iv, plaintext.encode(), _aad(org_id))
    return _ENC_PREFIX + base64.b64encode(iv + ct).decode()


def decrypt_config_json(value: str | None, *, org_id: uuid.UUID | str) -> str | None:
    """Decrypt a stored config_json value. Legacy plaintext (no enc prefix) is
    returned unchanged. Raises if an encrypted value is found but no key is set."""
    if value is None or not value.startswith(_ENC_PREFIX):
        return value
    kek = _kek()
    if kek is None:
        raise RuntimeError(
            "connector config_json is encrypted but ALGENTA_CONFIG_ENCRYPTION_KEY is not set"
        )
    blob = base64.b64decode(value[len(_ENC_PREFIX):])
    iv, ct = blob[:_GCM_IV_BYTES], blob[_GCM_IV_BYTES:]
    return AESGCM(kek).decrypt(iv, ct, _aad(org_id)).decode()


# ── JSON-column variants (for CapabilityBinding.config_json / auth_state_json) ──
# These columns are JSON (dict). We keep the column type by storing the ciphertext
# inside a one-key envelope dict {"__enc__": "<enc:v1:...>"}. A plain dict with no
# "__enc__" key is legacy plaintext → returned as-is.
_ENC_DICT_KEY = "__enc__"


def encrypt_config_dict(
    value: dict[str, Any] | None, *, org_id: uuid.UUID | str
) -> dict[str, Any] | None:
    """Encrypt a dict for storage in a JSON column. No-op when the key is unset."""
    if value is None or not value:
        return value
    kek = _kek()
    if kek is None:
        return value
    plaintext = json.dumps(value, sort_keys=True, separators=(",", ":"))
    iv = os.urandom(_GCM_IV_BYTES)
    ct = AESGCM(kek).encrypt(iv, plaintext.encode(), _aad(org_id))
    return {_ENC_DICT_KEY: _ENC_PREFIX + base64.b64encode(iv + ct).decode()}


def decrypt_config_dict(
    value: dict[str, Any] | None, *, org_id: uuid.UUID | str
) -> dict[str, Any] | None:
    """Decrypt a JSON-column dict. Legacy plain dicts (no envelope key) pass through."""
    if not isinstance(value, dict) or _ENC_DICT_KEY not in value:
        return value
    kek = _kek()
    if kek is None:
        raise RuntimeError(
            "capability binding config is encrypted but ALGENTA_CONFIG_ENCRYPTION_KEY is not set"
        )
    enc = value[_ENC_DICT_KEY]
    blob = base64.b64decode(enc[len(_ENC_PREFIX):])
    iv, ct = blob[:_GCM_IV_BYTES], blob[_GCM_IV_BYTES:]
    return json.loads(AESGCM(kek).decrypt(iv, ct, _aad(org_id)).decode())
