"""A5 — the API stability contract: one table, versioned aliases, and RFC-standard headers.

THE PROBLEM. 42 of the app's 254 routes answer on an UNVERSIONED path: ``/auth/login``,
``/account/devices``, ``/byok``, ``/oauth/device/code``, ``/billing/plans``. 26 of those are
published in ``schemas/openapi/openapi.yaml``, so a customer reading the spec cannot tell which
paths carry a compatibility promise and which are incidental. There is no mechanism to say "this
path still works but a better one exists", so the only ways to move a path were to break it or to
keep it forever.

WHAT THIS ADDS.

1.  A ``/v1`` **alias** for every route in a legacy family, generated from the live route table
    rather than declared by hand, so a route added to ``/auth`` tomorrow gets its successor for
    free and the pair can never drift apart.
2.  **RFC 9745** ``Deprecation`` and **RFC 8594** ``Sunset`` response headers, plus a
    ``rel="successor-version"`` (RFC 5829) ``Link`` pointing at the exact successor for the
    requested path, so a client discovers the migration target from the response it already made.
3.  A single table (``LEGACY_FAMILIES`` + ``UNVERSIONED_BY_DESIGN``) that classifies EVERY
    registered path. ``tests/test_api_stability_contract.py`` fails when a new route is neither
    versioned, aliased, nor explicitly justified — so the contract cannot quietly go stale.

THE ALIAS BEHAVES IDENTICALLY TO ITS LEGACY PATH. That is the whole promise: migrating from
``/auth/login`` to ``/v1/auth/login`` must not change what the endpoint does. Auth, RBAC and
validation all travel with the endpoint function (they are FastAPI dependencies), so those are
identical for free. Two middlewares, though, are keyed on the ``/v1/`` prefix as a proxy for "the
versioned public API":

  * ``IdempotencyMiddleware`` — write-protects ``POST``/``PATCH``/``DELETE`` under ``/v1/``.
  * ``ResponseContractMiddleware`` — adds ``X-Execution-Ms`` / ``X-Mojo-Ms`` under ``/v1/``.

A naive dual-mount would therefore have given ``/v1/auth/login`` a single-flight write lock that
``/auth/login`` has never had — two byte-identical concurrent logins would get
``409 resource_write_conflict`` instead of logging in. So both middlewares now ask
``is_alias_successor_path()`` and skip alias successors, which keeps the pair byte-identical. The
cost is stated in ``gitbook/api/stability.md`` rather than hidden: these families have no
idempotency protection on EITHER path, exactly as before, and gaining it is future work tied to
retiring the legacy path.

Note that ``deployment_router.py`` needs no change: its ``_CONTROL_PLANE_ONLY_PREFIXES`` already
lists ``/v1/auth``, ``/v1/account`` and ``/v1/billing`` — the versioned shape was always the
intended one — and ``_should_proxy`` is an allowlist that none of the new paths are on.

NO SUNSET DATE IS PUBLISHED HERE. ``Deprecation`` says "a successor exists, do not build new
integrations on this path" — a statement of fact this change makes true. ``Sunset`` is a promise to
STOP ANSWERING on a date, which is an owner decision with contractual weight (the same class of
call as the LTS window), so every family ships ``sunset=None`` and emits no ``Sunset`` header.
Filling one in later is a one-line edit to the table; a test covers both branches.
"""

from __future__ import annotations

import inspect
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from email.utils import format_datetime

from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

VERSION_PREFIX = "/v1"

# Human-readable page the `rel="deprecation"` Link points at (RFC 9745 §3).
STABILITY_DOCS_URL = "https://docs.algenta.ai/api/stability"

# Suffix that distinguishes a generated alias from the route it was cloned from. Route `name` and
# `operation_id` must stay unique: FastAPI derives OpenAPI operation ids from them, and duplicate
# operation ids are an invalid spec.
ALIAS_SUFFIX = "_v1_alias"


