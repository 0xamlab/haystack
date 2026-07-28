# Cloudflare edge for Telys — the `telys.ai` zone (owner runbook)

Everything here is **config**; applying it changes real production edge behaviour and is **owner-only**.

## Why this module exists

`api.telys.ai` fronts the **same Fly app** as the Algenta control plane (`algenta-control-plane`), so it
serves the same activation and licensing surfaces: `/v1/device/register`, `/v1/license/challenge`,
`/v1/license/renew`, `/v1/auth*`, `/v1/telys/onboard`.

But every rule in [`../algenta-control-plane/waf.tf`](../algenta-control-plane/waf.tf) is gated on
`http.host eq "api.algenta.ai"`, and the `telys.ai` zone was **not in Terraform at all** — its records
were created in the Cloudflare dashboard. A live audit on 2026-07-28 found:

| Finding | Live state before this module | This module |
|---|---|---|
| `http_ratelimit` ruleset on `telys.ai` | **none** — no per-IP limit on device register / license mint | **fixed** — mirrors algenta 1:1 |
| `http_request_cache_settings` ruleset | none — activation surface on Cloudflare cache defaults | **fixed** — explicit bypass/cache policy |
| `ssl` | `full` — CF↔Fly hop **not** origin-validated (algenta: `strict`) | **fixed** — `strict`, scoped to `api.telys.ai` |
| `min_tls_version` | `1.0` — TLS 1.0/1.1 still permitted (algenta: `1.2`) | **deferred, on purpose** — see below |
| DNS records | dashboard-only, unreviewable, no drift detection | **fixed** — adopted via `import` |

So the hostname the Telys CLI actually calls was the *least* protected route into the licensing origin.

## What this module does

- **Adopts** the existing `api` (A + AAAA), `packages` (AAAA), `docs` (CNAME) records unchanged, via
  `import` blocks in [`imports.tf`](imports.tf) — `plan` says *will be imported*, never *will be created*.
- **Creates** `telys-control-plane-ratelimit` — mirrors the algenta limits 1:1 (30/min on auth + device
  activation, 600/min baseline). **This is the actual fix.**
- **Creates** `telys-control-plane-cache` — bypass dynamic/authenticated, cache only JWKS + signed CRL.
- **Adopts** the existing managed-ruleset deployment so it stops being invisible drift.
- **Creates** `telys-control-plane-config` — Full (Strict) origin validation scoped to `api.telys.ai`
  **only**, via a Configuration Rule instead of the zone-wide `ssl` setting. See [`tls.tf`](tls.tf).

### What actually changes for clients

An earlier revision of this README claimed applying the module "cannot change what any client sees."
**That was false**, and it is corrected here because it is the sentence an operator would have trusted.
No *zone-level setting* is managed — that part is true — but the module's whole purpose is to add
enforcement, and enforcement is by definition visible:

| Change | Client-visible effect |
|---|---|
| `telys_ratelimit` | Requests over 30/min (auth + activation) or 600/min (`/v1/*`) are **blocked**. The zone previously had **no** rate limit, so this is a new rejection path, not a tightened one. |
| `telys_cache` | New `cf-cache-status` / `Cache-Control` behaviour on JWKS and the CRL. The CRL becomes edge-cached, so revocation propagates in ~2 min instead of immediately (see [`cache-rules.tf`](cache-rules.tf)). |
| `telys_config` (Full Strict) | Introduces a **`526`** failure mode for `api.telys.ai` if the Fly origin certificate ever lapses. Previously `ssl=full` would have served the request. |

None of that is a reason not to apply it — an unprotected licensing endpoint is worse than a rejection
path. But "zero client-visible change" was the wrong summary, and a blocked `telys login` behind a busy
NAT is a real support case, so plan for it rather than being surprised.

What *is* invisible: the `ssl` mode itself. `ssl` governs only the Cloudflare→origin leg, so the edge
certificate clients negotiate against is untouched.

### Why SSL is scoped, not zone-wide

An earlier draft flipped the zone to `ssl=strict` + `min_tls_version=1.2` via
`cloudflare_zone_settings_override`. Validating it surfaced that the provider **cannot import** that
resource, so it could only ever plan as *create* — capturing no prior state for rollback. A
Configuration Rule avoids that and confines the change to one hostname.

`min_tls_version` is **left at its live value of 1.0**. Note a second correction: an earlier revision
claimed it "cannot be scoped per-hostname." It can — via `cloudflare_hostname_tls_setting`
(`setting = "min_tls_version"`), which exists in provider v4. The earlier claim over-generalised from
"absent from `set_config`" to "impossible."

The real reason to defer stands on its own: raising it fails **closed** for any client pinned to TLS
1.0/1.1, and this zone also serves the marketing site, whose visitor mix is unknown. [`tls.tf`](tls.tf)
carries the ready-to-run Cloudflare GraphQL query for the actual TLS-version distribution, the token
permission currently missing to run it (`Analytics:Read`), and the decision rule. Raise it in its own
small PR — scoped to `api.telys.ai` where the client population *is* known — backed by that data.

