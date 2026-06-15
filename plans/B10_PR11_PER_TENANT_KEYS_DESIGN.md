# B10 PR11 — Per-Tenant Key Enforcement (design note)

Status: **design / not yet implemented.** Decision-engine + Codna (two repos). Audit ref:
`project_egress_audit_residuals` → "PR11, the audit's top rec."

## 1. Problem

The resolution **seam** shipped in PR10 (`apps/api_server/services/tenant_keys.py`):

- `resolve_provider_api_key(api_key_env)` / `resolve_engine_api_key()` — precedence **override > env**;
- `ALGENTA_REQUIRE_PER_TENANT_KEYS=1` ⇒ a missing override **fails closed** (never reuse the shared env key);
- request-scoped `ContextVar` overrides `set_*_override` / `reset_*_override`.

But the seam is **inert**: `set_provider_key_override` / `set_engine_key_override` have **zero production
callers**, and there is **no per-org key store** (the `Organization` model has only
`name/slug/plan/status/stripe_customer_id`; no credentials table). So in multi-tenant mode every call
fails closed. PR11 = the **store** + the **wiring that sets the override from the authenticated org**.

## 2. Constraints

- **"Any customer"** (hard product constraint, [[project_any_customer_multitenancy]]): arbitrary,
  self-onboarding tenants. A static operator-curated `ALGENTA_PER_TENANT_KEYS` env map does **not**
  qualify — the operator can't pre-register every customer. ⇒ the store must be **populated at runtime
  by an onboarding/API flow**.
- **Self_hosted + cloud, both.** Unlike a pure-SaaS product, we also run self_hosted/air_gapped (the
  B10 premise). The design must keep the **env key as the single-tenant/pooled default** and layer
  per-org keys on top — exactly the existing `override > env` precedence.
- **Fail-closed** is already handled by `require_per_tenant_keys()`.

## 3. The execution-context problem (why a request-only ContextVar is insufficient)

A repository/agent run reaches the LLM/engine key in **three** different contexts:

| Context | Trigger | ContextVar from an API auth hook? |
|---|---|---|
| Sync in-request | `async_execution=False` (default) | ✅ propagates |
| Fire-and-forget | `asyncio.create_task(_execute_repository_job_in_process)` | ⚠️ snapshot at create-time; the request's `finally` reset can race |
| **Worker** | `enqueue_repository_job` → **separate process** | ❌ ContextVar does not exist there |

For async runs, `task_spec["engine"]["api_key"] = resolve_engine_api_key()` is built **in the worker**,
then passed to the Codna sidecar. The worker rebuilds `(connector, request)` from `job.request_payload`
and **has `job.org_id`** (`repository_job_service._load_connector(..., org_id=job.org_id)`).

**Conclusion:** the override must be settable **per execution context from `org_id`**, and the key
**source must be process-independent** (readable by API *and* worker). A DB-backed store satisfies this
(the worker has a DB session); a ContextVar set only in the API request does not.

**Never** persist the resolved key into `job.request_payload` (secret at rest in the jobs table /
logs) — the worker must **re-resolve by `org_id`**.

## 4. What Cursor (and peers) do — reference model

- **Pooled / managed (default):** the backend proxies model calls with **its own** provider keys,
  metered against the subscription. The user supplies nothing. ⇒ in our terms, the **env key** is the
  pooled key.
- **BYOK (bring your own key):** the user enters their own Anthropic/OpenAI/Google key in settings;
  stored **server-side, encrypted**, used for that account's requests, retrievable/rotatable via the
  UI, never sent to the client. ⇒ in our terms, the **per-org override**.
- **Teams/Enterprise:** org-scoped, admin-managed keys + SSO + privacy/zero-retention mode; self-serve
  via the team dashboard.
- **Storage:** encrypted at rest, keyed by account/org, resolved server-side per request, rotatable.

**Takeaway:** Cursor's model maps **exactly** onto the existing `override > env` seam — env = pooled,
DB override = BYOK — and confirms the **DB-backed, encrypted, self-serve, per-org** store. We are a
**superset**: we also support self_hosted/air_gapped (env-only, no DB BYOK) and the engine-behind/Codna
split that Cursor doesn't have.

## 5. Proposed architecture