@dataclass(frozen=True)
class LegacyFamily:
    """An unversioned path family that gains a ``/v1`` successor.

    The successor prefix is DERIVED (``/v1`` + ``prefix``) rather than stored, so a pair cannot be
    mismatched by an edit to one half of the table.
    """

    prefix: str
    # True -> the legacy path emits RFC 9745 `Deprecation`. False -> alias only: the successor is
    # advertised via Link, but the legacy path carries no "stop using this" signal.
    deprecated: bool
    # RFC 9745 requires a Date, and it must be a FIXED constant: computing it at runtime would move
    # every deploy, which is exactly the opposite of what a deprecation date is for.
    deprecated_on: date | None
    # RFC 8594 `Sunset` -- the date the path stops answering. None -> no removal date published.
    sunset_on: datetime | None
    why: str

    @property
    def successor_prefix(self) -> str:
        return f"{VERSION_PREFIX}{self.prefix}"


LEGACY_FAMILIES: tuple[LegacyFamily, ...] = (
    LegacyFamily(
        prefix="/auth",
        deprecated=True,
        deprecated_on=date(2026, 8, 28),
        sunset_on=None,
        why=(
            "Signup/login/verify/password-reset. Unversioned since the first release; the "
            "versioned successor is the supported path for new integrations."
        ),
    ),
    LegacyFamily(
        prefix="/account",
        deprecated=True,
        deprecated_on=date(2026, 8, 28),
        sunset_on=None,
        why=(
            "Website dashboard surface (devices, seats, usage, team, billing, org list), "
            "authenticated by the signed-in user's session rather than an API key. 11 of its 13 "
            "routes are published in the OpenAPI spec, so it reads as public API and needs to sit "
            "under the same versioned contract as the rest of it."
        ),
    ),
    LegacyFamily(
        prefix="/billing",
        deprecated=True,
        deprecated_on=date(2026, 8, 28),
        sunset_on=None,
        why=(
            "GET /billing/plans is the only unversioned route left in a router whose other four "
            "routes are already /v1/billing/*. The successor removes that inconsistency."
        ),
    ),
    LegacyFamily(
        prefix="/byok",
        deprecated=True,
        deprecated_on=date(2026, 8, 28),
        sunset_on=None,
        why="Bring-your-own-key provider credentials for the website.",
    ),
    LegacyFamily(
        prefix="/oauth",
        # ALIAS ONLY, deliberately not deprecated. RFC 8628 device-login is what released CLI
        # builds already in the field talk to, and they cannot be updated retroactively. Marking it
        # deprecated would tell every existing CLI user their working install is on its way out.
        # It becomes deprecated when a CLI that prefers the versioned path has shipped and the
        # older builds are out of support -- a sequencing decision, not a code change.
        deprecated=False,
        deprecated_on=None,
        sunset_on=None,
        why=(
            "RFC 8628 device-authorization flow used by the released CLI. Aliased so new clients "
            "can use the versioned path; the legacy path carries no deprecation signal while "
            "shipped CLI builds depend on it."
        ),
    ),
)

# Paths that are deliberately NOT versioned, each with the reason. This is the other half of the
# classification: `tests/test_api_stability_contract.py` fails on any registered path that is
# neither /v1, nor in a legacy family, nor listed here -- so "we forgot to version it" and "we
# decided not to version it" can no longer look the same.
UNVERSIONED_BY_DESIGN: dict[str, str] = {
    "/mcp": (
        "The MCP endpoint URL is the value customers paste into their client configuration. MCP "
        "versions itself through the MCP-Protocol-Version header, not the path, so moving it under "
        "/v1 would break every configured client to express something the protocol already "
        "expresses."
    ),
    "/.well-known": (
        "RFC 8615 fixes these paths. A client fetching /.well-known/jwks.json is following the "
        "spec, not our routing."
    ),
    "/webhooks": (
        "Receiver URL registered in the GitHub App configuration. GitHub delivers to the URL "
        "recorded at install time; changing the path silently stops deliveries for every existing "
        "installation."
    ),
    "/github": (
        "GitHub App install/setup callback URLs, registered with GitHub for the same reason as "
        "/webhooks."
    ),
    "/internal": (
        "Service-to-service only, never published in the spec, and carries no compatibility "
        "promise to anyone outside this deployment."
    ),
    "/metrics": "Prometheus scrape endpoint; /metrics is the convention every scraper assumes.",
    "/docs": "Swagger UI. A browser surface, not an API.",
    "/redoc": "ReDoc UI. A browser surface, not an API.",
    "/openapi.json": "The spec document itself; FastAPI's conventional location.",
    "/openapi": (
        "Machine-readable descriptors served alongside the spec (decision-agent manifest), "
        "referenced by URL from published documentation."
    ),
}


