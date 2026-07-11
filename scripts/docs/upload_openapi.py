#!/usr/bin/env python3
"""Upload the canonical OpenAPI spec to GitBook as the `algenta-api` spec the docs explorer renders.

The on-disk spec is already public-facing. The upload step pins its title and server defensively so
GitBook cannot retain stale identity metadata from an older schema revision.

    GITBOOK_API_KEY=... python3 scripts/docs/upload_openapi.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SPEC = os.path.join(ROOT, "schemas", "openapi", "openapi.yaml")
ORG = "o33uJH8DVq2cATtrgKVy"
SLUG = "algenta-api"
TITLE = "Algenta API"
SERVER = "https://api.algenta.ai"
API = f"https://api.gitbook.com/v1/orgs/{ORG}/openapi/{SLUG}"


def main() -> int:
    key = os.environ.get("GITBOOK_API_KEY", "").strip()
    if not key:
        print("GITBOOK_API_KEY not set")
        return 2
    spec = yaml.safe_load(open(SPEC))
    spec.setdefault("info", {})["title"] = TITLE
    spec["servers"] = [{"url": SERVER, "description": "Algenta API"}]
    text = json.dumps(spec)
    n_ops = sum(
        1
        for item in (spec.get("paths") or {}).values()
        for m in (item or {})
        if m in ("get", "post", "put", "patch", "delete")
    )
    if "--dry-run" in sys.argv:
        print(
            f"DRY-RUN would PUT {SLUG}: title={TITLE!r} server={SERVER!r} "
            f"ops={n_ops} bytes={len(text)}"
        )
        return 0
    body = json.dumps({"source": {"text": text}}).encode()
    req = urllib.request.Request(  # noqa: S310 - API is a fixed HTTPS endpoint.
        API,
        data=body,
        method="PUT",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 - fixed HTTPS request.
            print(
                f"uploaded {SLUG}: HTTP {r.status} "
                f"(title={TITLE!r}, server={SERVER!r}, {n_ops} ops)"
            )
        return 0
    except urllib.error.HTTPError as e:
        print(f"PUT failed [{e.code}]: {e.read().decode('utf-8','replace')[:400]}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
