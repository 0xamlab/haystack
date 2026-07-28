# DNS: api.algenta.ai → Fly algenta-control-plane (proxied). The license SIGNER is its OWN
# Cloudflare Worker on license.algenta.ai (route bound in the Worker's wrangler.toml — it never
# traverses Fly), so there is NO Fly CNAME for license.algenta.ai here.
#
# ╔══════════════════════════════════════════════════════════════════════════════════════════════════╗
# ║ ⚠️  DO NOT `tofu apply` THIS MODULE UNTIL THE api.algenta.ai ROUTING QUESTION IS SETTLED.        ║
# ╚══════════════════════════════════════════════════════════════════════════════════════════════════╝
#
# `cloudflare_record.control_plane_api` below was evidently never applied — or was overwritten in the
# dashboard afterwards. Live state audited 2026-07-28 does NOT match this declaration:
#
#   declared here : CNAME api.algenta.ai → algenta-control-plane.fly.dev  (the engine-free control plane)
#   actually live : A     api.algenta.ai → 66.241.124.206                 (Fly codna-api, the FULL app)
#
# Proof: https://api.algenta.ai/openapi.json serves 218 paths titled "Algenta API" (engine routes
# present), whereas the control plane serves 51 paths titled "Algenta Control Plane". Compare
# https://api.telys.ai/openapi.json, which IS the control plane.
#
# THE LANDMINE: applying this module as written would repoint api.algenta.ai from codna-api to the
# control plane. Because the control plane deliberately mounts NO engine routers (see
# apps/api_server/control_plane.py), every engine caller of api.algenta.ai — /v1/simulate,
# /v1/recommend, /v1/query, /mcp — would start 404ing. That is a silent, total outage for engine
# clients, produced by what looks like a routine drift cleanup.
#
# Resolving it is a ROUTING DECISION, not a drift fix, and it needs an explicit answer to: should
# api.algenta.ai front the full app (make this a matching A record / CNAME to codna-api) or the control
# plane (then engine clients must first be migrated to another hostname)? Until that is answered this
# declaration is knowingly left as-is and flagged, rather than "corrected" in either direction.
#
# Note the same fact from the other side: because api.algenta.ai actually resolves to codna-api, the
# host-scoped rules in waf.tf are rate-limiting codna-api — NOT the control plane. The control plane's
# own edge protection comes from the telys.ai zone module (infra/cloudflare/telys/), since api.telys.ai
# is the only hostname that genuinely fronts it.
#
# ⚠️ Cert ordering (same as codna): Fly must hold a Ready cert for api.algenta.ai BEFORE Cloudflare
# proxies in Full-Strict. Sequence:
#   1) fly certs add api.algenta.ai -a algenta-control-plane
#   2) apply with control_plane_proxied=false (grey) so Fly's ACME challenge reaches the origin
#   3) once `fly certs show` is Ready, set control_plane_proxied=true (orange) + apply tls.tf

resource "cloudflare_record" "control_plane_api" {
  zone_id = var.algenta_zone_id
  name    = "api"
  type    = "CNAME"
  content = var.control_plane_origin_hostname
  proxied = var.control_plane_proxied
  ttl     = 1
  comment = "Algenta control plane API → Fly algenta-control-plane"
}

# docs.algenta.ai → GitBook (Algenta site). Site-specific hosting target provided by GitBook's
# custom-domain settings for this site. DNS-only (grey): GitBook terminates TLS and issues the
# cert once the domain is registered on the Algenta site + published.
resource "cloudflare_record" "docs" {
  zone_id = var.algenta_zone_id
  name    = "docs"
  type    = "CNAME"
  content = "c5dc63adab-hosting.gitbook.io"
  proxied = false
  ttl     = 300
  comment = "Algenta docs → GitBook (Algenta site)"
}