def _matches(path: str, prefix: str) -> bool:
    """Family membership: the prefix itself or a child of it -- never a mere string prefix.

    ``/byok`` must match ``/byok`` and ``/byok/anything`` but NOT ``/byoketc``, which a bare
    ``startswith`` would happily claim.
    """
    return path == prefix or path.startswith(f"{prefix}/")


def family_for(path: str) -> LegacyFamily | None:
    for family in LEGACY_FAMILIES:
        if _matches(path, family.prefix):
            return family
    return None


def successor_for(path: str) -> str | None:
    """``/auth/login`` -> ``/v1/auth/login``. None when the path is not in a legacy family."""
    family = family_for(path)
    if family is None:
        return None
    return f"{VERSION_PREFIX}{path}"


def unversioned_reason(path: str) -> str | None:
    for prefix, reason in UNVERSIONED_BY_DESIGN.items():
        if _matches(path, prefix):
            return reason
    return None


# ── generating the aliases ──────────────────────────────────────────────────────────────────────

# Derived from APIRoute's own signature rather than hand-listed, so a FastAPI upgrade that adds a
# route option carries it onto the aliases automatically instead of silently dropping it. Anything
# the signature declares but the instance does not expose is reported by
# test_every_api_route_option_is_carried_onto_the_alias, which fails the build rather than letting
# a dropped option through unnoticed.
_ROUTE_PASSTHROUGH_PARAMS: tuple[str, ...] = tuple(
    name
    for name in inspect.signature(APIRoute.__init__).parameters
    # path/endpoint are positional; name/operation_id must be made unique per alias.
    if name not in {"self", "path", "endpoint", "name", "operation_id"}
)

def route_params_without_attribute(route: APIRoute) -> tuple[str, ...]:
    """Options ``APIRoute.__init__`` accepts but this INSTANCE does not expose, so cloning drops them.

    Must be asked of an instance, never of the class: every one of these is assigned in
    ``__init__``, so ``hasattr(APIRoute, name)`` is False for all 27 of them and a class-level
    check would report the entire option set as uncopyable.
    """
    return tuple(name for name in _ROUTE_PASSTHROUGH_PARAMS if not hasattr(route, name))


def _effective_summary(route: APIRoute) -> str | None:
    """The summary the legacy route actually PUBLISHES, pinned so the alias shows the same one.

    When a route declares no ``summary``, FastAPI generates one from the route name at
    spec-build time (``name.replace("_", " ").title()``). The alias needs a different name for
    operation-id uniqueness, so left alone it published "Device Code V1 Alias" -- alias
    bookkeeping leaking into customer-facing documentation. Pinning the legacy route's effective
    summary onto the alias keeps the two operations identical in the spec.

    This reimplements FastAPI's fallback rule, so it could drift on an upgrade;
    test_published_operation_is_identical_apart_from_path_and_operation_id compares the two
    published operations and fails if it ever does.
    """
    if route.summary:
        return route.summary
    return route.name.replace("_", " ").title()


def _clone_route(route: APIRoute, new_path: str) -> APIRoute:
    kwargs = {
        name: getattr(route, name) for name in _ROUTE_PASSTHROUGH_PARAMS if hasattr(route, name)
    }
    kwargs["summary"] = _effective_summary(route)
    original_operation_id = getattr(route, "operation_id", None)
    return APIRoute(
        new_path,
        route.endpoint,
        name=f"{route.name}{ALIAS_SUFFIX}",
        operation_id=(
            f"{original_operation_id}{ALIAS_SUFFIX}" if original_operation_id else None
        ),
        **kwargs,
    )


