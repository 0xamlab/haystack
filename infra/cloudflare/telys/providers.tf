# Cloudflare edge for the TELYS product surface (OpenTofu) — the telys.ai zone.
#
# WHY THIS MODULE EXISTS: api.telys.ai fronts the SAME Fly app as the algenta control plane
# (algenta-control-plane), so it serves the same brute-force-sensitive surfaces — /v1/device/register,
# /v1/license/challenge, /v1/license/renew, /v1/auth*. But every rule in
# infra/cloudflare/algenta-control-plane/waf.tf is gated on `http.host eq "api.algenta.ai"`, and the
# telys.ai zone had NO http_ratelimit ruleset at all. The telys hostname was therefore running the
# licensing/activation surface with zero edge rate limiting. This module closes that gap and brings the
# previously dashboard-only telys.ai records under review.
#
# Separate from infra/cloudflare/ (codna.ai) and infra/cloudflare/algenta-control-plane/ (algenta.ai):
# different zone, same origin app. Edge only — DNS, TLS, cache policy, WAF/rate-limit.
#
# Auth via env:  TF_VAR_cloudflare_api_token, TF_VAR_cloudflare_account_id,
#                TF_VAR_telys_zone_id (the telys.ai zone id).
# Plan (start here — see README, the pre-existing records are adopted via import blocks):
#   cd infra/cloudflare/telys && tofu init && tofu plan
terraform {
  required_version = ">= 1.6.0" # import blocks
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.40"
    }
  }
}

variable "cloudflare_api_token" {
  type      = string
  sensitive = true
}
variable "cloudflare_account_id" {
  type = string
}
variable "telys_zone_id" {
  type        = string
  description = "Cloudflare zone id for telys.ai"
}
variable "root_domain" {
  type    = string
  default = "telys.ai"
}

# api.telys.ai is pinned to the control-plane Fly app's DEDICATED IPs (A + AAAA), not a CNAME to
# <app>.fly.dev. That is how the record was created in the dashboard, and it is what these defaults
# reproduce so `tofu plan` is clean on adoption. Trade-off worth knowing: an IP pin breaks if the Fly
# app's dedicated IP is ever released/reallocated, where a CNAME would follow it. Changing the record
# type is a separate, deliberate migration — do NOT fold it into the adoption plan.
#   fly ips list -a algenta-control-plane
variable "control_plane_origin_ipv4" {
  type    = string
  default = "66.241.125.156"
}
variable "control_plane_origin_ipv6" {
  type    = string
  default = "2a09:8280:1::130:43b7:0"
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}
