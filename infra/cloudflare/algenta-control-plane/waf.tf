# WAF for the control plane: a baseline per-IP API rate limit + a STRICTER limit on the
# brute-force-sensitive surfaces (login/signup + device registration), plus the Cloudflare
# Managed Ruleset. The Stripe webhook is excluded from rate-limiting (Stripe bursts + retries
# legitimately and the origin dedupes via the StripeWebhookEvent ledger — edge throttling would
# drop real deliveries). Managed ruleset + advanced rate-limiting need a paid plan.

resource "cloudflare_ruleset" "control_plane_ratelimit" {
  zone_id = var.algenta_zone_id
  name    = "algenta-control-plane-ratelimit"
  kind    = "zone"
  phase   = "http_ratelimit"

  # Tight limit on auth + device registration (anti brute-force / signup abuse).
  rules {
    description = "Strict per-IP limit on auth + device registration"
    enabled     = true
    expression  = <<-EOT
      (http.host eq "api.algenta.ai") and (
        starts_with(http.request.uri.path, "/v1/auth") or
        starts_with(http.request.uri.path, "/auth") or
        http.request.uri.path eq "/v1/device/register"
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

  # Baseline API limit (excludes the Stripe webhook).
  rules {
    description = "Per-IP API rate limit (excludes the Stripe webhook)"
    enabled     = true
    expression  = <<-EOT
      (http.host eq "api.algenta.ai") and
      (starts_with(http.request.uri.path, "/v1/")) and
      not (http.request.uri.path eq "/v1/billing/webhook")
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

resource "cloudflare_ruleset" "control_plane_waf_managed" {
  zone_id = var.algenta_zone_id
  name    = "algenta-control-plane-waf-managed"
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