```
                         ┌─────────────────────────────────────────────┐
   API request ─────────▶│ tenant_key_context dependency (yield)        │
   (get_current_org)     │   token = set_*_override(resolve(org_id));   │──┐
                         │   try: yield   finally: reset_*_override     │  │
                         └─────────────────────────────────────────────┘  │
   Worker / FAF ────────▶ set_*_override(resolve(job.org_id)) at job start │  ▼
   (job.org_id)            ... finally reset                               │ resolve_provider_api_key()
                                                                           │ resolve_engine_api_key()
                         ┌─────────────────────────────────────────────┐  │  (UNCHANGED call sites)
                         │ KeySource (pluggable, process-independent)    │◀─┘
                         │   default: DB-backed encrypted per-org store  │
                         │   resolve_org_keys(org_id) -> OrgKeys (cached) │
                         └─────────────────────────────────────────────┘
```

- **KeySource** — a small interface `resolve_org_keys(org_id) -> OrgKeys | None` with a TTL cache.
  Default impl = **DB-backed encrypted store**. (A self_hosted operator that doesn't want a DB store
  simply leaves `ALGENTA_REQUIRE_PER_TENANT_KEYS` off and uses the env key — unchanged.)
- **Two override entry points**, both setting the existing ContextVar so **call sites stay unchanged**:
  1. **API**: a FastAPI dependency-with-`yield` (composed after `get_current_org`) — set from
     `auth["org_id"]`, reset in `finally`. Add to the protected-router dependency list.
  2. **Worker / fire-and-forget**: set from `job.org_id` at the start of `execute_repository_job`
     (and the in-process fallback), reset in `finally`. This is what makes the engine-key path
     (built in the worker) correct.
- **Engine key → Codna sidecar:** unchanged transport — `task_spec["engine"]["api_key"] =
  resolve_engine_api_key()` now returns the per-org key because the worker set the override.
- **Provider key → Codna sidecar (cross-repo, PR11b):** the sidecar's agent LLM is BYOM and currently
  uses its **own** env key. To make the **agent's** LLM calls per-tenant, thread the resolved per-org
  provider key into the run payload as `task_spec.provider_api_key` (or `RunAgentArgs.provider_api_key`)
  and have Codna prefer it over its env. This is the only Codna-side change.

## 6. Storage (DB-backed, encrypted)

- New table `tenant_provider_keys` (or encrypted columns on `Organization`): `(org_id, backend,
  encrypted_key, created_at, rotated_at)` — **per (org, backend)** because the provider key is
  backend-specific (anthropic vs openai vs google). `resolve_provider_api_key(api_key_env)` already
  knows the backend's env-var name → map env-var/backend → row. Engine key is a single per-org value.
- Encryption: reuse `config_crypto` (the same envelope used for connector `config_json`).
- **Management API** (self-serve, satisfies "any customer"): `PUT/DELETE /v1/account/provider-keys`
  (+ engine key), org-scoped, admin role, set/rotate, write-only (never returned). Onboarding writes here.
- **Caching:** TTL cache (e.g. 60 s) keyed by `org_id`; rotation = store update + cache bust.

## 7. Security posture

- Override is **server-derived from the authenticated org only** — never caller-supplied (the seam
  docstring already mandates this).
- Resolved keys **never** enter `job.request_payload`, logs, proofs, or audit metadata (the existing
  `secret_redaction` covers logs/artifacts; assert it covers these fields).
- Encrypted at rest; write-only API; `require_per_tenant_keys()` fail-closed in multi-tenant.
- Worker re-resolves by `org_id` — no secret travels through the queue.

## 8. Proposed PR breakdown

- **PR11a (decision-engine, the core):** KeySource interface + DB-backed store + migration +
  `config_crypto` encryption + the **API dependency hook** + the **worker/FAF hook** + tests
  (deny/allow/rotation/worker-context). Makes the seam live end-to-end **inside** decision-engine.
- **PR11b (Codna):** `RunAgentArgs.provider_api_key` plumbing so the agent's LLM uses the per-tenant
  key; decision-engine passes `task_spec.provider_api_key`. Define + version the contract.
- **PR11c (management/onboarding):** the self-serve `/v1/account/provider-keys` CRUD + rotation UI/API.

PR11a alone closes the audit's "inert seam" gap and is independently shippable & testable.

## 9. Open decisions (need a call)

1. **Store shape:** dedicated `tenant_provider_keys` table **(recommended)** vs encrypted columns on
   `Organization`. Table = clean per-(org,backend) + rotation history; columns = fewer moving parts.
2. **Provider-key granularity:** per-(org, backend) map **(recommended; matches `api_key_env`)** vs a
   single active provider key per org.
3. **Scope of the first PR:** PR11a only (recommended — land enforcement, defer Codna + CRUD) vs
   PR11a+b together.
4. **Self_hosted fallback:** keep env key as pooled default **(recommended)**; confirm no operator-map
   source is wanted as an additional KeySource impl.