Deliberately **not** managed: `telys.ai` / `www` (Vercel), `_dmarc`, the Google site-verification TXT.
Those belong to the website + mail setup. Terraform only manages what it declares, so they are untouched.

### Removed: `_domainconnect.telys.ai` (2026-07-28)

The zone carried a **proxied** `CNAME _domainconnect.telys.ai → _domainconnect.gd.domaincontrol.com`.
It was GoDaddy Domain Connect residue from before DNS moved to Cloudflare, and it was dead:

- `_domainconnect.gd.domaincontrol.com` answers `NOERROR` with an **empty answer** (NODATA — the name
  exists, it has no address). Confirmed against 1.1.1.1, 8.8.8.8 and 9.9.9.9.
- `gd.domaincontrol.com` publishes no NS, and `domaincontrol.com` resolves to **127.0.0.1**.
- Because the record was orange-clouded, Cloudflare tried to proxy to that non-resolving origin and
  served **HTTP 530** (origin DNS failure) to anyone who asked.

So it was an actively-erroring hostname advertising a dead Domain Connect endpoint on a zone whose DNS
Cloudflare now serves. Deleted rather than adopted — there is nothing to preserve. Verified gone at the
authoritative nameserver, with `api.telys.ai` re-checked healthy (`200`, `role=control_plane`) after the
zone edit. Backup of the exact record: `/tmp/domainconnect-telys-backup.json` (also inline below, since
restoring it would only restore a 530):

```json
{ "name": "_domainconnect.telys.ai", "type": "CNAME",
  "content": "_domainconnect.gd.domaincontrol.com", "proxied": true, "ttl": 1,
  "created_on": "2026-06-27T03:03:54.744654Z" }
```

It is **not** declared in this module: re-adding it to Terraform would only codify the dead record, and
Terraform does not delete what it never managed.

⚠️ **The same dead record exists on five other zones** — `algenta.ai`, `codna.ai`, `cohenta.ai`,
`escrypto.ai`, `thyn.ai` — all proxied, all pointing at the same non-resolving target. Only `telys.ai`
was cleaned up here, because that is this module's scope. The others are a one-line delete each and
should be swept separately:

```
curl -X DELETE -H "Authorization: Bearer $CF_TOKEN" \
  "https://api.cloudflare.com/client/v4/zones/<zone_id>/dns_records/<record_id>"
```

## Plan first — always

```
cd infra/cloudflare/telys
export TF_VAR_cloudflare_api_token=…
export TF_VAR_cloudflare_account_id=…
export TF_VAR_telys_zone_id=…               # telys.ai zone id
tofu init && tofu plan
```

**Token scope.** This module writes rulesets in **three different phases**, and Cloudflare gates them
under separate permission groups. An earlier revision of this README listed only `Zone:Read`, `DNS:Edit`
and `Zone WAF:Edit` — that is **not sufficient**, and the failure mode is nasty: `apply` creates the
rate-limit ruleset, then `403`s on the cache or configuration rule, leaving the edge **half-configured**.
The token needs edit rights covering all of:

| Resource | Phase | Permission area |
|---|---|---|
| `telys_ratelimit` | `http_ratelimit` | WAF / Rate Limiting |
| `telys_waf_managed` | `http_request_firewall_managed` | WAF |
| `telys_cache` | `http_request_cache_settings` | **Cache Rules** |
| `telys_config` | `http_config_settings` | **Configuration Rules** |
| DNS records | — | DNS |
| — | — | Zone:Read |

Exact permission-group labels vary in the dashboard UI, so rather than trusting a list: **`tofu plan` is
read-only and safe — but a clean plan does not prove the token can write.** If `apply` does 403 partway,
it is recoverable: fix the token and re-run `apply`. Terraform is idempotent and will finish the
remaining resources. Do not hand-fix the half-state in the dashboard.

(Separately: reading the TLS-version analytics referenced in [`tls.tf`](tls.tf) needs `Analytics:Read`,
which the current token does **not** have.)

The verified first plan (run against the live zone on 2026-07-28) is exactly:

```
Plan: 5 to import, 3 to add, 4 to change, 0 to destroy.
```

- **5 to import** — the 4 existing DNS records + the existing managed-ruleset deployment
- **3 to add** — `telys_ratelimit`, `telys_cache`, `telys_config`. All three are new rulesets; none
  replaces or modifies anything that exists
- **4 to change** — metadata-only on the imported records: `allow_overwrite` (a provider-side flag, not
  a Cloudflare attribute), the `comment` strings, and a re-write of `content` with the **same** value
  (a provider quirk: import populates the deprecated `value` field, so `content` reads as newly set).
  Verified: no `x -> y` transition, no removals, and `type` / `proxied` / `ttl` / `name` all unchanged.
  **Nothing is repointed.**
