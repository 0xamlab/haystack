# Cloudflare edge for the ALGENTA CONTROL PLANE (OpenTofu) — the algenta.ai zone.
# Separate from infra/cloudflare/ (the codna.ai zone): different zone, different Fly app.
# Edge only — DNS, TLS (Full-Strict), cache policy, WAF/rate-limit. No object storage here.
#
# Auth via env:  TF_VAR_cloudflare_api_token, TF_VAR_cloudflare_account_id,
#                TF_VAR_algenta_zone_id (the algenta.ai zone id).
# Apply (OWNER):  cd infra/cloudflare/algenta-control-plane && tofu init && tofu apply
terraform {
  required_version = ">= 1.6.0"
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
variable "algenta_zone_id" {
  type        = string
  description = "Cloudflare zone id for algenta.ai"
}
variable "root_domain" {
  type    = string
  default = "algenta.ai"
}
# The control-plane Fly app origin (proxied behind Cloudflare).
variable "control_plane_origin_hostname" {
  type    = string
  default = "algenta-control-plane.fly.dev"
}
# Grey→orange cert ordering (see dns.tf): start proxied=false until Fly's cert is Ready.
variable "control_plane_proxied" {
  type    = bool
  default = true
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}
