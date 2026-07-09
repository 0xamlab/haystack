# Algenta pricing — two axes: hosted per-seat, self-hosted per-node

Engineering reference for how Algenta's paid tiers are priced and enforced. External/marketing copy lives
elsewhere (GitBook is external-only); this documents the model + the anti-abuse machinery.

## The decision

One plan/entitlement schema, **two priced dimensions selected by deployment**. Derived from a broad-market
survey (repository-intelligence + code-review + agentic tools) grounded against Algenta's own tier limits and
the already-published Codna/Telys prices.

| Tier | Deployment | Price | Billing unit | Notes |
|---|---|---|---|---|
| `algenta_free` | hosted **or** self-host | **$0** | — | **free forever, exactly 1 node**, non-commercial, full features |
| `algenta_pro` | hosted | **$29/mo** | flat (1 seat) | repo-intel band (CodeRabbit/Greptile/Qodo $24–30) |
| `algenta_team` | hosted | **$39/seat/mo** | **per seat** (Stripe adjustable quantity) | market Team band $30–40/seat |
| `algenta_selfhost` | self-hosted | **$199/active node/mo** | **per node** | infra/runtime comps (SonarQube/Redis/TeamCity) |
| enterprise | either | custom (~$60–100+/seat or site license from ~$40k/yr) | negotiated | via per-org `entitlement_overrides` |

Annual list motion = ~2 months free (16.7%, market standard).

## Why hosted = per-seat but self-hosted = per-node

Per-seat is only enforceable when **we** run the infra and count seats (the hosted axis). Once a customer
holds the engine binary (self-hosted), seats are unenforceable — they can point unlimited users at one
instance. The only enforceable unit is the **running engine = the active node**. So self-hosted is billed
**per node**, which also matches how self-managed infra tools price (SonarQube per instance, Redis per
node/shard, TeamCity per agent, HashiCorp historically per node). A self-hosted node serves many users, so
`$199/node ≈ 5×` a `$39` hosted seat.

This is the same model Codna ships — Algenta rides the **same shared platform machinery**
(`device_service`, `entitlement_service`, `worker_broker`, offline RS256 verification via
`product_registry`); no separate anti-cheat wiring, only the tier rows + minting correctly.

## Free forever on one node

`algenta_free` always includes **exactly one self-hosted node**, non-commercial: `price=0`, `devices=1`,
`active_node_limit=1`, `commercial_use=False`. This is the PLG top-of-funnel and is near-zero-COGS to serve
(local execution + BYOK LLM). Asserted in `tests/test_algenta_selfhost_pricing.py`.

## The anti-fleet-abuse defense (why one $199 license can't run across a fleet)

The enforcement is **not** the price — it's the **active-node-cap + minting with finite, non-OEM caps**.

1. **Active-node-cap** (`device_service.node_admission_block_count`, DB-counted, authoritative engine-side):
   a true concurrent ceiling — a new/returning node gets `402 device_limit_reached` once live nodes fill the
   licensed count. **Default-off**; a connected paid self-host deployment MUST run with
   `ALGENTA_ENFORCE_ACTIVE_NODE_CAP=1` (else it counts every device = effectively uncapped). For strict
   offline fail-closed also set `ALGENTA_REQUIRE_LOCAL_LICENSE=1`.

2. **Mint with finite caps, never OEM.** Paid self-host licenses are minted with
   `scripts/issue_offline_license.py --paid-selfhost`, which runs `scripts/license_mint_guard` and **refuses
   to sign** unless: `deployment_class != oem` and not `redistribution_allowed`, `commercial_use=True`, at
   least one finite cap (`active_node_limit` and/or `concurrent_worker_limit` > 0), bounded
   `offline_grace_days` (≤ 90), and — for `airgapped` — device-bound (`--device-pubkey-thumbprint`) with a
   finite worker cap (offline, the worker cap is the only unit the runtime self-enforces). **OEM licenses**
   (`issue_oem_license.py`: caps=0, redistribution, ~100y) are the deliberate fleet-portable shape reserved
   for trusted-partner / sub-brand redistribution and are **never** used for a paying customer — the guard
   rejects them.

Golden tests: `tests/test_license_mint_guard.py` (incl. proving OEM claims are rejected as paid self-host).

## Offline `active_node_limit` enforcement (runtime node_broker)

`active_node_limit` is now **runtime-enforced offline**, no phone-home, via `apps/runtime/node_broker.py`,
layered strongest-to-weakest and fail-closed:

- **L1 — device binding (air-gap-safe, primary).** At daemon boot (`_validate_daemon_startup_prerequisites`,
  before anything binds) a device-bound license (`device_pubkey_thumbprint` set) must run on the machine
  whose Ed25519 private key reproduces that thumbprint (`device_keypair.public_key_thumbprint`); mismatch →
  `NodeAdmissionError`, refuse to boot. For the `algenta_selfhost` unit (`active_node_limit=1`) this alone is
  an offline node cap of 1 with zero coordination — the token can't run on a second machine.
