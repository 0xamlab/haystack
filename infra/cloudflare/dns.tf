# DNS: api.codna.ai → Fly codna-api (proxied); app.codna.ai → frontend (optional).
#
# ⚠️ Cert ordering (see DEPLOY.md): Fly must hold a valid cert for api.codna.ai BEFORE Cloudflare
# proxies in Full-Strict, or the ACME challenge can be intercepted by the orange cloud. Sequence:
#   1) `fly certs add api.codna.ai -a codna-api`
#   2) create this record with proxied=false (grey) so Fly's challenge reaches the origin
#   3) once `fly certs show` is "Ready", set proxied=true (orange) and apply Full-Strict (tls.tf)
# Toggle via the `api_proxied` variable below.
variable "api_proxied" {
  type    = bool
  default = true
}

resource "cloudflare_record" "api" {
  zone_id = var.cloudflare_zone_id
  name    = "api"
  type    = "CNAME"
  content = var.api_origin_hostname
  proxied = var.api_proxied
  ttl     = 1
  comment = "codna engine API → Fly codna-api"
}

resource "cloudflare_record" "app" {
  count   = var.app_origin_hostname == "" ? 0 : 1
  zone_id = var.cloudflare_zone_id
  name    = "app"
  type    = "CNAME"
  content = var.app_origin_hostname
  proxied = true
  ttl     = 1
  comment = "codna dashboard/frontend"
}
