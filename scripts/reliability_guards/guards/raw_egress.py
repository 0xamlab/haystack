"""raw_egress — raw outbound HTTP/S3 calls outside the approved egress wrappers.

Every outbound call must route through egress_guard / storage_service /
connector_egress so the self-hosted/air-gapped fail-closed policy can enforce it.
Fixed by Wave B2 (the sidecar client) + Wave B10 (everything else)."""

from __future__ import annotations

import re
from pathlib import Path

from .._base import Guard, Violation, iter_py

_ALLOWED = {
    "apps/api_server/services/egress_guard.py",
    "apps/api_server/services/storage_service.py",
    "apps/api_server/services/connector_egress.py",
    # runtime plane's approved egress wrapper (enforce-before-dispatch); the SDK-transport-boundary
    # analogue of egress_guard — must not import the api_server egress_guard.
    "apps/runtime/privacy_guard.py",
}
# Hugging Face Space apps and their operator tooling (apps/spaces/**) are a separate deployment
# plane: they run on the Hub, not inside the self-hosted API, and talk to the Hub, our hosted API
# and inference providers by design -- the fail-closed egress policy of the api_server does not
# govern them (docs/spaces/README.md). Everything else under apps/ stays in scope.
_EXCLUDED_PREFIXES = ("apps/spaces/",)
_RE = re.compile(
    r"\b("
    r"httpx\.(?:get|post|put|delete|patch|stream|request|Client|AsyncClient)"
    r"|urllib\.request\.(?:urlopen|Request)"
    r"|requests\.(?:get|post|put|delete|patch|head|request|Session)"
    r"|boto3\.(?:client|resource)"
    r")\b"
)
_IMPORT_REQUESTS = re.compile(r"^\s*import\s+requests\b")


def _scan(root: Path) -> list[Violation]:
    out: list[Violation] = []
    for p in iter_py(root, "apps"):
        rel = p.relative_to(root).as_posix()
        if rel in _ALLOWED or rel.startswith(_EXCLUDED_PREFIXES):
            continue
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            if _RE.search(line) or _IMPORT_REQUESTS.search(line):
                out.append(Violation("raw_egress", rel, line.strip()))
    return out


GUARD = Guard(
    name="raw_egress",
    description=(
        "raw httpx/urllib/requests/boto3 outside egress_guard/storage_service/connector_egress"
    ),
    scan=_scan,
    fix_wave="B2/B10",
)
