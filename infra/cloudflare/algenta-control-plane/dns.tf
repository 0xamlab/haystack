# DNS: api.algenta.ai → Fly algenta-control-plane (proxied). The license SIGNER is its OWN
# Cloudflare Worker on license.algenta.ai (route bound in the Worker's wrangler.toml — it never
# traverses Fly), so there is NO Fly CNAME for license.algenta.ai here.
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

# docs.algenta.ai → GitBook (Algenta site). Target confirmed from the org's existing custom
# domain docs.cohenta.ai, which resolves to hosting.gitbook.io. DNS-only (grey): GitBook
# terminates TLS and issues the cert once the domain is registered on the Algenta site + published.
resource "cloudflare_record" "docs" {
  zone_id = var.algenta_zone_id
  name    = "docs"
  type    = "CNAME"
  content = "hosting.gitbook.io"
  proxied = false
  ttl     = 300
  comment = "Algenta docs → GitBook (hosting.gitbook.io)"
}
