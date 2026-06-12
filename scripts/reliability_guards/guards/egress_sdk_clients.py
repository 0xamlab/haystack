"""egress_sdk_clients — non-httpx SDK clients constructed outside the approved egress wrappers.

The raw_egress guard's regex only matches httpx/urllib/requests/boto3, so it is structurally BLIND
to the connectors' PRIMARY transports: aiobotocore ``session.create_client`` (the default async S3
read path — boto3 is only the ImportError fallback), ``google.cloud.storage.Client``, azure
``Blob{Service,}Client``, neo4j ``GraphDatabase.driver``, ``asyncpg.connect``, and ``smtplib.SMTP``.
Those are fail-closed today only via manually-placed enforce_egress_sync /
enforce_connector_destination / enforce_neo4j_settings_egress / smtp_connection that raw_egress
cannot see — so a future edit dropping an enforce before one of them would exfiltrate with
raw_egress green. This sibling guard flags every such construction outside the approved wrapper
modules and baselines the current (manually-guarded) sites, so a NEW un-enforced SDK client fails
fatally. (Enforce-PRECEDES-construction for the known sites is pinned by
tests/test_egress_sdk_clients_guard.py.)"""

from __future__ import annotations

import re
from pathlib import Path

from .._base import Guard, Violation, iter_py

_ALLOWED = {
    "apps/api_server/services/egress_guard.py",
    "apps/api_server/services/storage_service.py",
    "apps/api_server/services/connector_egress.py",
    "apps/runtime/privacy_guard.py",
}
_RE = re.compile(
    r"(?:"
    r"\.create_client\("  # aiobotocore session.create_client (default async S3 path)
    r"|\bstorage\.Client\("  # google.cloud.storage
    r"|\bGraphDatabase\.driver\("  # neo4j
    r"|\basyncpg\.connect\("  # asyncpg
    r"|BlobServiceClient(?:\.from_connection_string)?\("  # azure (also AsyncBlobServiceClient)
    r"|BlobClient(?:\.from_connection_string)?\("  # azure
    r"|\bsmtplib\.SMTP\("  # direct smtp connection
    r")"
)


def _scan(root: Path) -> list[Violation]:
    out: list[Violation] = []
    for p in iter_py(root, "apps"):
        rel = p.relative_to(root).as_posix()
        if rel in _ALLOWED:
            continue
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            if _RE.search(line):
                out.append(Violation("egress_sdk_clients", rel, line.strip()))
    return out


GUARD = Guard(
    name="egress_sdk_clients",
    description=(
        "aiobotocore/GCS/Azure/neo4j/asyncpg/smtplib SDK clients outside the approved egress wrappers"
    ),
    scan=_scan,
    fix_wave="B10",
)