- **L2 — peer census (shared-Redis clusters, opt-in `ALGENTA_ENFORCE_PEER_NODE_CAP`).** For a shared-token
  cluster (`active_node_limit=N`), nodes count each other in an atomic sorted-set census keyed by
  `license_id` on the customer's OWN coordination Redis (`apps/runtime/coordination.py`), refreshed by a
  heartbeat; the N+1-th node is refused. A single Lua eval (prune-stale → refresh-if-present → admit-if-under-
  cap) makes it a true concurrent ceiling with no last-slot race, and it never evicts a live node.

Dark by default: no-op unless license enforcement is on (`require_local_license` **or**
`enforce_license_validation`) and `active_node_limit > 0`; L2 additionally needs `ALGENTA_ENFORCE_PEER_NODE_CAP`
+ a reachable `ALGENTA_COORDINATION=redis`. Free-tier / single-node / dev untouched.

## Honest residual (what still can't be enforced, and why)

The fundamental limit stands: **mutually-unreachable nodes that share zero state and never phone home cannot
be globally counted** (the monotonic-counter / rollback impossibility). This design degrades gracefully to
the strongest practical posture rather than overcoming it:

- **L2 counts only REACHABLE peers** — two network partitions / isolated LAN islands each admit up to N (a
  partition is a per-segment ceiling, never global). Never marketed as a global cap.
- **L1 strength depends on the key store.** With the default software store (OS keychain / machine-id-
  encrypted file) it is tamper-EVIDENT: a root operator who clones a VM *preserving `/etc/machine-id`* and
  copies the key store gets a working identity. **Hardware backing (shipped) makes it tamper-PROOF:** set
  `ALGENTA_DEVICE_KEY_STORE=secure_enclave` (Apple Secure Enclave, macOS) or `tpm` (TPM 2.0, Linux/Windows —
  `ALGENTA_TPM_ENABLE=1` + `tpm2-pytss`). The per-node private key is generated in and never leaves the
  security element (a non-exportable secp256r1 key, `secp256r1:` thumbprint + ECDSA), so the bound token
  physically cannot activate on a second machine — **near-prevention for `active_node_limit=1`.** Hardware is
  opt-in (so a device's thumbprint stays stable); absent/failed hardware degrades to the software key, whose
  differing thumbprint fails a hardware-bound license closed rather than silently running. The Secure Enclave
  helper ships **prebuilt + code-signed + RS256-manifest-signed** in the sidecar wheel
  (`algenta_runtime_native/se/`), resolved + verified (signature + SHA-256, fail-closed) before execution —
  **no runtime compiler** (the clean-machine contract); `swiftc` JIT is a dev-only fallback. Built by
  `scripts/build_se_helper.py` in `build-runtime.yml`. See `apps/runtime/hardware_key_store.py` +
  `apps/runtime/native_manifest.py`.
- **Air-gap disables revocation** — a leaked bound token is aged out by short TTL + go-dark grace, not revoked.
- A determined operator can still mint-guard-violate (unbound tokens), disable the flags, or spin a fresh
  VM per node — none of which any offline scheme prevents; all are deliberate, auditable circumvention that
  voids the license (matching how HashiCorp/Elastic/Cloudera monetize air-gapped deployments).

## Other follow-ups

- **Default-off cap is a provisioning footgun.** A paid self-host deployment that forgets
  `ALGENTA_ENFORCE_ACTIVE_NODE_CAP=1` (connected) / `ALGENTA_ENFORCE_PEER_NODE_CAP=1` (cluster) is uncapped.
  The mint output prints a reminder; deployment automation must set it.
- **Multi-node self-serve** provisions one node via Stripe checkout; larger node counts scale
  `active_node_limit` via per-org `entitlement_overrides` (enterprise) + an offline per-node mint. Tightly
  coupling Stripe subscription quantity → `active_node_limit` needs persisted overrides (future).
- Autoscale burst/grace + a documented node definition (pod vs VM) so an over-cap scale-up degrades
  gracefully rather than refusing to boot.

## Sibling consistency

Algenta Pro `$29` < Codna proplus `$60`; Algenta Team `$39/seat` below Codna everywhere — the gap is
explained by Codna bundling managed-LLM spend (`llm_spend_cap` $50–$2,000/mo) while Algenta is BYOK
(`llm_spend_cap=0`, customer pays providers directly). Telys is the current byte-for-byte entitlement twin at
`$0/$25/$99`; Algenta diverges upward because repository intelligence commands the $30–40 repo-review band a
raw memory runtime does not — realign Telys or keep the divergence documented, but don't ship two
identical-entitlement SKUs at different prices unexplained.
