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

## Known enforcement gaps / follow-ups

- **Offline node-count is not runtime-enforced.** `active_node_limit` is a signed claim but offline only
  `concurrent_worker_limit` self-enforces. Air-gapped "N nodes" is therefore sold as device-bound,
  one-per-node tokens with a finite worker cap (enforced by the guard) until the runtime enforces
  `active_node_limit` offline.
- **Default-off cap is a provisioning footgun.** A paid self-host deployment that forgets
  `ALGENTA_ENFORCE_ACTIVE_NODE_CAP=1` is uncapped. The mint output prints a reminder; deployment automation
  must set it.
- **Multi-node self-serve** currently provisions one node via Stripe checkout; larger node counts scale
  `active_node_limit` via per-org `entitlement_overrides` (enterprise) + an offline per-node mint. Tightly
  coupling Stripe subscription quantity → `active_node_limit` needs persisted overrides (future).
- Autoscale burst/grace + a documented node definition (pod vs VM) so an over-cap scale-up degrades
  gracefully rather than `402`-ing customer prod.

## Sibling consistency

Algenta Pro `$29` < Codna proplus `$60`; Algenta Team `$39/seat` below Codna everywhere — the gap is
explained by Codna bundling managed-LLM spend (`llm_spend_cap` $50–$2,000/mo) while Algenta is BYOK
(`llm_spend_cap=0`, customer pays providers directly). Telys is the current byte-for-byte entitlement twin at
`$0/$25/$99`; Algenta diverges upward because repository intelligence commands the $30–40 repo-review band a
raw memory runtime does not — realign Telys or keep the divergence documented, but don't ship two
identical-entitlement SKUs at different prices unexplained.
