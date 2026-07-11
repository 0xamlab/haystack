"""
tests/integration/test_engines.py — Engine manifest + API router tests.

Two layers:
  Layer A — Manifest unit tests (no server required)
  Layer B — HTTP integration tests (requires running API server)

Run:
  python3 tests/integration/test_engines.py
  DE_SKIP_API=1 python3 tests/integration/test_engines.py   # manifest only
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from apps.api_server.routers.engines import router  # noqa: E402
from engines import ALL_ENGINE_LIBS, ENGINES, ENGINES_BY_SLUG, ENGINES_BY_TIER  # noqa: E402

try:
    from tests.integration.live_local_defaults import (
        resolve_local_live_api_key,
        resolve_local_live_base_url,
    )
except ModuleNotFoundError:
    from live_local_defaults import (
        resolve_local_live_api_key,
        resolve_local_live_base_url,
    )

BASE_URL = resolve_local_live_base_url()
API_KEY = resolve_local_live_api_key()
SKIP_API = os.environ.get("DE_SKIP_API", "0") == "1"

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️ "

_results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    icon = PASS if cond else FAIL
    _results.append((name, cond, detail))
    print(f"  {icon}  {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        raise AssertionError(f"FAILED: {name} — {detail}")


def api_get(path: str) -> dict:
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers={"X-API-Key": API_KEY})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


# ── Layer A: Manifest unit tests ─────────────────────────────────────────────


def test_engine_count():
    check("12 engines registered", len(ENGINES) == 12, f"got {len(ENGINES)}")


def test_required_fields():
    for e in ENGINES:
        check(f"{e.slug}: has slug", bool(e.slug))
        check(f"{e.slug}: has name", bool(e.name))
        check(f"{e.slug}: has description", len(e.description) > 20)
        check(f"{e.slug}: has api_path", e.api_path.startswith("/v1/"))
        check(f"{e.slug}: has mojo_libs", len(e.mojo_libs) >= 3)
        check(f"{e.slug}: has use_cases", len(e.use_cases) >= 2)
        check(f"{e.slug}: valid tier", e.tier in ("core", "advanced", "platform"))


def test_tier_counts():
    check("core tier has 6 engines", len(ENGINES_BY_TIER["core"]) == 6)
    check("advanced tier has 4 engines", len(ENGINES_BY_TIER["advanced"]) == 4)
    check("platform tier has 2 engines", len(ENGINES_BY_TIER["platform"]) == 2)


def test_all_slugs_resolve():
    expected = {
        "decision",
        "inference",
        "agent",
        "retrieval",
        "optimize",
        "serving",
        "training",
        "data",
        "model",
        "cost",
        "security",
        "hybrid",
    }
    for slug in expected:
        check(f"slug '{slug}' resolves", slug in ENGINES_BY_SLUG)


def test_no_duplicates():
    slugs = [e.slug for e in ENGINES]
    paths = [e.api_path for e in ENGINES]
    check("no duplicate slugs", len(slugs) == len(set(slugs)))
    check("no duplicate api_paths", len(paths) == len(set(paths)))


def test_lib_coverage():
    check(
        f"≥30 distinct Mojo libs referenced ({len(ALL_ENGINE_LIBS)})",
        len(ALL_ENGINE_LIBS) >= 30,
    )


def test_core_engines_have_key_libs():
    decision = ENGINES_BY_SLUG["decision"]
    check("decision references monte_carlo", "engines_monte_carlo" in decision.mojo_libs)
    check("decision references decision_ml_fusion", "decision_ml_fusion" in decision.mojo_libs)

    inference = ENGINES_BY_SLUG["inference"]
    check("inference references flash_attention", "flash_attention" in inference.mojo_libs)
    check("inference references generation_loop", "generation_loop" in inference.mojo_libs)
    check("inference references paged_kv_cache", "paged_kv_cache" in inference.mojo_libs)

    agent = ENGINES_BY_SLUG["agent"]
    check("agent references workflow_engine", "workflow_engine" in agent.mojo_libs)
    check("agent references structured_output", "structured_output" in agent.mojo_libs)

    hybrid = ENGINES_BY_SLUG["hybrid"]
    check("hybrid references hybrid_reasoning", "hybrid_reasoning" in hybrid.mojo_libs)


def test_router_routes():
    routes = {r.path for r in router.routes}
    check("GET /v1/engines registered", "/v1/engines" in routes)
    check("GET /v1/engines/tiers registered", "/v1/engines/tiers" in routes)
    check("GET /v1/engines/{slug} registered", "/v1/engines/{slug}" in routes)


def test_router_methods():
    for r in router.routes:
        check(
            f"route {r.path} is GET-only",
            "GET" in r.methods and len(r.methods) == 1,
            str(r.methods),
        )


def test_catalog_api_paths_are_registered():
    from apps.api_server.main import app

    registered_paths = {route.path for route in app.routes}
    for engine in ENGINES:
        check(
            f"{engine.slug}: api_path is registered",
            engine.api_path in registered_paths,
            engine.api_path,
        )


# ── Layer B: HTTP integration tests ─────────────────────────────────────────


def test_api_list_engines():
    data = api_get("/v1/engines")
    check("API /v1/engines returns count=12", data["count"] == 12, str(data.get("count")))
    check("API /v1/engines returns engines list", isinstance(data["engines"], list))
    check("API engines list has 12 items", len(data["engines"]) == 12)


def test_api_engines_tiers():
    data = api_get("/v1/engines/tiers")
    check("API /v1/engines/tiers has core", "core" in data)
    check("API /v1/engines/tiers has advanced", "advanced" in data)
    check("API /v1/engines/tiers has platform", "platform" in data)
    check("API core tier has 6", len(data["core"]) == 6)
    check("API advanced tier has 4", len(data["advanced"]) == 4)
    check("API platform tier has 2", len(data["platform"]) == 2)


def test_api_engine_by_slug():
    for slug in ["decision", "inference", "agent", "hybrid"]:
        data = api_get(f"/v1/engines/{slug}")
        check(f"API /v1/engines/{slug} returns slug", data["slug"] == slug)
        check(f"API /v1/engines/{slug} returns name", bool(data["name"]))
        check(f"API /v1/engines/{slug} returns mojo_libs", len(data["mojo_libs"]) >= 3)


def test_api_engine_not_found():
    try:
        api_get("/v1/engines/does_not_exist")
        check("404 on unknown slug", False, "expected HTTPError")
    except urllib.error.HTTPError as e:
        check("404 on unknown slug", e.code == 404, f"got {e.code}")


def test_api_engine_fields_complete():
    data = api_get("/v1/engines/decision")
    for field in ["name", "slug", "description", "api_path", "mojo_libs", "use_cases", "tier"]:
        check(f"decision engine has field '{field}'", field in data)


# ── Runner ───────────────────────────────────────────────────────────────────


def main() -> None:
    print("\n" + "=" * 68)
    print("  ENGINE TESTS")
    print("=" * 68)

    # Layer A — always run
    print("\n── Layer A: Manifest + Router (no server) ──────────────────────\n")
    layer_a = [
        test_engine_count,
        test_required_fields,
        test_tier_counts,
        test_all_slugs_resolve,
        test_no_duplicates,
        test_lib_coverage,
        test_core_engines_have_key_libs,
        test_router_routes,
        test_router_methods,
        test_catalog_api_paths_are_registered,
    ]
    for fn in layer_a:
        try:
            fn()
        except AssertionError:
            pass  # already printed

    # Layer B — HTTP tests
    print("\n── Layer B: HTTP API ────────────────────────────────────────────\n")
    if SKIP_API:
        print(f"  {SKIP}  Skipped (DE_SKIP_API=1)")
    else:
        layer_b = [
            test_api_list_engines,
            test_api_engines_tiers,
            test_api_engine_by_slug,
            test_api_engine_not_found,
            test_api_engine_fields_complete,
        ]
        for fn in layer_b:
            try:
                fn()
            except urllib.error.URLError as exc:
                print(f"  {SKIP}  {fn.__name__} — server unreachable ({exc.reason})")
            except AssertionError:
                pass

    # Summary
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = sum(1 for _, ok, _ in _results if not ok)
    print("\n" + "=" * 68)
    print(f"  {passed} passed  |  {failed} failed  |  {len(_results)} total")
    print("=" * 68 + "\n")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