- **0 to destroy**

⚠️ If your plan differs — any destroy, any DNS record under *to add*, or any real `content` transition —
**stop**. It means live state moved since the ids in `imports.tf` were captured. Re-read the ids and
re-review; do not force-apply.

Only then:

```
tofu apply
```

## Smoke after apply

```
curl -A "telys-cli" https://api.telys.ai/v1/health                 # 200
curl -A "telys-cli" https://api.telys.ai/v1/control-plane/meta     # {"role":"control_plane",…}
curl -A "telys-cli" https://api.telys.ai/.well-known/jwks.json     # signer public key (now edge-cached)
telys login                                                        # the real end-to-end check
```

**Cache assertion — must target JWKS with a GET.** An earlier revision of this README checked
`curl -sI …/v1/health | grep cf-cache-status`, which can never validate the cache ruleset: `-I` sends
`HEAD`, and the bypass rule matches `http.request.method ne "GET"`, so that request is *always* `BYPASS`
regardless of whether the ruleset exists. Check a path the cache rule actually covers:

```
# expect HIT (or MISS on the very first request, then HIT)
curl -s -o /dev/null -D- -A "telys-cli" https://api.telys.ai/.well-known/jwks.json | grep -i cf-cache-status
curl -s -o /dev/null -D- -A "telys-cli" https://api.telys.ai/.well-known/jwks.json | grep -i cf-cache-status

# and confirm an authenticated path is still BYPASS
curl -s -o /dev/null -D- -A "telys-cli" -H "Authorization: Bearer x" \
  https://api.telys.ai/v1/health | grep -i cf-cache-status
```

**Full (Strict) assertion.** The config rule makes this hostname fail *closed* (`526`) if the Fly origin
cert ever lapses, so assert it explicitly rather than trusting a 200 elsewhere:

```
curl -sS -o /dev/null -w "%{http_code}\n" -A "telys-cli" https://api.telys.ai/v1/health   # 200, never 526

# and confirm the origin cert Full (Strict) validates against is still valid:
echo | openssl s_client -connect algenta-control-plane.fly.dev:443 -servername api.telys.ai 2>/dev/null \
  | openssl x509 -noout -subject -dates
```

A `526` here means origin-cert validation failed — check `fly certs show api.telys.ai -a
algenta-control-plane`. Fly auto-renews, so this should not happen, but it is the one new failure mode
this module introduces and it is worth knowing on sight.

Rate-limit sanity.

⚠️ **This test locks your own IP out of device activation for 60 seconds** (`mitigation_timeout = 60`).
Do not run it from an office/CI egress others share, and do not run it while someone is onboarding —
they will see a failed `telys login`, not a rate-limit message. An earlier revision of this README
printed status codes without asserting anything, so it could not fail; this version actually checks.

```
codes=$(for i in $(seq 1 35); do
  curl -s -o /dev/null -w "%{http_code}\n" -A "telys-cli" \
    -X POST https://api.telys.ai/v1/device/register
done)
echo "$codes" | sort | uniq -c
# PASS = at least one 429 or 403 appears (the edge started blocking)
echo "$codes" | grep -qE '^(429|403)$' \
  && echo "PASS: edge rate limit is enforcing" \
  || echo "FAIL: 35 requests in <60s and nothing was blocked — ruleset not active"
```

## Known-good hostname → origin map

| Hostname | Live origin | Serves |
|---|---|---|
| `api.telys.ai` | `66.241.125.156` → Fly `algenta-control-plane` | control plane (51 paths, engine-free) |
| `api.algenta.ai` | `66.241.124.206` → Fly `codna-api` | full API incl. engine (218 paths) |

⚠️ That second row **contradicts** what
[`../algenta-control-plane/dns.tf`](../algenta-control-plane/dns.tf) declares. See the WARNING there —
it is a latent landmine and is **not** fixed by this PR, because choosing the intended origin for
`api.algenta.ai` is a routing decision, not a drift cleanup.

## Two gotchas worth remembering

**Cloudflare Error 1010 `browser_signature_banned`.** The managed ruleset on this zone rejects stdlib
urllib's default `Python-urllib/X.Y` User-Agent. This broke `telys login` entirely. It was fixed
client-side with a real UA (`telys/login.py` `_USER_AGENT`), **not** by weakening the ruleset — keep it
that way.

**The IP pin.** `api.telys.ai` is an A/AAAA record to the Fly app's dedicated IPs, not a CNAME to
`<app>.fly.dev`. If that IP is ever released or reallocated the hostname breaks silently. Migrating to a
CNAME is a separate, deliberate change — do not fold it into an adoption plan. Verify current IPs with
`fly ips list -a algenta-control-plane`.
