"""B10: defense-in-depth secret redaction for persisted artifacts + structured logs.

Recursively replaces values whose KEY looks like a credential before an artifact is written
(object_store.put_json, incl. the S3 mirror) or a structured log is emitted — so a stray
auth header / API key / token never lands in a manifest, the object store, or the logs.

The key pattern is intentionally PRECISE, not the broad ``token`` substring the TS ``redactSecrets``
uses: repository-intelligence manifests legitimately carry count fields like ``token_estimate`` /
``raw_repo_token_estimate`` / ``evidence_bundle_token_count``, and a bare ``token`` match would
corrupt them. So secret-token keys are enumerated (``access_token`` / ``provider_token`` / …) and
bare ``token`` is NOT matched. It DOES catch the compound credential keys the anchored
``cline_proof_common.SECRET_FIELD_PATTERN`` (``^...$``) misses — ``x_api_key`` / ``engine_api_key`` /
``provider_api_key`` / ``authorization_header`` — via substring search. Covered by
tests/test_secret_redaction.py (both the must-redact and the must-NOT-corrupt sets)."""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[REDACTED]"

# Substring (unanchored) match on the KEY name. Enumerates credential shapes; deliberately omits a
# bare ``token`` (would hit token_estimate/token_count) — only secret-token NAMES are matched.
_SECRET_KEY = re.compile(
    r"(?:"
    r"api[_-]?key"  # api_key / apikey / x_api_key / engine_api_key / provider_api_key
    r"|access[_-]?token|refresh[_-]?token|auth[_-]?token|bearer[_-]?token"
    r"|id[_-]?token|provider[_-]?token|session[_-]?token|api[_-]?token"
    r"|secret"  # secret / client_secret / app_secret / secret_key
    r"|password|passwd|passphrase"
    r"|authorization"  # authorization / authorization_header
    r"|cookie"
    r"|private[_-]?key"
    r"|credential"
    r")",
    re.I,
)


def is_secret_key(key: str) -> bool:
    return bool(_SECRET_KEY.search(key))


def redact_secret_fields(value: Any) -> Any:
    """Return a copy of ``value`` with any dict entry whose key matches a credential name replaced
    by ``[REDACTED]``. Recurses into nested dicts/lists; scalars pass through unchanged. Pure (does
    not mutate the input)."""
    if isinstance(value, dict):
        return {
            k: (REDACTED if isinstance(k, str) and is_secret_key(k) else redact_secret_fields(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_secret_fields(v) for v in value]
    return value
