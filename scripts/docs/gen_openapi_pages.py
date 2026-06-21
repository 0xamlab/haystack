#!/usr/bin/env python3
"""Generate the API explorer + endpoint reference from the OpenAPI spec — complete by construction.

Emits:
  gitbook/api/explorer.md   — every operation as a live {% openapi-operation %} block, grouped by tag
  gitbook/api/reference.md  — a complete grouped index (method · path · summary) of every operation

    python3 scripts/docs/gen_openapi_pages.py            # write both pages
    python3 scripts/docs/gen_openapi_pages.py --check     # CI: fail if either page is stale

--check regenerates and byte-compares (a dropped/renamed/duplicated operation changes the output),
and asserts the (method, path) inventory is unique and meets a regression floor.
"""
from __future__ import annotations

import os
import sys
from collections import Counter

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SPEC = os.path.join(ROOT, "schemas", "openapi", "openapi.yaml")
EXPLORER = os.path.join(ROOT, "gitbook", "api", "explorer.md")
REFERENCE = os.path.join(ROOT, "gitbook", "api", "reference.md")
SPEC_SLUG = "algenta-api"
FLOOR = 100
_METHODS = ("get", "post", "put", "patch", "delete")


def load():
    spec = yaml.safe_load(open(SPEC))
    tag_order = [t["name"] for t in spec.get("tags", []) if isinstance(t, dict) and t.get("name")]
    groups: dict[str, list[tuple[str, str, str]]] = {}
    for path, item in (spec.get("paths") or {}).items():
        # The MCP-over-HTTP transport endpoints are documented separately (sdk/mcp.md) and the spec
        # marks them unavailable — keep them out of the public API explorer/reference.
        if path.startswith("/mcp"):
            continue
        for method, op in (item or {}).items():
            if method not in _METHODS or not isinstance(op, dict):
                continue
            tag = (op.get("tags") or ["Other"])[0]
            summary = (op.get("summary") or op.get("operationId") or "").strip()
            groups.setdefault(tag, []).append((method, path, summary))
    # order tags by the spec's declared order, then any extras alphabetically
    ordered = [t for t in tag_order if t in groups] + sorted(t for t in groups if t not in tag_order)
    return ordered, groups


def _cell(s: str) -> str:
    return s.replace("\n", " ").replace("|", "\\|").strip()


def render_explorer(ordered, groups) -> str:
    out = [
        "---",
        "icon: circle-play",
        "description: Try the Algenta HTTP API live — set your key and base URL, then send real "
        "requests to every endpoint from the browser.",
        "---",
        "",
        "# API explorer",
        "",
        "Every endpoint below renders live from the Algenta OpenAPI specification. Expand an operation "
        "to see parameters, request and response schemas, and example payloads, then use **Test it** to "
        "call the API directly from this page with your own key.",
        "",
        "{% hint style=\"info\" %}",
        "Generated from the canonical OpenAPI spec, so it always matches the deployed engine. Set your "
        "base URL (your self-hosted deployment or `https://api.algenta.ai`) and API key in the **Test "
        "it** panel. For a flat index see the [endpoint reference](reference.md); for prose, the "
        "[API overview](overview.md).",
        "{% endhint %}",
        "",
    ]
    for tag in ordered:
        out.append(f"## {tag}")
        out.append("")
        for method, path, _summary in groups[tag]:
            out.append(f"### `{method.upper()} {path}`")
            out.append("")
            out.append(f'{{% openapi-operation spec="{SPEC_SLUG}" path="{path}" method="{method}" %}}')
            out.append("{% endopenapi-operation %}")
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def render_reference(ordered, groups) -> str:
    out = [
        "---",
        "icon: code",
        "description: The complete Algenta HTTP API endpoint reference — every operation grouped by "
        "area, with method, path, and summary, generated from the OpenAPI spec.",
        "---",
        "",
        "# API endpoint reference",
        "",
        "Every Algenta HTTP operation, grouped by area and generated from the canonical OpenAPI spec — "
        "so the list is complete and current. All routes are versioned under `/v1`; authenticate with "
        "`Authorization: Bearer <key>` (legacy `X-API-Key` is accepted).",
        "",
        "{% hint style=\"info\" %}",
        "To call any endpoint live (parameters, schemas, Test it), use the [API explorer](explorer.md). "
        "Errors are listed on [Error codes](errors.md); limits on [Rate limits & quotas](rate-limits.md).",
        "{% endhint %}",
        "",
    ]
    for tag in ordered:
        out.append(f"## {tag}")
        out.append("")
        out.append("| Method | Path | Summary |")
        out.append("| --- | --- | --- |")
        for method, path, summary in groups[tag]:
            out.append(f"| `{method.upper()}` | `{path}` | {_cell(summary) or '—'} |")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    ordered, groups = load()
    pairs = [(m, p) for t in ordered for m, p, _ in groups[t]]
    dupes = [k for k, c in Counter(pairs).items() if c > 1]
    assert not dupes, f"duplicate (method, path): {dupes}"
    assert len(pairs) >= FLOOR, f"only {len(pairs)} operations (< floor {FLOOR}) — spec parse broke"
    expl, ref = render_explorer(ordered, groups), render_reference(ordered, groups)
    if "--check" in sys.argv:
        bad = False
        for path_, md in ((EXPLORER, expl), (REFERENCE, ref)):
            cur = open(path_).read() if os.path.exists(path_) else ""
            if cur != md:
                print(f"DRIFT: {os.path.relpath(path_, ROOT)} is stale vs the OpenAPI spec — run `make docs-gen`")
                bad = True
        if not bad:
            print(f"explorer.md + reference.md OK ({len(pairs)} operations, {len(ordered)} tags)")
        return 1 if bad else 0
    open(EXPLORER, "w").write(expl)
    open(REFERENCE, "w").write(ref)
    print(f"wrote explorer.md + reference.md ({len(pairs)} operations, {len(ordered)} tags)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
