# WAF + rate limiting for api.telys.ai.
#
# ── THE GAP THIS CLOSES ─────────────────────────────────────────────────────────────────────────────
# api.telys.ai fronts the Fly app `algenta-control-plane`, so it exposes the activation/licensing
# surfaces. A live audit of the telys.ai zone found NO http_ratelimit ruleset whatsoever — only the
# managed rulesets below. Net effect before this file: /v1/device/register, /v1/license/challenge,
# /v1/license/renew and /v1/auth* were reachable through api.telys.ai with NO per-IP edge limit.
#
# ⚠️ DO NOT ASSUME api.algenta.ai PROTECTS THIS ORIGIN. An earlier revision of this comment said the
# two hostnames front the same Fly app. They do not, as verified 2026-07-28:
#
#   api.telys.ai    A 66.241.125.156 -> algenta-control-plane   51 paths,  "Algenta Control Plane"
#   api.algenta.ai  A 66.241.124.206 -> codna-api              218 paths, "Algenta API" (has engine)
#
# So the host-scoped rules in ../algenta-control-plane/waf.tf are rate-limiting codna-api, NOT the
# control plane — even though that module's own dns.tf declares api.algenta.ai should point at the
# control plane (see the DO NOT APPLY warning there). That means THIS file is currently the ONLY edge
# rate limiting in front of algenta-control-plane. Limits are still mirrored 1:1 from the algenta
# module for consistency, but treat that as a convention, not as redundancy: there is no second layer.
#
# Defense-in-depth ONLY, same caveat as the algenta module: the authoritative anti-abuse control is the
# DB-counted device cap in the app, which also works self-hosted and air-gapped where Cloudflare is not
# in the path. Per-IP edge limits are a coarse backstop against scripted hammering.

