#!/usr/bin/env python3
"""Emit a deploy-ready Azure AI Foundry OpenAPI tool with the reduced spec inlined.

Foundry's OpenAPI tool has NO spec_url field — the spec must be embedded inline. This fetches the
gateway's reduced agent spec, normalizes it for the Foundry importer (HTTPS server, single
Entra-compatible bearer scheme), and writes the tool JSON in the current OpenApiFunctionDefinition
shape (type + openapi{name,description,spec,auth}).

Usage:  python infra/azure/foundry/build_tool.py
Output: infra/azure/foundry/tool-definition/decision-tool.deploy.json
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

GATEWAY_SPEC_URL = "https://gateway.algenta.ai/openapi/decision-agent.json"
AUDIENCE = "api://3983990d-e9b5-4866-9a43-d52d6e0c20c3"
HERE = Path(__file__).resolve().parent
OUT = HERE / "tool-definition" / "decision-tool.deploy.json"
DESCRIPTION = (
    "Coarse governed-decision operations: frame a decision, run the analysis (async), read the "
    "result, inspect evidence, propose a plan, record an outcome. Approval and execution are NOT "
    "available here — they are separate, credentialed human actions."
)


def normalize(spec: dict) -> dict:
    # Foundry calls the server over TLS; managed-identity Entra tokens require HTTPS.
    for s in spec.get("servers", []):
        if str(s.get("url", "")).startswith("http://"):
            s["url"] = "https://" + s["url"][len("http://"):]
    # Keep a single Entra-compatible (http bearer) scheme; drop the API-key scheme from the agent spec.
    comps = spec.setdefault("components", {})
    schemes = comps.get("securitySchemes", {}) or {}
    schemes.pop("LegacyApiKey", None)
    if not schemes:
        schemes = {"BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}}
    comps["securitySchemes"] = schemes
    bearer = next(iter(schemes.keys()))
    for ops in spec.get("paths", {}).values():
        for op in ops.values():
            if isinstance(op, dict) and "responses" in op:
                op["security"] = [{bearer: []}]
    spec["security"] = [{bearer: []}]
    return spec


def main() -> int:
    with urllib.request.urlopen(GATEWAY_SPEC_URL) as r:  # noqa: S310 — fixed HTTPS gateway URL
        spec = normalize(json.loads(r.read()))
    tool = {
        "type": "openapi",
        "openapi": {
            "name": "algenta_decision_api",
            "description": DESCRIPTION,
            "spec": spec,
            "auth": {"type": "managed_identity", "security_scheme": {"audience": AUDIENCE}},
        },
    }
    OUT.write_text(json.dumps(tool, indent=2) + "\n")
    print(f"wrote {OUT} ({len(spec.get('paths', {}))} paths, audience {AUDIENCE})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
