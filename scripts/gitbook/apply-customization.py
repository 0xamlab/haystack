#!/usr/bin/env python3
"""Apply a product's GitBook site customization = shared design system + per-product brand override.

The shared design system (gitbook/shared-customization.json) is FIXED across all Thyn product docs
sites — visual system, interaction grammar, archetypes, and QA gates do not vary. Only brand
(logo, favicon, hero, accent color, header links, domain) varies, via gitbook/products/<p>.json.

Usage:
    GITBOOK_API_KEY=... python3 gitbook/apply-customization.py gitbook/products/codna.json [--dry-run]

GitBook customization is set with PUT (the API rejects PATCH on this resource), so we GET the
current customization, merge our keys in, strip read-only fields, and PUT the whole object.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.gitbook.com/v1"
HERE = os.path.dirname(os.path.abspath(__file__))


def _req(method: str, url: str, key: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode("utf-8", "replace")}


def _contentref(href: str, domain: str) -> dict:
    # internal "/path" -> absolute on the product domain; everything else is a url ref
    url = f"https://{domain}{href}" if href.startswith("/") else href
    return {"kind": "url", "url": url}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    product = json.load(open(sys.argv[1]))
    dry = "--dry-run" in sys.argv[2:]
    shared = json.load(open(os.path.join(HERE, "shared-customization.json")))
    key = os.environ.get("GITBOOK_API_KEY", "").strip()
    if not key:
        print("GITBOOK_API_KEY not set"); return 2

    org, site, domain = product["org"], product["siteId"], product["domain"]
    cust_url = f"{API}/orgs/{org}/sites/{site}/customization"

    status, current = _req("GET", cust_url, key)
    if status != 200:
        print(f"GET customization failed [{status}]: {current}"); return 1
    current.pop("updatedAt", None)

    # 1) shared styling, with the product's accent color
    styling = dict(shared["styling"])
    styling["primaryColor"] = product["primaryColor"]
    styling["infoColor"] = product["primaryColor"]
    current["styling"] = styling

    # 2) Header nav, favicon, and logo are ALL UI-managed in GitBook (Customization -> Basic):
    #    GitBook has no upload API and the repo is private, so we NEVER set favicon/header.logo here,
    #    and we only set header.links if a product explicitly opts in via "headerLinks". By default
    #    the nav/favicon/logo are left exactly as the UI set them — re-running apply can't clobber them.
    hl = product.get("headerLinks")
    if hl:
        header = current.get("header") or {}
        header.setdefault("preset", "default")
        header["links"] = [
            {"title": l["title"],
             "style": "button-primary" if l.get("variant") == "primary" else "link",
             "to": _contentref(l["href"], domain),
             "links": []}  # required by the API (sub-links for dropdowns), empty for a flat link
            for l in hl
        ]
        current["header"] = header

    if dry:
        print(json.dumps({"styling": styling,
                          "header_links": (current.get("header") or {}).get("links", "UI-managed (left untouched)"),
                          "favicon_logo": "UI-managed (left untouched)"}, indent=2))
        return 0

    status, resp = _req("PUT", cust_url, key, current)
    if status != 200:
        print(f"PUT failed [{status}]: {resp}"); return 1
    print(f"applied customization to {product['product']} ({site}) — PUT [{status}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
