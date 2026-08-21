---
icon: key
description: Engineering reference for the server licensing layer — Compute Units (4 effective vCPU = 1 unit), device vs deployment scope, strict JOSE verification, Relay leases, air-gap ceremony.
---

# Server / Enterprise Licensing — Compute Units (engineering reference)

Internal engineering doc for the additive server/enterprise licensing layer. External-facing
copy lives elsewhere; this file documents mechanics, seams, and operating steps. Plan of record:
`~/.claude/plans/need-full-research-how-enumerated-hollerith.md`.

## Model in one paragraph

Personal use is unchanged: Community ($0) / Pro / Team remain **per-device**, fully local,
offline-capable. On top of that, organizations license **server deployments** by **Compute
Units**: `4 concurrent effective vCPU = 1 Compute Unit`, aggregated across the licensed pool.
The two worlds are one runtime, one verifier, one entitlement model, separated by a single
signed claim — `license_scope` = `device` (default) or `deployment`. Detection of a cloud/VM/
CI host is **evidence only** and can never move a runtime into deployment scope; only an
explicit deployment artifact does. Lapse never hard-cuts — it settles at the always-free
Community floor.

## Two scopes (`license_scope`)

| | `device` (personal, shipped) | `deployment` (server, this layer) |
|---|---|---|
| Default | yes — legacy/absent claim ⇒ device | activated ONLY by explicit artifact |
| Metric | devices + per-device workers | Compute Units (pooled) |
| Activation | `algenta login` / device registration | `ALGENTA_DEPLOYMENT_ID`, a deployment-bound license file, or a Relay lease |
| Sees units/pools/Relay | never | yes |
| Binding | device key | deployment/Relay key |

Detection (Docker/WSL/VDI/cloud-DMI/CI/K8s) is silent risk-signal input only — see
[apps/runtime/host_class.py](../apps/runtime/host_class.py). It never selects scope.

## Compute-Unit measurement — [apps/runtime/capacity.py](../apps/runtime/capacity.py)

`effective_vcpu` = the **minimum finite positive** constraint among: process CPU affinity,
cpuset, cgroup v2 `cpu.max` (walking ancestors — a parent may be tighter), cgroup v1 CFS
quota, and the host CPU count (fallback only). So a 2-vCPU-limited pod on a 96-vCPU node
measures 2.

Aggregation rounds **once at the pool level**, never per node:

```text title="pool aggregation"
node_contribution_i = effective_vcpu_i / vcpu_per_unit      # fractional, unrounded
pool_units          = ceil( Σ node_contribution_i )
```
Consequence (the anti-per-node-minimum rule): 20 pods × 0.5 vCPU = 10 vCPU = `ceil(10/4)` = **3
units**, not 20. A 96-vCPU box = 24 units. Per-order minimums (pinned 4, floating 16) are
commercial, applied at purchase — never per node.

## License claims (v2, additive)

New signed claims (emitted only for deployment scope, so device tokens keep their exact shape):
`license_scope`, `deployment_id`, `max_concurrent_units`, `max_effective_vcpu`, `vcpu_per_unit`,
`measurement_policy_version`, `grace_policy_id`. Parsed in
[apps/runtime/license.py](../apps/runtime/license.py) (`DeviceLicense`,
`_device_license_from_payload`, `mint_device_token`), resolved from the entitlement tier in
[entitlement_service.py](../apps/api_server/services/entitlement_service.py) (`to_license_claims`
emits the subset only when `is_deployment_scope()`).

## Strict verification — [apps/runtime/license_verify.py](../apps/runtime/license_verify.py)

New server/deployment tokens use the strict JOSE profile (`typ=algenta-license+jwt`), RFC 8725:
RS256 only (rejects `alg=none` and RS/HS confusion), `kid` resolved only against an embedded
trust bundle (multi-key for rotation), exact `iss`/`aud`/`typ`/`sub` match, required-claim
enforcement, no token-supplied key URLs, and exact `product`/`edition` match so a Telys license
can never activate Algenta. `_parse_token` routes strict-profile tokens here and never falls
back to the legacy path for them. **Non-breaking:** every existing field license (no such `typ`)
keeps the current path. The trust bundle comes from `ALGENTA_LICENSE_TRUST_BUNDLE` (JSON
`{kid: pem}`) or the legacy single-key envs. The runtime's own product is
`ALGENTA_RUNTIME_PRODUCT` (default `algenta`).

Full artifact split (stripping HS256 from the production wheel) and native-daemon-only
verification are the remaining hardening steps (see "Not yet shipped").

