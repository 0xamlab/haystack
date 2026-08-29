#!/usr/bin/env python3
"""Generate schemas/openapi/openapi.yaml in-process -- no live server required.

The spec used to be produced by booting the real API on :8000 and `curl`-ing
/openapi.json (see git history of the Makefile's `openapi:` target). That meant the spec
could only ever be as fresh as whoever remembered to boot the server and re-run the target --
easy to forget, and impossible to run in a CI job that doesn't already have Postgres/Redis/MinIO
up. This script imports the real `apps.api_server.main.app` object directly and calls
`app.openapi()`, the exact function FastAPI calls to serve that same endpoint, so the output is
byte-for-byte what a live server would answer right now, with no server, port, or curl involved.

    python3 scripts/openapi/export_openapi.py                    # regen schemas/openapi/openapi.yaml
    python3 scripts/openapi/export_openapi.py --output PATH      # write elsewhere (used by tests/CI)

`build_openapi_schema()` is imported directly by tests/test_openapi_spec_drift.py, so the pytest
drift guard and this script's own regeneration always exercise the identical code path.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC_PATH = ROOT / "schemas" / "openapi" / "openapi.yaml"


def bootstrap_import_environment() -> None:
    """Set the env vars `apps.api_server.main` needs to import cleanly, standalone.

    Every one of these Settings fields has a safe default (see apps/api_server/config.py) --
    none of them need a real, reachable Postgres/Redis/S3 endpoint just to IMPORT the app and
    build its OpenAPI schema (the code that actually dials those services lives in the
    `lifespan` context manager, which only runs when the ASGI app actually starts up, not on
    plain import or on a bare `app.openapi()` call). These setdefaults exist only so
    pydantic-settings has well-formed values to parse instead of falling back to whatever ".env"
    file this checkout happens to have (or doesn't). Mirrors the equivalent block in
    tests/conftest.py, minus the live-server/API-key bootstrap that file also does for tests that
    make real HTTP requests against a running instance -- we don't start one here.
    """
    os.environ.setdefault("API_ENV", "development")
    os.environ.setdefault(
        "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/algenta"
    )
    os.environ.setdefault(
        "DATABASE_URL_SYNC", "postgresql://postgres:postgres@localhost:5432/algenta"
    )
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("JWT_SECRET", "openapi-export-not-for-production")


def build_openapi_schema() -> dict[str, Any]:
    """Return the live app's OpenAPI schema -- the same dict FastAPI serves at GET /openapi.json."""
    bootstrap_import_environment()
    repo_root = str(ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from apps.api_server.main import app  # local import: only safe after env bootstrap above

    schema = app.openapi()
    # custom_openapi() (apps/api_server/main.py) assigns the SAME "security" dict objects onto
    # many different operations. yaml.safe_dump would then notice the repeated object identity
    # and emit &id001/*id001 anchors/aliases instead of the plain repeated blocks the committed
    # file has always had. A JSON round-trip normalizes that away by rebuilding fresh, unshared
    # objects -- exactly the normalization the old curl-based pipeline got for free by
    # serializing the schema to HTTP JSON and parsing it back on the other end.
    schema = json.loads(json.dumps(schema))
    # apps/mcp_server's router is assembled behind a try/except that recovers from a failed
    # primary construction attempt (see server.py's create_fastapi_router docstring: /mcp/tools
    # is "always" mounted even when the rest of the MCP transport can't build cleanly). Which
    # attempt succeeds is not reliably the same between two otherwise-identical processes, so
    # /mcp/tools's position among the OTHER mcp routes has been observed to vary run-to-run even
    # with nothing else different -- caught by the CI openapi-check gate reporting a pure
    # reordering (no content change) diff. A byte-diff gate can't tolerate an incidentally-ordered
    # dict, so canonicalize it here rather than chase the non-determinism's root cause inside the
    # MCP transport, which is unrelated to what this script's job is.
    if isinstance(schema.get("paths"), dict):
        schema["paths"] = dict(sorted(schema["paths"].items()))
    return schema


def validate_schema(schema: dict[str, Any]) -> None:
    from openapi_spec_validator import validate_spec

    validate_spec(schema)


def write_yaml(schema: dict[str, Any], output_path: Path) -> None:
    import yaml

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as fh:
        yaml.safe_dump(schema, fh, sort_keys=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_SPEC_PATH,
        help="Where to write the generated spec (default: schemas/openapi/openapi.yaml).",
    )
    args = parser.parse_args(argv)

    schema = build_openapi_schema()
    # Validate BEFORE writing -- a spec that fails validation should never overwrite a good one.
    validate_schema(schema)
    write_yaml(schema, args.output)

    paths = schema.get("paths") or {}
    n_ops = sum(
        1
        for item in paths.values()
        if isinstance(item, dict)
        for method in item
        if method in ("get", "post", "put", "patch", "delete")
    )
    try:
        shown_path = args.output.resolve().relative_to(ROOT)
    except ValueError:
        shown_path = args.output
    print(f"wrote {shown_path} ({len(paths)} paths, {n_ops} operations) -- validated OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
