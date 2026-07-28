# Origin guard (Cloudflare half) — inject the shared secret the origin checks for.
#
# ── THE PROBLEM ─────────────────────────────────────────────────────────────────────────────────────
# Every control in this module is bound to the PROXIED HOSTNAME api.telys.ai. The Fly app also answers
# on algenta-control-plane.fly.dev, which never traverses Cloudflare, so all of it is skippable.
# Measured 2026-07-28:
#
#   40 x POST https://api.telys.ai/v1/device/register               -> 429 from request 31 (limited)
#   40 x POST https://algenta-control-plane.fly.dev/v1/device/...   -> 40 x 401, ZERO blocking
#   GET  https://api.algenta.ai/metrics                             -> 403
#   GET  https://algenta-control-plane.fly.dev/metrics              -> 200, 3662 bytes
#
# The rate limit in waf.tf is not wrong; it is optional. This rule is what makes it mandatory: it sets
# a header that only requests traversing this zone can carry, and the origin rejects requests without
# it (apps/api_server/middleware/origin_guard.py).
#
# ── WHY A HEADER AND NOT mTLS ───────────────────────────────────────────────────────────────────────
# Cloudflare Authenticated Origin Pulls is the canonical mechanism, but Fly terminates TLS at its own
# proxy and does not surface the client certificate to the app, so the origin cannot verify it. An IP
# allowlist is worse: Cloudflare's ranges change, and behind Fly's proxy the only client-IP signal is a
# forwardable header. A shared secret header is Cloudflare's own recommendation when mTLS is off the
# table.
#
# ── ROLLOUT: DO NOT SKIP THE LOG STAGE ──────────────────────────────────────────────────────────────
# Applying this rule ALONE is safe and inert — it only adds a header nobody reads yet. Turning on
# enforcement is a separate, reversible Fly-secret change:
#
#   1. openssl rand -hex 32                       # generate once, use the same value in both places
#   2. tofu apply -var="origin_shared_secret=<v>" # this rule starts stamping the header
#   3. fly secrets set -a algenta-control-plane ORIGIN_SHARED_SECRET=<v> ORIGIN_GUARD_MODE=log
#   4. watch logs for origin_guard.missing_header — a steady stream means the rule is NOT applying,
#      so stop and fix before going further
#   5. fly secrets set -a algenta-control-plane ORIGIN_GUARD_MODE=enforce
#   6. verify: api.telys.ai/v1/health -> 200, algenta-control-plane.fly.dev/v1/device/register -> 403
#
# Rollback is one command and needs no deploy: fly secrets set ORIGIN_GUARD_MODE=log
#
# ── SECRET HANDLING ─────────────────────────────────────────────────────────────────────────────────
# The value is a sensitive variable and is NOT committed. It does land in Terraform state, which is
# why state lives in R2 rather than a working copy (see ../README.md). Pass it per-apply:
#   TF_VAR_origin_shared_secret=… tofu apply
# Leaving it empty (the default) means this ruleset is NOT created at all, so the module stays exactly
# as it is today until someone deliberately opts in.

variable "origin_shared_secret" {
  type        = string
  sensitive   = true
  default     = ""
  description = "Shared secret injected as X-Origin-Auth. Empty (default) = do not create the rule."
}

resource "cloudflare_ruleset" "telys_origin_guard" {
  count = var.origin_shared_secret == "" ? 0 : 1

  zone_id = var.telys_zone_id
  name    = "telys-origin-guard"
  kind    = "zone"
  phase   = "http_request_late_transform"

  rules {
    description = "Stamp X-Origin-Auth so the origin can reject requests that skipped Cloudflare"
    enabled     = true
    expression  = "(http.host eq \"api.telys.ai\")"
    action      = "rewrite"
    action_parameters {
      headers {
        name      = "X-Origin-Auth"
        operation = "set" # "set" not "add": overwrite any client-supplied value, never append to it
        value     = var.origin_shared_secret
      }
    }
  }
}
