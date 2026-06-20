# TLS: Full (Strict) for algenta.ai — Cloudflare validates the Fly origin cert end-to-end.
# Requires a Ready Fly cert for api.algenta.ai first (see dns.tf cert-ordering note).
resource "cloudflare_zone_settings_override" "algenta" {
  zone_id = var.algenta_zone_id

  settings {
    ssl                      = "strict" # Full (Strict)
    always_use_https         = "on"
    min_tls_version          = "1.2"
    tls_1_3                  = "on"
    automatic_https_rewrites = "on"
    brotli                   = "on"
  }
}
