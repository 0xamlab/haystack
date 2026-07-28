# Cache policy for api.telys.ai, mirroring ../algenta-control-plane/cache-rules.tf.
#
# The telys.ai zone had NO cache ruleset, so api.telys.ai ran on Cloudflare's default cache behaviour
# for the activation/licensing surface. Default behaviour does not cache authenticated responses, so
# this is hardening rather than an active-bug fix — but it makes the guarantee EXPLICIT and identical
# on both hostnames into the origin, instead of relying on a default that could change.
#
# BYPASS everything dynamic/authenticated (issuance, auth, billing, device, credits, metering,
# renewal) so an activation/renewal/billing response is NEVER served stale from the edge; CACHE only
# the immutable, self-authenticating verification surfaces (JWKS + the signed CRL), which are
# short-TTL signed artifacts safe to serve from cache.
resource "cloudflare_ruleset" "telys_cache" {
  zone_id = var.telys_zone_id
  name    = "telys-control-plane-cache"
  kind    = "zone"
  phase   = "http_request_cache_settings"

  # Order matters: bypass runs first.
  rules {
    description = "Bypass cache for dynamic + authenticated control-plane paths"
    enabled     = true
    expression  = <<-EOT
      (http.host eq "api.telys.ai") and (
        (http.request.method ne "GET") or
        (starts_with(http.request.uri.path, "/v1/auth")) or
        (starts_with(http.request.uri.path, "/auth")) or
        (starts_with(http.request.uri.path, "/v1/account")) or
        (starts_with(http.request.uri.path, "/v1/team")) or
        (starts_with(http.request.uri.path, "/v1/billing")) or
        (starts_with(http.request.uri.path, "/v1/credits")) or
        (starts_with(http.request.uri.path, "/v1/metering")) or
        (starts_with(http.request.uri.path, "/v1/device")) or
        (starts_with(http.request.uri.path, "/v1/telys")) or
        (http.request.uri.path eq "/v1/license/challenge") or
        (http.request.uri.path eq "/v1/license/renew") or
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

  # JWKS: the signer's public key. Safe to cache for an hour — keys rotate on the order of months,
  # and a runtime that meets an unknown kid re-fetches.
  rules {
    description = "Cache JWKS (1h, override origin)"
    enabled     = true
    expression  = <<-EOT
      (http.host eq "api.telys.ai") and (http.request.method eq "GET") and
      (http.request.uri.path eq "/.well-known/jwks.json")
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

  # The signed CRL gets a SHORT ttl, deliberately different from JWKS.
  #
  # ../algenta-control-plane/cache-rules.tf caches both for 3600s in one rule, and this module
  # originally copied that verbatim. That is wrong for a revocation list: `override_origin` means the
  # origin cannot shorten it, so revoking a compromised device would not take effect at the edge for
  # up to an hour, and the runtime's revocation check is fail-open. Caching the CRL and caching a
  # public key are not the same problem and should not share a TTL.
  #
  # 120s keeps essentially all of the origin-load benefit (runtimes poll far less often than that)
  # while bounding revocation propagation to ~2 minutes. The algenta module very likely has the same
  # defect and should be fixed the same way — flagged rather than silently diverged from.
  rules {
    description = "Cache the signed CRL briefly (120s) — bounds revocation propagation"
    enabled     = true
    expression  = <<-EOT
      (http.host eq "api.telys.ai") and (http.request.method eq "GET") and
      (http.request.uri.path eq "/v1/license/revocations")
    EOT
    action      = "set_cache_settings"
    action_parameters {
      cache = true
      edge_ttl {
        mode    = "override_origin"
        default = 120
      }
      browser_ttl {
        mode    = "override_origin"
        default = 120
      }
    }
  }
}