## Enforcement (offline, air-gap-safe)

- **L1 device/deployment binding** — a bound token runs only on its node
  ([node_broker.py](../apps/runtime/node_broker.py) `assert_node_binding`).
- **Pinned-node Compute-Unit ceiling** — a node measured at more units than the whole pool can
  never boot (`assert_deployment_capacity`, wired at
  [daemon.py](../apps/runtime/daemon.py) startup). Local, no coordination backend needed.
- **Distributed pool sum** across many nodes (floating pool) is the L3 (connected control
  plane) / L4 (customer-run Relay) lease authority — see "Not yet shipped".

All enforcement is dark by default (gated on `require_local_license` /
`enforce_license_validation` / `ALGENTA_ENFORCE_ACTIVE_NODE_CAP`), fail-safe, and never hard-cuts.

## No per-customer usage measurement

The engine runs entirely on the customer's own infrastructure and the no-phone-home policy
holds: **we do not measure, report, or true-up on per-customer usage.** Billing is by
**purchased Compute Units** (Stripe quantity / contract) — the license carries
`max_concurrent_units`, and the runtime enforces `capacity ≤ units` **locally**. Need more
capacity? Buy more units → a new license with a higher ceiling. There is no usage meter, no
usage report, no phone-home telemetry, and no usage-based true-up. Capacity is licensed and
locally capped, not metered.

## Lapse → Community floor (never hard-cut)

A lapsed/expired deployment license that can't renew settles at the always-free Community floor
(1 unit / 1 worker, non-commercial) plus full diagnostics/config/export — never a dead process.
The Community fallback carries `deployment_id` so the recovery floor is scoped **once per
deployment** (elected recovery runtime), never one free instance per node/pod. See
`_make_community_license` in [license.py](../apps/runtime/license.py).

## All five editions, one model

