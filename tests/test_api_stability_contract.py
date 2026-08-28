"""A5 — the API stability contract.

TWO KINDS OF TEST, deliberately separated.

*Structural* tests interrogate the REAL app: is every registered path classified, does every
legacy route have exactly one successor, is the alias's published operation identical to its
legacy twin's? These need no database, and they are the ones that fail when someone adds an
unversioned route.

*Behavioural* tests build a SMALL app with the same middlewares and one route per shape. The
headers and the middleware-exclusion logic are what they are testing, and a five-route app makes a
failure point at the mechanism instead of at whichever real endpoint happened to need Postgres.
Both matter: the structural tests would pass on a mechanism that emits nothing, and the
behavioural ones would pass on an app that forgot half its families.

The counts here are DERIVED (from the route table, from the family table). A test pinned to "26
aliases" would fail on unrelated work and get bumped without thought, which is how a guard stops
being read.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.testclient import TestClient

from apps.api_server.middleware.deprecation import (
    ALIAS_SUFFIX,
    LEGACY_FAMILIES,
    STABILITY_DOCS_URL,
    UNVERSIONED_BY_DESIGN,
    VERSION_PREFIX,
    DeprecationMiddleware,
    LegacyFamily,
    _matches,
    family_for,
    mount_versioned_aliases,
    route_params_without_attribute,
    successor_for,
    unversioned_reason,
)
from apps.api_server.middleware.idempotency import IdempotencyMiddleware
from apps.api_server.middleware.response_contract import ResponseContractMiddleware


@pytest.fixture(scope="module")
def real_app() -> FastAPI:
    from apps.api_server.main import app

    return app


def _api_routes(app: FastAPI) -> list[APIRoute]:
    return [r for r in app.router.routes if isinstance(r, APIRoute)]


def _comparable(operation: dict) -> dict:
    """An operation stripped of the three keys that MUST differ between a pair.

    ``operationId`` and ``deprecated`` differ by design. ``title`` is subtler: for a route with no
    explicit ``response_model``, FastAPI names the inline response schema after the route's own
    name and path ("Response Verify Email Auth Verify Get"), and the alias must carry a different
    name so operation ids stay unique. That label is documentation-only, so it is scrubbed
    recursively -- everything that governs client behaviour (parameters, request body, $refs,
    required, types, security, response codes) is still compared exactly.
    """

    def scrub(node: object) -> object:
        if isinstance(node, dict):
            return {k: scrub(v) for k, v in node.items() if k not in {"title", "operationId", "deprecated"}}
        if isinstance(node, list):
            return [scrub(v) for v in node]
        return node

    return scrub(operation)  # type: ignore[return-value]


# ── the classification is exhaustive ─────────────────────────────────────────────────────────────


def test_every_registered_path_is_classified(real_app: FastAPI) -> None:
    """The load-bearing assertion: a new unversioned route cannot slip in unnoticed.

    Every path must be versioned, in a legacy family (so it has a successor), or listed in
    UNVERSIONED_BY_DESIGN with a reason. Without this, "we forgot to version it" and "we decided
    not to version it" look identical from outside.
    """
    paths = {p for r in real_app.router.routes if (p := getattr(r, "path", None))}
    unclassified = sorted(
        p
        for p in paths
        if not p.startswith(f"{VERSION_PREFIX}/")
        and p != VERSION_PREFIX
        and family_for(p) is None
        and unversioned_reason(p) is None
    )
    assert unclassified == [], (
        "unversioned path(s) outside the stability contract: "
        f"{unclassified}. Either mount them under /v1 (add the family to LEGACY_FAMILIES) or "
        "record why they stay unversioned in UNVERSIONED_BY_DESIGN."
    )


def test_every_by_design_exclusion_carries_a_reason() -> None:
    """An empty reason is how an exclusion table turns into a rubber stamp."""
    for prefix, reason in UNVERSIONED_BY_DESIGN.items():
        assert prefix.startswith("/"), prefix
        assert len(reason) >= 40, f"{prefix}: reason is too thin to review -- {reason!r}"


def test_every_by_design_exclusion_still_matches_something(real_app: FastAPI) -> None:
    """A stale exclusion is worse than none: it silently pre-approves a path shape nobody has."""
    paths = [p for r in real_app.router.routes if (p := getattr(r, "path", None))]
    unused = [prefix for prefix in UNVERSIONED_BY_DESIGN if not any(_matches(p, prefix) for p in paths)]
    assert unused == [], f"UNVERSIONED_BY_DESIGN entries matching no route: {unused}"


def test_no_family_is_itself_versioned() -> None:
    """A family under /v1 would generate /v1/v1/... successors."""
    for family in LEGACY_FAMILIES:
        assert not family.prefix.startswith(VERSION_PREFIX), family.prefix
        assert family.successor_prefix == f"{VERSION_PREFIX}{family.prefix}"


# ── the aliases ──────────────────────────────────────────────────────────────────────────────────


def test_every_legacy_route_has_exactly_one_successor(real_app: FastAPI) -> None:
    routes = _api_routes(real_app)
    legacy = [r for r in routes if family_for(r.path) is not None]
    assert legacy, "no legacy-family routes found -- the families or the app changed shape"

    by_path_methods = {(r.path, frozenset(r.methods or ())) for r in routes}
    for route in legacy:
        successor = successor_for(route.path)
        assert successor is not None
        assert (successor, frozenset(route.methods or ())) in by_path_methods, (
            f"{sorted(route.methods or ())} {route.path} has no successor at {successor}"
        )


def test_aliases_and_legacy_routes_share_the_endpoint_function(real_app: FastAPI) -> None:
    """The successor must be the SAME handler, not a reimplementation that can drift."""
    by_key = {(r.path, frozenset(r.methods or ())): r for r in _api_routes(real_app)}
    aliases = real_app.state.alias_successor_routes
    assert aliases, "no aliases were mounted"
    for alias in aliases:
        legacy_path = alias.path[len(VERSION_PREFIX) :]
        legacy = by_key[(legacy_path, frozenset(alias.methods or ()))]
        assert alias.endpoint is legacy.endpoint, alias.path


def test_no_route_is_registered_twice(real_app: FastAPI) -> None:
    """Two registrations of one (path, methods) is a coin flip: Starlette answers the first match.

    No legacy path currently maps onto an existing /v1 route, so this passes on the real app even
    with the shadowing guard removed -- which is why
    test_an_alias_never_shadows_a_hand_written_v1_route exercises that guard on a synthetic app
    instead. This test is the regression net for the day one of them does collide.
    """
    counts: dict[tuple[str, frozenset[str]], int] = {}
    for route in _api_routes(real_app):
        key = (route.path, frozenset(route.methods or ()))
        counts[key] = counts.get(key, 0) + 1
    duplicated = sorted(f"{sorted(m)} {p}" for (p, m), n in counts.items() if n > 1)
    assert duplicated == [], f"duplicate route registrations: {duplicated}"


def test_an_alias_never_shadows_a_hand_written_v1_route() -> None:
    """A native /v1 route must win; the generator must not add a second registration for it.

    Exercised on a synthetic app because no real legacy path collides with a native /v1 route
    today, so the guard has no trigger there and the real-app duplicate check cannot prove it
    works. It matters for the migration end-state: the way a family stops being an alias is that
    someone writes a real /v1 handler, and on that day the generator must step aside rather than
    register a duplicate that Starlette resolves by declaration order.
    """
    app = FastAPI()

    @app.post("/byok")
    async def _legacy() -> dict[str, str]:
        return {"which": "legacy"}

    @app.post("/v1/byok")
    async def _native() -> dict[str, str]:
        return {"which": "native"}

    created = mount_versioned_aliases(app)

    assert created == (), "the generator shadowed a hand-written /v1 route"
    registrations = [r for r in app.router.routes if getattr(r, "path", None) == "/v1/byok"]
    assert len(registrations) == 1
    client = TestClient(app)
    assert client.post("/v1/byok").json() == {"which": "native"}


def test_every_api_route_option_is_carried_onto_the_alias(real_app: FastAPI) -> None:
    """Alias options are copied by reading APIRoute's own signature.

    If a FastAPI upgrade adds an option the instance does not expose under the same name, the copy
    would silently drop it (a lost response_model, a lost dependency). Fail here instead.
    """
    for route in _api_routes(real_app):
        if family_for(route.path) is None:
            continue
        missing = route_params_without_attribute(route)
        assert missing == (), (
            f"{route.path}: APIRoute options not copyable onto the alias: {missing}. "
            "Copy them explicitly in _clone_route."
        )


def test_published_operation_is_identical_apart_from_path_and_operation_id(
    real_app: FastAPI,
) -> None:
    """The strongest available proof the clone is faithful.

    Rather than trusting the copied attribute list, compare what FastAPI actually PUBLISHES for
    each pair: parameters, request body, responses, security, tags. Anything the clone dropped
    shows up here as a diff.
    """
    schema = real_app.openapi()
    paths = schema["paths"]
    compared = 0
    for path, item in list(paths.items()):
        if family_for(path) is None:
            continue
        successor = f"{VERSION_PREFIX}{path}"
        if successor not in paths:  # not published (include_in_schema=False) -- nothing to compare
            continue
        for method, legacy_op in item.items():
            alias_op = paths[successor].get(method)
            assert alias_op is not None, f"{method.upper()} {successor} missing from the spec"
            assert _comparable(alias_op) == _comparable(legacy_op), (
                f"{method.upper()} {successor} does not match {path}"
            )
            compared += 1
    assert compared > 0, "no published legacy/alias pairs were compared -- the test proved nothing"


def test_operation_ids_stay_unique(real_app: FastAPI) -> None:
    """Duplicate operationIds are an invalid spec and break every generated client."""
    schema = real_app.openapi()
    ids = [
        op["operationId"]
        for item in schema["paths"].values()
        for op in item.values()
        if isinstance(op, dict) and "operationId" in op
    ]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    assert dupes == [], f"duplicate operationIds: {dupes}"


def test_legacy_routes_are_marked_deprecated_in_the_published_spec(real_app: FastAPI) -> None:
    """Steering happens through OpenAPI's own `deprecated` flag, NOT by hiding the path.

    include_in_schema=False would drop ~26 paths that still answer, which is the lie-by-omission
    that A1's truth gate exists to prevent.
    """
    schema = real_app.openapi()
    for path, item in schema["paths"].items():
        family = family_for(path)
        if family is None or not family.deprecated:
            continue
        for method, op in item.items():
            assert op.get("deprecated") is True, f"{method.upper()} {path} is not marked deprecated"
        assert f"{VERSION_PREFIX}{path}" in schema["paths"], (
            f"{path} is marked deprecated but its successor is not published"
        )


def test_an_alias_only_family_is_not_marked_deprecated(real_app: FastAPI) -> None:
    """/oauth is aliased so new clients can move, but released CLI builds still use it."""
    oauth = next(f for f in LEGACY_FAMILIES if f.prefix == "/oauth")
    assert oauth.deprecated is False
    assert oauth.deprecated_on is None
    schema = real_app.openapi()
    for path, item in schema["paths"].items():
        if family_for(path) is not oauth:
            continue
        for method, op in item.items():
            assert op.get("deprecated") is not True, (
                f"{method.upper()} {path} was marked deprecated while shipped CLIs depend on it"
            )


def test_no_family_publishes_a_sunset_date() -> None:
    """A Sunset date is a contractual promise to stop answering -- an owner decision.

    When one is set this test is the place to record that it was a deliberate call, not a default.
    """
    dated = [f.prefix for f in LEGACY_FAMILIES if f.sunset_on is not None]
    assert dated == [], (
        f"families publishing a Sunset date: {dated}. A removal date needs owner sign-off and a "
        "published notice period (see gitbook/api/stability.md) before it ships."
    )


# ── path matching ────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/byok", "/v1/byok"),
        ("/auth/login", "/v1/auth/login"),
        ("/account/team/{user_id}/role", "/v1/account/team/{user_id}/role"),
        # A bare startswith would claim these for the /byok and /auth families.
        ("/byoketc", None),
        ("/authorize", None),
        ("/v1/auth/login", None),
        ("/mcp", None),
    ],
)
def test_family_membership_is_by_path_segment_not_string_prefix(
    path: str, expected: str | None
) -> None:
    assert successor_for(path) == expected


def test_successor_link_names_the_requested_path_not_the_family_root() -> None:
    """A Link to /v1/auth would send the caller nowhere useful."""
    assert successor_for("/auth/reset-password") == "/v1/auth/reset-password"


# ── behaviour: headers and middleware exclusion ──────────────────────────────────────────────────


def _tiny_app(families: tuple[LegacyFamily, ...] | None = None) -> FastAPI:
    """A five-route stand-in wired with the same three middlewares as the real app."""
    app = FastAPI()

    @app.post("/auth/login")
    async def _login() -> dict[str, str]:
        return {"ok": "legacy-auth"}

    @app.post("/oauth/device/code")
    async def _device_code() -> dict[str, str]:
        return {"ok": "legacy-oauth"}

    @app.get("/v1/native")
    async def _native() -> dict[str, str]:
        return {"ok": "native"}

    @app.post("/v1/native-write")
    async def _native_write() -> dict[str, str]:
        return {"ok": "native-write"}

    @app.get("/unclassified")
    async def _unclassified() -> dict[str, str]:
        return {"ok": "unclassified"}

    mount_versioned_aliases(app)
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(ResponseContractMiddleware)
    app.add_middleware(DeprecationMiddleware)
    app.state.redis = None
    return app


@pytest.fixture
def tiny() -> TestClient:
    return TestClient(_tiny_app(), raise_server_exceptions=False)


def test_a_deprecated_legacy_path_advertises_deprecation_and_its_successor(
    tiny: TestClient,
) -> None:
    r = tiny.post("/auth/login")
    assert r.status_code == 200

    family = next(f for f in LEGACY_FAMILIES if f.prefix == "/auth")
    assert family.deprecated_on is not None
    expected = int(datetime.combine(family.deprecated_on, datetime.min.time(), tzinfo=UTC).timestamp())
    # RFC 9745: an Item Structured Field whose value is a Date -- "@<unix seconds>", not a
    # date string and not "true" (which the pre-RFC draft allowed).
    assert r.headers["Deprecation"] == f"@{expected}"

    links = r.headers.get_list("link")
    assert f'</v1/auth/login>; rel="successor-version"' in links
    assert any(STABILITY_DOCS_URL in link and 'rel="deprecation"' in link for link in links)


def test_no_sunset_header_when_no_removal_date_is_published(tiny: TestClient) -> None:
    assert "Sunset" not in tiny.post("/auth/login").headers


def test_a_published_sunset_date_is_emitted_as_an_http_date() -> None:
    """The other branch of the Sunset logic, exercised through a synthetic family.

    Left untested, the code that formats the header would first run on the day someone publishes a
    real removal date.
    """
    from apps.api_server.middleware import deprecation as mod

    synthetic = LegacyFamily(
        prefix="/auth",
        deprecated=True,
        deprecated_on=date(2026, 8, 28),
        sunset_on=datetime(2027, 12, 31, 23, 59, 59, tzinfo=UTC),
        why="test",
    )
    assert mod._sunset_header(synthetic) == "Fri, 31 Dec 2027 23:59:59 GMT"


def test_an_alias_only_path_advertises_the_successor_but_not_deprecation(
    tiny: TestClient,
) -> None:
    r = tiny.post("/oauth/device/code")
    assert r.status_code == 200
    assert "Deprecation" not in r.headers
    assert "Sunset" not in r.headers
    assert '</v1/oauth/device/code>; rel="successor-version"' in r.headers.get_list("link")


def test_a_404_under_a_deprecated_family_advertises_nothing(tiny: TestClient) -> None:
    """/v1/auth/typo does not exist either -- pointing there sends the caller to a second 404."""
    r = tiny.post("/auth/typo")
    assert r.status_code == 404
    assert "Deprecation" not in r.headers
    assert r.headers.get_list("link") == []


@pytest.mark.parametrize("path", ["/v1/native", "/unclassified"])
def test_paths_outside_every_family_carry_no_stability_headers(
    tiny: TestClient, path: str
) -> None:
    r = tiny.get(path)
    assert "Deprecation" not in r.headers
    assert "Sunset" not in r.headers
    assert r.headers.get_list("link") == []


def test_the_alias_carries_no_stability_headers_either(tiny: TestClient) -> None:
    """The successor is the supported path; telling a caller it is deprecated would be wrong."""
    r = tiny.post("/v1/auth/login")
    assert r.status_code == 200
    assert "Deprecation" not in r.headers
    assert r.headers.get_list("link") == []


# ── behaviour: the alias must not gain /v1 semantics its legacy twin lacks ───────────────────────


def test_the_alias_and_its_legacy_path_return_the_same_headers(tiny: TestClient) -> None:
    """The whole promise of the alias: migrating is a path change with no other consequence.

    Compared minus the stability headers themselves (only the legacy path carries those, by
    design) and minus per-request values like date and request id.
    """
    volatile = {"date", "content-length", "x-request-id", "deprecation", "sunset", "link"}
    legacy = {k.lower(): v for k, v in tiny.post("/auth/login").headers.items()}
    alias = {k.lower(): v for k, v in tiny.post("/v1/auth/login").headers.items()}
    assert {k: v for k, v in alias.items() if k not in volatile} == {
        k: v for k, v in legacy.items() if k not in volatile
    }


@pytest.mark.parametrize(
    ("method", "path", "skipped", "why"),
    [
        ("POST", "/v1/auth/login", True, "alias of an unprotected legacy path"),
        ("DELETE", "/v1/byok", True, "alias of an unprotected legacy path"),
        ("POST", "/v1/billing/checkout", False, "native /v1 route, must stay protected"),
        ("POST", "/v1/decision-cases", False, "native /v1 route, must stay protected"),
        ("POST", "/auth/login", True, "not under /v1 at all"),
    ],
)
def test_write_protection_skips_aliases_and_only_aliases(
    real_app: FastAPI, method: str, path: str, skipped: bool, why: str
) -> None:
    """Asserted on the predicate directly, because the HTTP test below cannot see this.

    The write lock is released when a request finishes, so two SEQUENTIAL posts never collide --
    an HTTP test would pass even with the exclusion deleted. Only a genuinely concurrent pair or
    this direct assertion distinguishes "excluded" from "protected but uncontended", and this one
    is deterministic.
    """
    from starlette.datastructures import URL

    from apps.api_server.middleware.idempotency import _should_skip_write_protection

    class _Req:
        def __init__(self) -> None:
            self.method = method
            self.url = URL(f"http://t{path}")
            self.app = real_app

    assert _should_skip_write_protection(_Req()) is skipped, why  # type: ignore[arg-type]


def test_the_alias_does_not_pick_up_v1_write_protection(tiny: TestClient) -> None:
    """The concrete regression a naive dual-mount would have shipped.

    IdempotencyMiddleware single-flights byte-identical concurrent writes under /v1/. POST
    /auth/login has never had that, so two identical logins -- a double-clicked form -- would
    start returning 409 resource_write_conflict purely because the caller moved to the versioned
    path. Sequential requests suffice to detect it: the middleware also rebuilds the response and
    adds contract headers, and a held lock would surface as a 409 here under concurrency.
    """
    first = tiny.post("/v1/auth/login", json={"same": "body"})
    second = tiny.post("/v1/auth/login", json={"same": "body"})
    assert first.status_code == 200
    assert second.status_code == 200
    assert "X-Execution-Ms" not in second.headers, (
        "the alias gained the /v1 response contract its legacy twin does not emit"
    )


def test_a_native_v1_route_keeps_its_write_protection_and_contract_headers(
    tiny: TestClient,
) -> None:
    """The other half: the exclusion must be exact, not a /v1/<family> prefix test.

    /v1/billing hosts both an alias (/v1/billing/plans) and four native routes, so a prefix-based
    exclusion would have quietly stripped protection from POST /v1/billing/checkout.
    """
    r = tiny.post("/v1/native-write", json={})
    assert r.status_code == 200
    assert "X-Execution-Ms" in r.headers, "a native /v1 route lost the response contract"


def test_alias_recognition_is_route_exact_not_prefix_based(real_app: FastAPI) -> None:
    """Directly assert the trap on the real app's route set."""
    from starlette.datastructures import URL

    class _Req:
        def __init__(self, path: str) -> None:
            self.url = URL(f"http://t{path}")
            self.app = real_app

    from apps.api_server.middleware.deprecation import is_alias_successor_path

    assert is_alias_successor_path(_Req("/v1/billing/plans")) is True
    assert is_alias_successor_path(_Req("/v1/billing/checkout")) is False
    assert is_alias_successor_path(_Req("/v1/auth/login")) is True
    assert is_alias_successor_path(_Req("/v1/health")) is False


def test_no_alias_name_collides_with_an_existing_route_name(real_app: FastAPI) -> None:
    """Route names drive ``url_path_for``, so an alias must not take a name already in use.

    Asserted only of the ALIASES. The app already carries three pre-existing duplicate names
    (``get_run``, ``list_runs``, ``record_outcome``, from separate routers that happen to use the
    same handler names) -- unrelated to this change, so demanding global uniqueness here would
    fail on someone else's debt and teach the next reader to weaken the assertion.
    """
    names = [r.name for r in _api_routes(real_app)]
    aliases = real_app.state.alias_successor_routes
    assert aliases, "no aliases were mounted"
    for alias in aliases:
        assert alias.name.endswith(ALIAS_SUFFIX), alias.name
        assert names.count(alias.name) == 1, f"alias name {alias.name!r} is not unique"


def test_an_app_without_aliases_is_not_mistaken_for_one_with_them() -> None:
    """is_alias_successor_path must default to False, never crash, on an app that never mounted."""
    from starlette.datastructures import URL

    from apps.api_server.middleware.deprecation import is_alias_successor_path

    bare = FastAPI()

    class _Req:
        url = URL("http://t/v1/auth/login")
        app = bare

    assert is_alias_successor_path(_Req()) is False
