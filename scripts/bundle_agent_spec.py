#!/usr/bin/env python3
"""Bundle the agent-facing OpenAPI spec into the M365 app package, downgraded to OpenAPI 3.0.x.

The Copilot API-plugin org-catalog publish (POST /appCatalogs/teamsApps) requires the OpenAPI
document to be a FILE inside the package (not a remote URL) AND to be OpenAPI 3.0.x — but FastAPI
emits 3.1.0. This fetches the live reduced spec and rewrites it to 3.0.3 (handling FastAPI's 3.1
nullable/const/examples constructs), writing integrations/microsoft/m365-app/decision-agent-openapi.json
which apiPlugin.json references by relative path.

    python scripts/bundle_agent_spec.py            # from the live gateway
    python scripts/bundle_agent_spec.py --from-file spec.json
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

SPEC_URL = "https://gateway.algenta.ai/openapi/decision-agent.json"
OUT = Path(__file__).resolve().parent.parent / "integrations" / "microsoft" / "m365-app" / "decision-agent-openapi.json"


def down(node) -> None:
    """In-place OpenAPI 3.1 -> 3.0.3 downgrade of the constructs FastAPI emits."""
    if isinstance(node, dict):
        for comb in ("anyOf", "oneOf"):
            subs = node.get(comb)
            if isinstance(subs, list):
                has_null = any(isinstance(s, dict) and s.get("type") == "null" for s in subs)
                non_null = [s for s in subs if not (isinstance(s, dict) and s.get("type") == "null")]
                if has_null:
                    node["nullable"] = True
                    if len(non_null) == 1:
                        only = non_null.pop()
                        node.pop(comb)
                        for k, v in only.items():
                            node.setdefault(k, v)
                    else:
                        node[comb] = non_null
        t = node.get("type")
        if isinstance(t, list):
            if "null" in t:
                node["nullable"] = True
            nn = [x for x in t if x != "null"]
            if len(nn) == 1:
                node["type"] = nn[0]
            else:
                node.pop("type", None)
        if "const" in node:
            node["enum"] = [node.pop("const")]
        if ("examples" in node and isinstance(node["examples"], list) and "example" not in node
                and any(k in node for k in ("type", "properties", "items", "allOf", "anyOf",
                                            "oneOf", "enum", "$ref", "format", "nullable"))):
            if node["examples"]:
                node["example"] = node["examples"][0]
            node.pop("examples", None)
        for k, base in (("exclusiveMinimum", "minimum"), ("exclusiveMaximum", "maximum")):
            if k in node and isinstance(node[k], (int, float)) and not isinstance(node[k], bool):
                node[base] = node[k]
                node[k] = True
        for v in list(node.values()):
            down(v)
    elif isinstance(node, list):
        for x in node:
            down(x)


def main() -> int:
    ap = argparse.ArgumentParser(description="Bundle + downgrade the agent OpenAPI spec to 3.0.3.")
    ap.add_argument("--url", default=SPEC_URL)
    ap.add_argument("--from-file", type=Path)
    args = ap.parse_args()

    if args.from_file:
        spec = json.loads(args.from_file.read_text())
    else:
        with urllib.request.urlopen(args.url) as r:  # noqa: S310 — fixed HTTPS gateway URL
            spec = json.loads(r.read())
    spec["openapi"] = "3.0.3"
    down(spec)
    OUT.write_text(json.dumps(spec, indent=2) + "\n")
    print(f"wrote {OUT} (openapi 3.0.3, {len(spec.get('paths', {}))} paths, "
          f"servers={[s.get('url') for s in spec.get('servers', [])]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
