"""sync_sidecar — the repository API request path calling the agent synchronously.

A long agent/sidecar run must never execute on the request path; the API must
enqueue a worker job and return 202. This guard scans the request-path chain for
direct ``run_agent(...)`` calls, ``urlopen``, or blocking httpx. Wave B2 deletes the
baseline so this becomes fatal everywhere (the no-sync-sidecar regression gate)."""

from __future__ import annotations

import re
from pathlib import Path

from .._base import Guard, Violation

_FILES = (
    "apps/api_server/routers/repositories.py",
    "apps/api_server/services/repository_intelligence_verified_agentic.py",
    "apps/api_server/services/repository_intelligence_pipeline.py",
)
# a SYNCHRONOUS run_agent call (not its def, and not an awaited async call), urlopen,
# or a blocking httpx client/call. `await run_agent(...)` is the correct async path (B2)
# and is intentionally allowed.
_RE = re.compile(
    r"(?<!def )(?<!await )\brun_agent\s*\(|\burllib\.request\.urlopen\b|\bhttpx\.(?:Client|get|post)\b"
)


def _scan(root: Path) -> list[Violation]:
    out: list[Violation] = []
    for rel in _FILES:
        p = root / rel
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            if _RE.search(line):
                out.append(Violation("sync_sidecar", rel, line.strip()))
    return out


GUARD = Guard(
    name="sync_sidecar",
    description="repository API request path calling the agent/sidecar synchronously",
    scan=_scan,
    fix_wave="B2",
    baselined=False,  # B2: fatal — any synchronous sidecar call on the request path fails
)
