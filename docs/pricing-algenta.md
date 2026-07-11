---
icon: tags
description: Internal pricing and enforcement reference for Algenta device-based licensing.
---

# Algenta pricing — self-hosted, licensed per device

Engineering reference for how Algenta's paid tiers are priced and enforced. External/marketing copy lives
elsewhere (GitBook is external-only); this documents the model + the anti-abuse machinery. The live card is
[algenta.ai/pricing](https://algenta.ai/pricing); the Stripe products (`source=algenta`, `usage=licensed`)
are the source of truth for prices.

## The decision

The engine runs on the customer's hardware at **every** tier (Community included), so the only enforceable
billing unit is the **running engine = a device**. Everything is therefore **self-hosted, licensed per
device**. One plan/entitlement schema; the paid tiers differ by per-device throughput (workers/device) and
included team seats.

| Tier | Internal plan | Price | Billing unit | Workers/device | Seats |
|---|---|---|---|---|---|
| Community | `algenta_free` | **$0** | — (1 device) | 1 | 1 |
| Pro | `algenta_pro` | **$99/device/mo** ($948/device/yr) | **per device** (Stripe qty = devices) | 5 | 1 |
| Team | `algenta_team` | **$499/device/mo** ($4788/device/yr) | **per device** (Stripe qty = devices) | 20 | 15 |
| Enterprise | `enterprise` | from **$50k/yr** | fleet licensing (negotiated) | unlimited | negotiated |

Community is non-commercial (1 device, 1 worker). Enterprise adds air-gapped mode + fleet licensing (your
device count under one agreement) + SLA. Annual ≈ 2 months free (Pro $948 ≈ $79/mo; Team $4788 ≈ $399/mo).

> **Removed (2026-07):** the old two-axis model (`algenta_pro` $29 flat, `algenta_team` $39/seat, and a
> separate `algenta_selfhost` $199/node) no longer exists. Pro/Team ARE the per-device self-host tiers.

## Why per device

Once a customer holds the engine binary, seats are unenforceable — they can point unlimited users at one
instance. The only unit the runtime can enforce is the **running engine = the device** (its bound key). So
every tier is billed per device; workers-per-device (1/5/20) and included seats (1/1/15) are the differentiators.
This matches how self-managed infra tools price (SonarQube per instance, TeamCity per agent, HashiCorp
historically per node). The Stripe prices are `usage=licensed`: the subscription **quantity = the number of
licensed devices**.

Algenta rides the **same shared platform machinery** Codna/Telys ship (`device_service`,
`entitlement_service`, `worker_broker`, offline RS256 verification via `product_registry`); no separate
anti-cheat wiring, only the tier rows + minting correctly.

## Free forever on one device

`algenta_free` (Community) always includes **exactly one self-hosted device**, non-commercial: `price=0`,
`devices=1`, `active_node_limit=1`, `concurrent_worker_limit=1`, `commercial_use=False`. This is the PLG
top-of-funnel and near-zero-COGS to serve (local execution + BYOK LLM). It is also the **lapse target**: a
cancelled/lapsed paid license downgrades to Community rather than hard-blocking. Asserted in
`tests/test_algenta_pricing.py`.

## The anti-fleet-abuse defense (why one per-device license can't run across a fleet)

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
  `NodeAdmissionError`, refuse to boot. For a single-device unit (`active_node_limit=1`, e.g. Community) this
  alone is an offline device cap of 1 with zero coordination — the token can't run on a second machine.
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
  helper ships **prebuilt + RS256-manifest-signed** in the sidecar wheel (`algenta_runtime_native/se/`),
  resolved + verified (manifest signature + SHA-256, fail-closed) before execution — **no runtime compiler**
  (the clean-machine contract); `swiftc` JIT is a dev-only fallback. The RS256 manifest is the trust anchor;
  the Mach-O is **ad-hoc code-signed** by default (all an internal, wheel-bundled, Python-invoked binary needs
  to run on Apple Silicon), with an **optional** Developer ID (`ALGENTA_SE_CODESIGN_IDENTITY`, for standalone
  distribution / notarization) that falls back to ad-hoc if its cert is absent. Built by
  `scripts/build_se_helper.py` in `build-runtime.yml`. See `apps/runtime/hardware_key_store.py` +
  `apps/runtime/native_manifest.py`.
- **Air-gap disables revocation** — a leaked bound token is aged out by short TTL + go-dark grace, not revoked.
- A determined operator can still mint-guard-violate (unbound tokens), disable the flags, or spin a fresh
  VM per node — none of which any offline scheme prevents; all are deliberate, auditable circumvention that
  voids the license (matching how HashiCorp/Elastic/Cloudera monetize air-gapped deployments).
- **TPM path validation.** `TpmKeyStore` (P-256 via `tpm2-pytss`) is validated against **swtpm** (a real
  TPM 2.0 software stack — libtpms) in CI (`.github/workflows/tpm.yml`): create → sign → ECDSA-SHA256
  verify → `secp256r1:` thumbprint → cross-process reload. swtpm proves the ESAPI code is **correct**; it
  does **not** prove the anti-clone SECURITY property — swtpm keys live in a state directory, not tamper-
  resistant silicon. The non-exportable guarantee only holds on a **discrete/firmware TPM** (`FIXEDTPM`),
  which must be confirmed once on real hardware (an fTPM Linux box / self-hosted runner). macOS has no
  libtss2, so the TPM path is Linux/Windows only; on macOS use Secure Enclave.

## Other follow-ups

- **Default-off cap is a provisioning footgun.** A paid self-host deployment that forgets
  `ALGENTA_ENFORCE_ACTIVE_NODE_CAP=1` (connected) / `ALGENTA_ENFORCE_PEER_NODE_CAP=1` (cluster) is uncapped.
  The mint output prints a reminder; deployment automation must set it.
- **Per-device quantity → device cap.** Checkout must set Stripe quantity = number of licensed devices, and
  the webhook must sync that quantity into the org's device cap (`active_node_limit` / device allowance) so a
  paying customer can register exactly the devices they bought. This is the Part-2 billing inversion (today
  the seat-quantity plumbing predates the per-device card); enterprise fleet counts still scale via per-org
  `entitlement_overrides` + offline per-device mints.
- Autoscale burst/grace + a documented node definition (pod vs VM) so an over-cap scale-up degrades
  gracefully rather than refusing to boot.

## Sibling consistency

Algenta is priced per **device** ($99/$499) where Codna/Telys are priced per **seat** — different billing
units for different products, so a direct seat-to-seat comparison doesn't apply. Algenta is BYOK
(`llm_spend_cap=0`, customer pays providers directly) whereas Codna bundles managed-LLM spend
(`llm_spend_cap` $50–$2,000/mo); a per-device Algenta license serves many users on one machine, so the
per-device price sits well above any single hosted seat by design.

## Next step

Reconcile any pricing change with the entitlement schema, Stripe products, and [go-live gates](go-live-algenta.md) before publication.