def mount_versioned_aliases(app: FastAPI) -> tuple[APIRoute, ...]:
    """Register a ``/v1`` successor for every legacy-family route, and mark the legacy ones.

    Call ONCE, after every ``include_router``. Returns the aliases it created and records them on
    ``app.state.alias_successor_routes`` so the ``/v1``-keyed middlewares can recognise them.
    """
    api_routes = [r for r in app.router.routes if isinstance(r, APIRoute)]
    # (path, methods) already answered by a hand-written route -- an alias must never shadow one.
    occupied = {(r.path, frozenset(r.methods or ())) for r in api_routes}

    created: list[APIRoute] = []
    for route in api_routes:
        family = family_for(route.path)
        if family is None:
            continue
        new_path = f"{VERSION_PREFIX}{route.path}"
        if (new_path, frozenset(route.methods or ())) in occupied:
            continue
        created.append(_clone_route(route, new_path))
        # Mark the LEGACY route deprecated in the published spec (OpenAPI's own `deprecated` flag,
        # which Swagger/ReDoc render struck through). Deliberately NOT include_in_schema=False:
        # hiding ~26 paths that still answer would make the spec lie by omission, which is the
        # exact failure A1's truth gate exists to prevent. The alias keeps the original flag.
        if family.deprecated:
            route.deprecated = True

    app.router.routes.extend(created)
    app.state.alias_successor_routes = tuple(created)
    # app.openapi() memoises into app.openapi_schema; drop it so the aliases appear.
    app.openapi_schema = None
    return tuple(created)


_SUCCESSOR_PREFIXES: tuple[str, ...] = tuple(f.successor_prefix for f in LEGACY_FAMILIES)


def is_alias_successor_path(request: Request) -> bool:
    """True when this request hit a generated alias rather than a hand-written ``/v1`` route.

    Matched against the alias routes' own compiled regexes, NOT by prefix. ``/v1/billing`` is both
    an alias prefix (for ``/billing/plans``) and the home of four native routes, so a prefix test
    would strip write protection from ``POST /v1/billing/checkout``. The cheap ``startswith``
    below is only a pre-filter to keep the regex sweep off the hot path.
    """
    path = request.url.path
    if not path.startswith(_SUCCESSOR_PREFIXES):
        return False
    routes: Iterable[APIRoute] = getattr(request.app.state, "alias_successor_routes", ())
    return any(route.path_regex.fullmatch(path) for route in routes)


# ── the headers ─────────────────────────────────────────────────────────────────────────────────


def _deprecation_header(family: LegacyFamily) -> str | None:
    """RFC 9745: an Item Structured Field whose value is a Date -- ``Deprecation: @1756339200``."""
    if not family.deprecated or family.deprecated_on is None:
        return None
    moment = datetime.combine(family.deprecated_on, time.min, tzinfo=UTC)
    return f"@{int(moment.timestamp())}"


def _sunset_header(family: LegacyFamily) -> str | None:
    """RFC 8594: an HTTP-date -- ``Sunset: Sat, 31 Dec 2026 23:59:59 GMT``."""
    if family.sunset_on is None:
        return None
    return format_datetime(family.sunset_on, usegmt=True)


class DeprecationMiddleware(BaseHTTPMiddleware):
    """Attach the stability headers to responses from a legacy-family path."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        path = request.url.path
        family = family_for(path)
        if family is None:
            return response

        # A 404 is not an endpoint, so there is nothing to deprecate and no successor to point at:
        # `/v1/auth/typo` does not exist either, and advertising it would send the caller to a
        # second 404.
        if response.status_code == 404:
            return response

        deprecation = _deprecation_header(family)
        if deprecation:
            response.headers.setdefault("Deprecation", deprecation)

        sunset = _sunset_header(family)
        if sunset:
            response.headers.setdefault("Sunset", sunset)

        # append, never set: Link is a list field and something else may already have added one.
        response.headers.append("Link", f'<{VERSION_PREFIX}{path}>; rel="successor-version"')
        if deprecation:
            response.headers.append(
                "Link", f'<{STABILITY_DOCS_URL}>; rel="deprecation"; type="text/html"'
            )
        return response
