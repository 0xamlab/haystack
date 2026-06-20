# Cache policy for the control plane: BYPASS everything dynamic/authenticated (issuance, auth,
# billing, device, credits, metering, renewal) so an activation/renewal/billing response is NEVER
# served stale from the edge; CACHE only the immutable, self-authenticating verification surfaces
# (JWKS + the signed CRL), which are short-TTL signed artifacts safe to serve from cache.
resource "cloudflare_ruleset" "control_plane_cache" {
  zone_id = var.algenta_zone_id
  name    = "algenta-control-plane-cache"
  kind    = "zone"
  phase   = "http_request_cache_settings"

  # Order matters: bypass runs first.
  rules {
    description = "Bypass cache for dynamic + authenticated control-plane paths"
    enabled     = true
    expression  = <<-EOT
      (http.host eq "api.algenta.ai") and (
        (http.request.method ne "GET") or
        (starts_with(http.request.uri.path, "/v1/auth")) or
        (starts_with(http.request.uri.path, "/auth")) or
        (starts_with(http.request.uri.path, "/v1/account")) or
        (starts_with(http.request.uri.path, "/v1/team")) or
        (starts_with(http.request.uri.path, "/v1/billing")) or
        (starts_with(http.request.uri.path, "/v1/credits")) or
        (starts_with(http.request.uri.path, "/v1/metering")) or
        (starts_with(http.request.uri.path, "/v1/device")) or
        (eq(http.request.uri.path, "/v1/license/challenge")) or
        (eq(http.request.uri.path, "/v1/license/renew")) or
        (starts_with(http.request.uri.path, "/v1/control-plane")) or
        (len(http.request.headers["authorization"]) > 0) or
        (len(http.request.headers["cookie"]) > 0)
      )
    EOT
    action      = "set_cache_settings"
    action_parameters {
      cache = false
    }
  }

  # The ONLY cacheable control-plane surfaces: the public, signed verification artifacts.
  rules {
    description = "Cache JWKS + the signed CRL (short TTL, override origin)"
    enabled     = true
    expression  = <<-EOT
      (http.host eq "api.algenta.ai") and (http.request.method eq "GET") and (
        (eq(http.request.uri.path, "/.well-known/jwks.json")) or
        (eq(http.request.uri.path, "/v1/license/revocations"))
      )
    EOT
    action      = "set_cache_settings"
    action_parameters {
      cache = true
      edge_ttl {
        mode    = "override_origin"
        default = 3600
      }
      browser_ttl {
        mode    = "override_origin"
        default = 3600
      }
    }
  }
}