`algenta_server`, `codna_server`, `telys_server`, `sqai_server`, `cohenta_server` are built from
one factory (`_server_record` in entitlement_service) + matching `plan_limits` entries — the same
Compute-Unit model; only the product grant differs. Editions are distinguished by the signed
`product` claim (enforced by the strict verifier's cross-product check).

## Operating steps

**Mint an offline server (air-gap) license:**

```bash title="mint an offline server license"
python3 scripts/issue_offline_license.py \
  --device-id "$DEPLOYMENT_NODE_ID" --plan algenta_server --output server.jwt \
  --private-key-file "$CONTROL_PLANE_PRIVATE_KEY_PEM" --org-id "$ORG_ID" \
  --license-scope deployment --deployment-id "$DEPLOYMENT_ID" \
  --max-concurrent-units "$PURCHASED_UNITS" --vcpu-per-unit 4 \
  --measurement-policy-version cgroup-v1 --grace-policy-id community-floor-v1 \
  --commercial-use --offline-grace-days 30 --paid-selfhost
```
`--paid-selfhost` runs the anti-fleet guard ([license_mint_guard.py](../scripts/license_mint_guard.py)):
a deployment license with no `max_concurrent_units` ceiling is rejected as fleet-portable.

**Runtime env:** license via `ALGENTA_LICENSE_JWT`(`_FILE`) or the runtime dir file; trust bundle
via `ALGENTA_LICENSE_TRUST_BUNDLE`(`_FILE`); product via `ALGENTA_RUNTIME_PRODUCT`; deployment
activation via `ALGENTA_DEPLOYMENT_ID`.

## Tests

- [tests/test_runtime_capacity.py](../tests/test_runtime_capacity.py) — cgroup v1/v2, fractional
  quotas, cpuset, nested ancestors, no-quota fallback, pool rounding (20-pod case).
- [tests/test_runtime_host_class.py](../tests/test_runtime_host_class.py) — cloud-vendor
  classification + false-positive protection (Docker/WSL/CI/QEMU on a laptop ≠ datacenter).
- [tests/test_license_verify_strict.py](../tests/test_license_verify_strict.py) — the full
  attack matrix (alg=none, RS/HS, wrong iss/aud/product, unknown/missing kid, jku, bad sig,
  size bounds, rotation).
- [tests/test_deployment_scope.py](../tests/test_deployment_scope.py) — Compute-Unit admission,
  strict routing incl. cross-product rejection, deployment-aware Community fallback.

## Shipped (this build, tested)

- **C0 Stripe catalog compiler + EntitlementSnapshot** —
  [stripe_catalog_compiler.py](../apps/api_server/services/stripe_catalog_compiler.py)
  (typed `thyn_license_v1` parse, full validation matrix, immutable `CatalogRelease` +
  `policy_hash`, fetch-injectable) and
  [entitlement_snapshot.py](../apps/api_server/services/entitlement_snapshot.py) (three source
  types incl. `community_baseline` — no Stripe subscription needed for the free floor).
- **C deployment activation** — `mint_deployment_token` (strict profile) in
  [license.py](../apps/runtime/license.py), the
  [deployment_service.py](../apps/api_server/services/deployment_service.py) mint seam, and the
  connected `POST /v1/deployment/activate`
  ([deployment_activation.py](../apps/api_server/routers/deployment_activation.py)) +
  `deployment_license_registrations` table (migration 0059) + `<edition>_server` org plans.
- **A `jti` revocation** — the strict verifier denies positively-listed jtis (fail-open when no
  denylist); runtime rejects dev-secret HS256 forgeries under the production profile.
- **A RS256-only production mode** — `ALGENTA_LICENSE_RS256_ONLY=1` (implied by
  `require_local_license`) makes the verifier reject EVERY HS256 token (dev-stub AND
  control-plane secret); only asymmetric RS256 verifies. The runtime half of the artifact split;
  preflight guard [scripts/check_license_hardening.py](../scripts/check_license_hardening.py)
  fails a deploy that isn't hardened. Default OFF preserves shipped HS256 internal consumers.
- **E Relay** — the full lease authority for air-gapped/floating pools:
  [relay_lease.py](../apps/runtime/relay_lease.py) (pool ceiling fail-closed, idempotent
  acquire, borrow-with-expiry, TTL reclaim, never-evict, node ceiling);
  [relay_delegation.py](../apps/runtime/relay_delegation.py) (root→pool-root→node-lease signing
  + verification, relay-key thumbprint binding so a stolen pool-root file without the relay
  private key is useless); [relay_server.py](../apps/runtime/relay_server.py) (the customer-run
  HTTP heartbeat service — `POST /v1/relay/{lease,heartbeat,release}` + status — fail-closed at
  construction if the pool root doesn't bind this relay's key).
- **L3 connected pool authority** — `POST /v1/deployment/node/heartbeat` + the
  `deployment_node_leases` table (migration 0060): the control plane admits an engine node only
  if the sum of active peers' Compute Units stays within the deployment's pool (server-side, the
  connected equivalent of the Relay ledger; unit-weighted, idempotent, never-evict).

## Adversarial-review hardening (applied)

A 5-dimension adversarial review (12 confirmed findings) drove these fixes, all tested:
- **Pool over-provisioning closed** — `POST /v1/deployment/activate` now allocates a `units`
  slice per deployment and enforces `Σ active deployments ≤ purchased pool` (409 on exceed/
  exhaust); N purchased units stay N total across deployments, never N×K. The endpoint mints the
  deployment's slice, not the whole org pool.
- **never-hard-cut protected** — the Community floor is exempt from node binding + peer census
  ([node_broker.py](../apps/runtime/node_broker.py) `_is_community_floor`), so a lapsed,
  unbound Community license can never be hard-blocked by enforcement.
- **cgroup v1 leaf walk** — `_cgroup_v1_cpu_quota_vcpu` now walks `/proc/self/cgroup` to the
  process's actual cpu sub-cgroup (systemd slice / container limit), not just the mount root.
- **finite paid expiry** — `issue_offline_license.py --paid-selfhost` requires a finite
  `--expires-at` (no perpetual "pay once and leave").
- **deployment revocability** — deployment tokens carry an `activation_id` (CRL-revocable) +
  are jti-denylist-revocable.
- **activation race** — concurrent first-time activations reconcile on the unique constraint
  (no 500).
- **offline-license device binding (round 3, HIGH)** — `assert_node_binding` gated the thumbprint
  check on `node_limit > 0`, so it was dead code for deployment licenses (which have
  `active_node_limit=0`) — an offline response could be copied across nodes. Binding is now
  enforced whenever the license carries a `device_pubkey_thumbprint`, independent of `node_limit`
  (unbound tokens still fall through to the L2 census).
- **relay bad-product lease (round 3, MEDIUM)** — a lease request for a product not in the pool
  acquired (clobbering the node's existing valid lease) then released it; the product check now
  runs BEFORE the ledger is touched.
- **strip scans bytecode (round 3, LOW)** — `strip_dev_stub.py` now scans ALL files as bytes
  (not just `*.py`) and deletes the stub's `__pycache__` artifacts, so a compiled `.pyc`/`.so`
  embedding the secret can't produce a false "hardened" result; the `production-wheel` rsync also
  excludes `__pycache__`.
- **pool over-admission race (round 2)** — `admit_deployment_node` (L3) and `activate_deployment`
  both did a non-atomic SUM-then-insert, so concurrent requests for different nodes/deployments
  could each read a stale total and jointly exceed the pool. Both now take a transaction-scoped
  `pg_advisory_xact_lock` (`acquire_pool_advisory_lock`, mirroring the device path's
  `acquire_org_device_lock`) before the check, serializing admissions against the same ceiling;
  the node-lease insert also reconciles on IntegrityError.

## Known limitations (acknowledged; enforcement is dark-by-default)

- **Post-boot capacity growth** — the pinned-node Compute-Unit ceiling is measured at daemon
  startup; a hostile local operator who relaxes the cgroup / affinity AFTER boot can grow past
  the licensed units until restart. Continuous re-measurement + execution gating against a fully
  privileged local admin is inherently limited (the plan acknowledges this); the durable defense
  is the vendor-rooted Relay lease (short-TTL re-measured leases) — see E remainder.
- **Once-per-deployment Community election** — a lapsed multi-node deployment currently recovers
  the Community floor per node (each carries `deployment_id` for a future election); the
  coordination to elect a single recovery runtime per `deployment_id` is a follow-on. It never
  hard-cuts (above), it just doesn't yet collapse to exactly one free node.
- **Edition cross-check** — the strict verifier enforces exact `product` match (no cross-product
  replay); exact `edition` match is available but not wired at the runtime (product is the
  load-bearing boundary).

## Packaging strip, HA, and the air-gap ceremony (shipped)

- **Production-wheel dev-secret strip** — the HS256 dev secret lives ONLY in
  [_dev_license_stub.py](../apps/runtime/_dev_license_stub.py); `make production-wheel` stages the
  source, runs [scripts/strip_dev_stub.py](../scripts/strip_dev_stub.py) to delete it and verify
  no copy survives, then builds the wheel. With the stub absent, `license._DEV_SECRET` is `None`
  and the HS256 dev-stub path is unreachable — the artifact can't contain the forgeable secret
  (defense-in-depth atop the RS256-only runtime guard). The control-plane HS256 path is a separate
  secret and is unaffected.
- **Air-gap request→portal→response ceremony** — node runs
  [scripts/generate_offline_request.py](../scripts/generate_offline_request.py) (a signed request
  bound to its device-key thumbprint, carrying measured vCPU + host evidence + nonce); the operator
  runs [scripts/issue_offline_response.py](../scripts/issue_offline_response.py) to mint a
  deployment license bound to that thumbprint at the approved unit ceiling; the node loads it via
  `ALGENTA_LICENSE_JWT`. Request build/parse is runtime-safe in
  [offline_ceremony.py](../apps/runtime/offline_ceremony.py).
- **Relay HA** — [relay_lease_store.py](../apps/runtime/relay_lease_store.py) `SqliteLeaseLedger`:
  a shared, persistent ledger with cross-process atomic admission (`BEGIN IMMEDIATE`), so multiple
  relay replicas over one shared DB file can't double-allocate the pool. Wire it via
  `create_relay_app(ledger_factory=...)`. For large/multi-region fleets, back it with Postgres
  (SELECT FOR UPDATE / advisory lock) or a quorum/leader-elected relay set — the ledger API is the
  seam.

## Not yet shipped (owner-coupled — tracked)

- **A remainder:** native-daemon-only verification hardening + deployment-key PoP at renewal.
- **D:** DROPPED — no per-customer usage measurement/report (runs on their infra; billing is
  purchased Compute Units, locally capped, no phone-home).
- **E remainder:** multi-region/Postgres-backed Relay HA + quorum (single shared-file HA + 72h
  node grace shipped today).
- **F:** AWS Marketplace SaaS-contract listing (Azure gated on Partner Center verification).

Deployment topology: Supabase (identity) · Fly.io (control plane + signing keys) · Cloudflare
(mint edge) · accounts repo (billing/portal UX).

## Related

* [LICENSE_ENFORCEMENT_RUNBOOK.md](LICENSE_ENFORCEMENT_RUNBOOK.md) — operating the enforcement seams this page defines.
* [BUSINESS_MODEL.md](BUSINESS_MODEL.md) — the commercial model these Compute Units price.
* [pricing-algenta.md](pricing-algenta.md) — the published pricing surface.