resource "cloudflare_ruleset" "telys_ratelimit" {
  zone_id = var.telys_zone_id
  name    = "telys-control-plane-ratelimit"
  kind    = "zone"
  phase   = "http_ratelimit"

  # Tight limit on auth + the full device activation flow: registration AND license minting
  # (challenge + renew).
  #
  # ── EXACT COVERAGE, because "it's rate limited" is not true of this whole hostname ──────────────
  # The baseline rule below matches `starts_with(path, "/v1/")` ONLY. The control plane serves 10
  # paths outside /v1/, so the real picture is:
  #
  #   path                        strict 30/min   baseline 600/min   edge total
  #   /auth/*                     yes (via "/auth" prefix)  no       covered
  #   /v1/auth*                   yes                       yes      covered
  #   /v1/device/register         yes                       yes      covered
  #   /v1/license/challenge|renew yes                       yes      covered
  #   /v1/telys/onboard           no                        yes      600/min only
  #   /v1/license/revocations     no                        yes      600/min only
  #   /oauth/device/{code,token,approve,grant}  no          no       NO EDGE LIMIT
  #   /billing/plans              no                        no       NO EDGE LIMIT
  #   /.well-known/jwks.json      no                        no       NO EDGE LIMIT
  #
  # The last three are NOT an oversight, and adding them would be actively harmful:
  #
  # /oauth/device/* — DO NOT add a per-IP limit here. The CLI does not call this hostname directly;
  #   it calls accounts.thyn.ai/oauth/device/{code,token}, which proxies server-side to the control
  #   plane. So all device-flow traffic arrives at api.telys.ai from the accounts app's few egress
  #   IPs, with every user's login funnelled through them. A 30/min per-IP rule would throttle
  #   logins GLOBALLY, and even the 600/min baseline is reachable at modest concurrency. The correct
  #   granularity is the app-side limit, which is already keyed on the authenticated subject rather
  #   than the IP: routers/oauth_device.py `device_approve` uses per_minute=200 keyed on
  #   `subject or client_ip`, and `device_code_req` uses per_minute=30. Edge limiting is the wrong
  #   layer for a proxied surface; that is where it belongs.
  #
  # /.well-known/jwks.json — installed runtimes poll it and many devices share one egress IP, so a
  #   per-IP limit punishes the wrong party. Origin load is instead bounded by the edge CACHE
  #   (cache-rules.tf), which is the right tool for a public, immutable, signed artifact.
  #
  # /billing/plans — public, cacheable, read-only price list. Nothing to brute-force.
  #
  # NOT included, deliberately: /v1/telys/onboard. It mints an org + the first API key, but requires
  # a verified Supabase JWT, so brute force is not the threat model and the baseline is the right
  # ceiling. Folding it in at 30/min risks blocking legitimate onboarding behind a shared egress IP.
  # (It does mint real resources per call with no app-side cap — a genuine gap, but an application
  # concern, not one the edge can express correctly.)
  #
  # NAT caveat: ip.src + cf.colo.id at 30/min is per-IP-per-colo, and a device activation consumes
  # more than one request (register + challenge/renew), so the effective ceiling is roughly 10-15
  # activations/min from one egress IP. A large office or CI NAT doing bulk first-time activations
  # can trip it, and a blocked activation surfaces to the user as a failed `telys login` rather than
  # as a rate-limit message. If it bites, raise this limit here — do NOT reach for the identical rule
  # in the algenta module expecting it to matter, since that one governs codna-api (see above).
  rules {
    description = "Strict per-IP limit on auth + device activation (register + license mint)"
    enabled     = true
    expression  = <<-EOT
      (http.host eq "api.telys.ai") and (
        starts_with(http.request.uri.path, "/v1/auth") or
        starts_with(http.request.uri.path, "/auth") or
        http.request.uri.path eq "/v1/device/register" or
        http.request.uri.path eq "/v1/license/challenge" or
        http.request.uri.path eq "/v1/license/renew"
      )
    EOT
    action      = "block"
    ratelimit {
      characteristics     = ["ip.src", "cf.colo.id"]
      period              = 60
      requests_per_period = 30
      mitigation_timeout  = 60
    }
  }

  # Baseline API limit. No Stripe-webhook carve-out here: billing webhooks are delivered to
  # api.algenta.ai, not to the telys hostname, so there is nothing to exclude.
  rules {
    description = "Per-IP API rate limit"
    enabled     = true
    expression  = <<-EOT
      (http.host eq "api.telys.ai") and
      (starts_with(http.request.uri.path, "/v1/"))
    EOT
    action      = "block"
    ratelimit {
      characteristics     = ["ip.src", "cf.colo.id"]
      period              = 60
      requests_per_period = 600
      mitigation_timeout  = 60
    }
  }
}

# The zone's managed-ruleset deployment. This ALREADY EXISTS in the telys.ai zone (created via the
# dashboard, adopted by the import block in imports.tf) and is declared here so it stops being
# invisible drift. Same Cloudflare Managed Ruleset id as the algenta zone deploys.
#
# HISTORICAL NOTE — this layer is what broke `telys login`: requests from the CLI were rejected at the
# edge with Cloudflare Error 1010 `browser_signature_banned` because stdlib urllib sends
# "Python-urllib/X.Y". The fix shipped client-side (a real, identifiable User-Agent — see
# telys/login.py `_USER_AGENT`), NOT by weakening this ruleset. Recorded here so the next person who
# sees a 1010 on this zone knows where it comes from and does not "fix" it by disabling protection.
resource "cloudflare_ruleset" "telys_waf_managed" {
  zone_id = var.telys_zone_id
  name    = "default"
  kind    = "zone"
  phase   = "http_request_firewall_managed"

  rules {
    description = "Cloudflare Managed Ruleset"
    enabled     = true
    expression  = "true"
    action      = "execute"
    action_parameters {
      id = "efb7b8c949ac4650a09736fc376e9aee" # Cloudflare Managed Ruleset (well-known id)
    }
  }
}
