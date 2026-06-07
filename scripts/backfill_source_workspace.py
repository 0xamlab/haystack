"""One-off backfill: stamp workspace_id onto legacy on-disk dataset registry entries (#6).

After workspace-partitioning the source_registry (data_visibility.dataset_visible now gates
by workspace), legacy entries with no workspace_id are INVISIBLE to a workspace-scoped caller.
A tenant that calls with X-Workspace-Id therefore sees an EMPTY dataset inventory until its
pre-migration datasets are stamped. This script stamps every unstamped entry for an org with a
target workspace_id (idempotent — entries that already carry a workspace_id are left untouched).

For Mission's company org, the connectors were already backfilled to the dev workspace
(00000000-0000-4000-8000-000000000001), so stamp the org's datasets to the same workspace.

Usage (from the decision-engine repo root, with the engine's .env / ALGENTA_SOURCES_DIR in env):
    uv run python scripts/backfill_source_workspace.py <org_id> <workspace_id> [--dry-run]

Example (Mission):
    uv run python scripts/backfill_source_workspace.py \
        33e71da5-057f-4bfa-8278-9fe0ca1a641b 00000000-0000-4000-8000-000000000001 --dry-run

Re-run without --dry-run to apply. Safe to run multiple times.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `apps...` importable when run as a standalone script (uvicorn gets this via cwd).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apps.api_server.services import source_registry as reg  # noqa: E402


def backfill(org_id: str, workspace_id: str, *, dry_run: bool) -> tuple[int, int]:
    entries = reg.list_sources(org_id)
    total = len(entries)
    stamped = 0
    for entry in entries:
        source_id = str(entry.get("id") or "")
        if not source_id:
            continue
        if entry.get("workspace_id"):
            continue  # already scoped — idempotent skip
        if dry_run:
            print(f"  [dry-run] would stamp {source_id} ({entry.get('name')!r}) -> ws {workspace_id}")
        else:
            reg.update_source_entry(org_id, source_id, {"workspace_id": workspace_id})
            print(f"  stamped {source_id} ({entry.get('name')!r}) -> ws {workspace_id}")
        stamped += 1
    return total, stamped


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    dry_run = "--dry-run" in argv
    if len(args) != 2:
        print(__doc__)
        return 2
    org_id, workspace_id = args[0], args[1]
    print(f"Backfilling org={org_id} -> workspace_id={workspace_id} (dry_run={dry_run})")
    total, stamped = backfill(org_id, workspace_id, dry_run=dry_run)
    verb = "would stamp" if dry_run else "stamped"
    print(f"Done: {total} entries scanned, {verb} {stamped} unstamped entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
