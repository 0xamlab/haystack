# TLS for api.telys.ai — scoped per-hostname, NOT zone-wide.
#
# ── WHY A CONFIGURATION RULE INSTEAD OF cloudflare_zone_settings_override ────────────────────────────
# The problem being solved is that the telys.ai zone runs `ssl = "full"`: Cloudflare encrypts to the
# origin but does NOT validate the origin certificate, so the Cloudflare↔Fly hop is unauthenticated. On
# the zone that carries device registration and license minting — a chain whose entire purpose is
# proving device identity — that is the weakest link.
#
# The obvious fix (flip the zone's `ssl` setting to "strict") is a ZONE-WIDE change: it applies to every
# proxied record, so any proxied hostname whose origin lacks a valid cert breaks immediately. A
# Configuration Rule sets the SSL mode per-request instead, so Full (Strict) applies to exactly one
# hostname and the blast radius is exactly that hostname. Verified available in the provider schema:
# `cloudflare_ruleset` phase `http_config_settings`, action `set_config`, attribute `ssl`.
#
# This is also CLIENT-INVISIBLE: `ssl` governs the Cloudflare→origin leg only. Browsers and the Telys
# CLI negotiate against Cloudflare's edge certificate, which is untouched by this rule.
#
# Origin readiness verified before writing this (2026-07-28) — Full (Strict) requires a valid,
# non-expired origin cert whose name matches:
#   $ echo | openssl s_client -connect algenta-control-plane.fly.dev:443 -servername api.telys.ai \
#       | openssl x509 -noout -subject -issuer -dates
#     subject= /CN=api.telys.ai
#     issuer = /C=US/O=Let's Encrypt/CN=YE2
#     notBefore=Jul  1 22:26:15 2026 GMT   notAfter=Sep 29 22:26:14 2026 GMT
# Fly renews this automatically. If it ever lapses, Full (Strict) fails CLOSED (526) for this hostname
# — which is the correct failure mode for a licensing endpoint, but is why the smoke check in README.md
# includes a TLS assertion.
resource "cloudflare_ruleset" "telys_config" {
  zone_id = var.telys_zone_id
  name    = "telys-control-plane-config"
  kind    = "zone"
  phase   = "http_config_settings"

  rules {
    description = "Full (Strict) origin validation for the control-plane hostname only"
    enabled     = true
    expression  = "(http.host eq \"api.telys.ai\")"
    action      = "set_config"
    action_parameters {
      ssl = "strict"
    }
  }
}

# ── min_tls_version: DELIBERATELY NOT CHANGED HERE ──────────────────────────────────────────────────
# Live state: telys.ai is on min_tls_version = 1.0 (algenta.ai is on 1.2), so TLS 1.0 and 1.1 are still
# accepted. Raising it is worth doing — both are long deprecated and fail a PCI baseline — but it is NOT
# done in this module.
#
# CORRECTION, recorded because an earlier revision of this file asserted the opposite: it is NOT true
# that min_tls_version cannot be scoped per-hostname. It is absent from the `set_config` action
# parameters used above — that much is verified against `tofu providers schema -json` — but the provider
# ALSO ships a dedicated resource for exactly this:
#
#   resource "cloudflare_hostname_tls_setting" { zone_id, hostname, setting, value }
#
# with `setting = "min_tls_version"`, `value = "1.2"`. The earlier claim over-generalised from "not in
# set_config" to "impossible", which is wrong. Do not repeat it.
#
# The reason to defer is therefore only the second one, which stands on its own:
#
#   It is CLIENT-VISIBLE and fails CLOSED. Any client pinned to TLS 1.0/1.1 stops connecting — no
#   warning, no negotiation, just a handshake failure. For the Telys CLI and SDK that is a non-issue
#   (Python's ssl module and Node both default to 1.2+ on every supported version), but this zone also
#   serves the marketing site, whose visitor mix is not something to guess at.
#
# So when this is picked up, prefer cloudflare_hostname_tls_setting scoped to api.telys.ai over a
# zone-wide flip — it confines the change to the API hostname, where the client population IS known
# (the CLI and SDK), and leaves the marketing site untouched. Two caveats to check first: per-hostname
# TLS settings are generally an Advanced Certificate Manager feature, so confirm it is available on
# this zone's plan (telys.ai is Pro) before relying on it, and confirm the provider version in use
# actually manages it against a live zone rather than only exposing the schema.
#
# Note also that the zone-wide blast radius cited earlier was overstated: docs.telys.ai is DNS-only
# (grey), and telys.ai/www are grey too, so a zone setting would not affect them at the Cloudflare
# edge at all. The real exposure of a zone-wide flip is narrower than first written — which makes the
# per-hostname resource a convenience rather than a necessity, but still the cleaner instrument.
#
# DO NOT raise it on the assumption that "nothing uses TLS 1.0". Get the data first — Cloudflare records
# exactly this. The query below is ready to run; it currently fails because the API token in use lacks
# `com.cloudflare.api.account.zone.analytics.read` ("Actor ... does not have permission ... for zone
# ce52bc06a...", confirmed 2026-07-28). Add Analytics:Read to the token, then:
#
#   curl https://api.cloudflare.com/client/v4/graphql \
#     -H "Authorization: Bearer $CF_TOKEN" -H 'Content-Type: application/json' --data '{"query":
#     "query { viewer { zones(filter: {zoneTag: \"<telys_zone_id>\"}) {
#        httpRequests1dGroups(limit: 31, filter: {date_gt: \"<30d-ago>\"}, orderBy: [date_DESC]) {
#          dimensions { date } sum { clientSSLMap { clientSSLProtocol requests } } } } } }"}'
#
# Decision rule: if TLS 1.0 + 1.1 are 0% (or a rounding-error share attributable to scanners), raise the
# zone to 1.2 in its own small PR that touches nothing else, so it can be reverted independently. If
# there is real legacy traffic, identify it before breaking it.
#
# Recorded for restoration, since this module intentionally leaves zone settings unmanaged — live
# telys.ai values as audited 2026-07-28:
#   ssl=full  min_tls_version=1.0  always_use_https=on  tls_1_3=on  brotli=on
#   automatic_https_rewrites=off
# (algenta.ai, for comparison: ssl=strict, min_tls_version=1.2, automatic_https_rewrites=on.)
