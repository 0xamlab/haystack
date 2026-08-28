---
icon: shield-check
description: Which Algenta paths carry a compatibility promise, how deprecation is announced in the response itself, and what changes without notice.
---

# API stability

Every path this engine answers falls into exactly one of four classes. A test in the engine's own
suite fails the build if a route is added that fits none of them, so this page cannot quietly fall
behind the code.

| Class | Paths | Promise |
| --- | --- | --- |
| Versioned API | `/v1/*` | Backward-compatible within `v1`. Additive change only. |
| Versioned alias | `/v1/auth/*`, `/v1/account/*`, `/v1/billing/plans`, `/v1/byok`, `/v1/oauth/device/*` | Same promise as `/v1`. The supported path for these families. |
| Deprecated legacy | `/auth/*`, `/account/*`, `/billing/plans`, `/byok`, `/oauth/device/*` | Still answers, unchanged. Announces its successor in every response. |
| Not part of the API | `/mcp/*`, `/.well-known/*`, `/metrics`, `/docs`, `/redoc`, `/openapi.json`, GitHub App callbacks, internal service paths | No version promise; governed by the protocol or convention that owns the path. |

## What backward-compatible means inside `v1`

Within `v1` these are **compatible** changes and ship without notice:

* a new endpoint, a new optional request field, a new response field;
* a new optional query parameter, a new enum value in a field documented as extensible;
* a new HTTP header;
* a new error `code` for a condition that previously produced a more general one.

These are **breaking** and do not happen inside `v1`:

* removing or renaming a path, a response field, or an error `code`;
* making an optional request field required, or narrowing an accepted type;
* changing the success status code, or the meaning of an existing field;
* removing an enum value.

Write clients that ignore unknown response fields and unknown headers. Match error conditions on
the `code` string rather than on prose or on the HTTP status alone — see
[Error codes](errors.md).

## Deprecation is announced in the response

A request to a deprecated path answers normally and adds standard headers, so a client discovers
the migration target from traffic it is already sending — no changelog subscription required.

```
$ curl -sSD - -o /dev/null https://your-engine.example.com/auth/login

deprecation: @1787875200
link: </v1/auth/login>; rel="successor-version"
link: <https://docs.algenta.ai/api/stability>; rel="deprecation"; type="text/html"
```

* **`Deprecation`** ([RFC 9745](https://www.rfc-editor.org/rfc/rfc9745.html)) — the date the path
  was deprecated, as a structured-field Date (`@` followed by Unix seconds). Its presence means
  *do not build new integrations on this path*. It does **not** mean the path is going away on a
  date.
* **`Link; rel="successor-version"`** ([RFC 5829](https://www.rfc-editor.org/rfc/rfc5829.html)) —
  the exact replacement for **the path you requested**, not the family root. Substituting it is
  the whole migration.
* **`Sunset`** ([RFC 8594](https://www.rfc-editor.org/rfc/rfc8594.html)) — the date a path stops
  answering. **No Algenta path publishes one today.** When one is announced it appears here and in
  the header, never only in the header.

A `404` under a deprecated family carries none of these headers: there is no endpoint to deprecate,
and its notional successor would `404` as well.

The published OpenAPI spec marks every deprecated operation with OpenAPI's own `deprecated: true`,
so generated clients and Swagger/ReDoc show it without reading this page. Deprecated paths are
**not** hidden from the spec — a path that still answers stays documented.

## Migrating is a path change and nothing else

An alias and its legacy path are the same endpoint: the same handler, the same authentication, the
same request and response bodies, the same status codes, the same headers. The engine's test suite
compares each pair's published OpenAPI operation and its live response headers, so the two cannot
drift apart.

```bash
# before
curl -X POST "$BASE/auth/login"      -d '{"email":"…","password":"…"}'
# after — same request, same response
curl -X POST "$BASE/v1/auth/login"   -d '{"email":"…","password":"…"}'
```

One consequence is worth stating rather than leaving to be discovered. Two `/v1` behaviours are
scoped to the natively-versioned API and are **not** applied to these aliases, precisely so the
pair stays identical:

* **Write conflict protection.** `POST`/`PATCH`/`DELETE` on a native `/v1` path single-flights
  byte-identical concurrent requests and honours `Idempotency-Key`. The legacy families have never
  had this, and the alias does not add it — otherwise two identical concurrent logins would start
  returning `409 resource_write_conflict` merely because the caller moved to the versioned path.
  Extending protection to these families is planned for when the legacy paths retire.
* **`X-Execution-Ms` / `X-Mojo-Ms`.** Emitted by native `/v1` routes, not by these families on
  either path.

Everything else about the versioned contract — error envelope, `request_id`, authentication — is
identical, because it was never keyed on the path.

## `/oauth/device/*` is aliased but not deprecated

The device-authorization endpoints ([RFC 8628](https://www.rfc-editor.org/rfc/rfc8628.html)) are
what released CLI builds already talk to, and an installed CLI cannot be updated retroactively.
They therefore emit a `successor-version` Link — new clients should use `/v1/oauth/device/*` — but
no `Deprecation` header, because telling every existing CLI user their working install is on the
way out would be false. That changes only once a CLI preferring the versioned path has shipped and
older builds are out of support.

## Notice periods

* A path in the **Deprecated legacy** class keeps answering until a `Sunset` date is published on
  this page.
* Removal is never the first announcement: a `Deprecation` header and a documented successor come
  first, and the successor is available before the legacy path is deprecated.
* Because Algenta is self-hosted, **you control when you upgrade.** A version you have deployed
  does not change under you; these classes describe what a future engine version may change, not
  what your running deployment does.

## Paths deliberately outside the version scheme

These are not oversights, and each is fixed by something other than our routing:

| Path | Why it is not versioned |
| --- | --- |
| `/mcp/*` | The MCP endpoint URL is the value you paste into a client's configuration. MCP versions itself through the `MCP-Protocol-Version` header, so moving the path would break configured clients to express something the protocol already expresses. |
| `/.well-known/*` | Fixed by [RFC 8615](https://www.rfc-editor.org/rfc/rfc8615.html). A client fetching `/.well-known/jwks.json` is following the spec. |
| `/metrics` | The Prometheus scrape convention. |
| `/docs`, `/redoc`, `/openapi.json` | Documentation surfaces for a browser, not API endpoints. |
| GitHub App callbacks | The receiver URL is recorded by GitHub at install time; changing it stops deliveries for existing installations. |
| Internal service paths | Service-to-service within one deployment, never published in the spec, no external promise. |

## Checking a deployment yourself

The contract is machine-readable from any running engine — you do not have to take this page's word
for it:

```bash
# every deprecated operation in the published spec
curl -sS "$BASE/openapi.json" \
  | jq -r '.paths | to_entries[] | .key as $p | .value | to_entries[]
           | select(.value.deprecated == true) | "\(.key|ascii_upcase) \($p)"'

# the successor for a path you depend on
curl -sSD - -o /dev/null "$BASE/byok" | grep -i '^link:'
```
