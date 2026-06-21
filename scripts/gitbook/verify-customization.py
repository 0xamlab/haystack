#!/usr/bin/env python3
"""Read a product's live GitBook customization back and diff it against the intended config.

Part of the golden-template lock gate: the API read-back must match the intended customization.

Usage:
    GITBOOK_API_KEY=... python3 gitbook/verify-customization.py gitbook/products/codna.json
Exits non-zero on any mismatch.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

API = "https://api.gitbook.com/v1"
HERE = os.path.dirname(os.path.abspath(__file__))


def _get(url: str, key: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__); return 2
    product = json.load(open(sys.argv[1]))
    shared = json.load(open(os.path.join(HERE, "shared-customization.json")))
    key = os.environ.get("GITBOOK_API_KEY", "").strip()
    if not key:
        print("GITBOOK_API_KEY not set"); return 2

    cust = _get(f"{API}/orgs/{product['org']}/sites/{product['siteId']}/customization", key)
    styling = cust.get("styling", {})
    problems = []

    want = dict(shared["styling"]); want["primaryColor"] = product["primaryColor"]
    want["infoColor"] = product["primaryColor"]
    for k, v in want.items():
        if styling.get(k) != v:
            problems.append(f"styling.{k}: got {styling.get(k)!r} want {v!r}")

    # favicon + logo are UI-managed (uploaded in GitBook -> Customization -> Basic). Verify they
    # are SET (the upload happened) — we don't compare URLs since GitBook hosts them.
    fav = (cust.get("favicon") or {}).get("icon") or {}
    if not fav.get("light") or not fav.get("dark"):
        problems.append("favicon not uploaded (Customization -> Basic -> Icon, light + dark)")

    logo = (cust.get("header") or {}).get("logo") or {}
    if not logo.get("light") or not logo.get("dark"):
        problems.append("logo not uploaded (Customization -> Basic -> Logo, light + dark)")

    # header nav is UI-managed and optional (default nav is fine) — not part of the lock gate.

    if problems:
        print(f"VERIFY FAILED for {product['product']}:")
        for p in problems:
            print("  -", p)
        return 1
    links = (cust.get("header") or {}).get("links") or []
    print(f"VERIFY OK for {product['product']}: styling matches shared+accent, favicon + logo set "
          f"({len(links)} header links).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
