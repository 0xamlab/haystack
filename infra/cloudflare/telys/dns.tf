# DNS for the telys.ai zone.
#
# SCOPE: only the records that serve the Telys PRODUCT surface (api / packages / docs) are declared
# here. The marketing + mail records (telys.ai and www.telys.ai → Vercel, _dmarc, the Google site
# verification TXT, _domainconnect) are deliberately left UNMANAGED: they are owned by the website /
# mail setup, not by this control-plane module, and Terraform only manages what it declares — it will
# not touch or delete an undeclared record. Splitting them keeps the blast radius of an `apply` here
# limited to the API surface.

# api.telys.ai → Fly algenta-control-plane (proxied). Same origin app as api.algenta.ai is *supposed*
# to front; see the WARNING in ../algenta-control-plane/dns.tf about that hostname's live state.
resource "cloudflare_record" "api_v4" {
  zone_id = var.telys_zone_id
  name    = "api"
  type    = "A"
  content = var.control_plane_origin_ipv4
  proxied = true
  ttl     = 1
  comment = "Telys control plane API → Fly algenta-control-plane"
}

resource "cloudflare_record" "api_v6" {
  zone_id = var.telys_zone_id
  name    = "api"
  type    = "AAAA"
  content = var.control_plane_origin_ipv6
  proxied = true
  ttl     = 1
  comment = "Telys control plane API → Fly algenta-control-plane"
}

# packages.telys.ai → the telys-runtime-host Cloudflare Worker, which serves the SIGNED runtime
# bundle. The AAAA 100:: placeholder is the standard Cloudflare pattern for a hostname handled purely
# by a Worker route: there is no origin, the placeholder just makes the name proxiable so the route
# binds. The route itself + CONTROL_PLANE_URL live in the Worker's wrangler.toml, NOT here:
#   memory-engine/infra/cloudflare/telys-runtime-host/wrangler.toml
# Deploying that Worker is what actually makes this hostname serve anything.
resource "cloudflare_record" "packages" {
  zone_id = var.telys_zone_id
  name    = "packages"
  type    = "AAAA"
  content = "100::"
  proxied = true
  ttl     = 1
  comment = "Telys runtime host Worker (route bound in telys-runtime-host/wrangler.toml)"
}

# docs.telys.ai → GitBook. DNS-only (grey): GitBook terminates TLS and issues the cert itself once the
# domain is registered on the Telys site + published. Proxying this would break their cert issuance.
resource "cloudflare_record" "docs" {
  zone_id = var.telys_zone_id
  name    = "docs"
  type    = "CNAME"
  content = "c5dc63adab-hosting.gitbook.io"
  proxied = false
  ttl     = 1
  comment = "Telys GitBook docs site (site_ENmp0)"
}
