# TLS: Full (Strict) — Cloudflare validates the Fly origin cert end-to-end. Requires a valid Fly
# cert for api.codna.ai first (see dns.tf cert-ordering note).
resource "cloudflare_zone_settings_override" "codna" {
  zone_id = var.cloudflare_zone_id

  settings {
    ssl                      = "strict" # Full (Strict)
    always_use_https         = "on"
    min_tls_version          = "1.2"
    tls_1_3                  = "on"
    automatic_https_rewrites = "on"
    brotli                   = "on"
  }
}
