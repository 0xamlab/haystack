# WAF: per-IP rate limit on the API + the Cloudflare Managed Ruleset.
# NOTE: the managed ruleset + advanced rate-limiting need a paid Cloudflare plan; on Free, keep just
# the rate-limit rule (or a simpler one) — `tofu plan` will show what your plan allows.

# The webhook path is deliberately NOT rate-limited here: GitHub bursts + retries legitimately, and
# the origin already dedupes (durable delivery claim) — edge throttling would drop real deliveries.
resource "cloudflare_ruleset" "ratelimit" {
  zone_id = var.cloudflare_zone_id
  name    = "codna-ratelimit"
  kind    = "zone"
  phase   = "http_ratelimit"

  rules {
    description = "Per-IP API rate limit (excludes the GitHub webhook)"
    enabled     = true
    expression  = <<-EOT
      (starts_with(http.request.uri.path, "/v1/")) and
      not (starts_with(http.request.uri.path, "/webhooks/github"))
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

resource "cloudflare_ruleset" "waf_managed" {
  zone_id = var.cloudflare_zone_id
  name    = "codna-waf-managed"
  kind    = "zone"
  phase   = "http_request_firewall_managed"

  rules {
    description = "Deploy the Cloudflare Managed Ruleset"
    enabled     = true
    expression  = "true"
    action      = "execute"
    action_parameters {
      id = "efb7b8c949ac4650a09736fc376e9aee" # Cloudflare Managed Ruleset (well-known id)
    }
  }
}
