# Cache policy: static/immutable only. Everything dynamic or authenticated is bypassed so a webhook,
# auth, job, repo-mutation, or billing response is never served from the edge.
resource "cloudflare_ruleset" "cache" {
  zone_id = var.cloudflare_zone_id
  name    = "codna-cache"
  kind    = "zone"
  phase   = "http_request_cache_settings"

  # Order matters: the bypass rule runs first.
  rules {
    description = "Bypass cache for dynamic + authenticated paths"
    enabled     = true
    expression  = <<-EOT
      (http.request.method ne "GET") or
      (starts_with(http.request.uri.path, "/webhooks/github")) or
      (starts_with(http.request.uri.path, "/v1/auth")) or
      (starts_with(http.request.uri.path, "/v1/jobs")) or
      (starts_with(http.request.uri.path, "/v1/repos")) or
      (starts_with(http.request.uri.path, "/v1/billing")) or
      (len(http.request.headers["authorization"]) > 0) or
      (len(http.request.headers["cookie"]) > 0)
    EOT
    action      = "set_cache_settings"
    action_parameters {
      cache = false
    }
  }

  rules {
    description = "Cache static / immutable assets at the edge"
    enabled     = true
    expression  = <<-EOT
      (starts_with(http.request.uri.path, "/assets/")) or
      (starts_with(http.request.uri.path, "/static/")) or
      (http.request.uri.path eq "/favicon.ico") or
      (starts_with(http.request.uri.path, "/docs/public/")) or
      (starts_with(http.request.uri.path, "/artifacts/public/immutable/"))
    EOT
    action      = "set_cache_settings"
    action_parameters {
      cache = true
      edge_ttl {
        mode    = "override_origin"
        default = 86400
      }
      browser_ttl {
        mode    = "override_origin"
        default = 3600
      }
    }
  }
}
