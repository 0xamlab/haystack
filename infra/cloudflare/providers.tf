# Cloudflare edge for codna (OpenTofu). Edge only — DNS, TLS, cache, WAF/rate-limit.
# Object storage is Tigris (Fly), NOT Cloudflare R2.
#
# Auth via env:  TF_VAR_cloudflare_api_token (the existing CLOUDFLARE_API_TOKEN),
#                TF_VAR_cloudflare_account_id, TF_VAR_cloudflare_zone_id.
# Apply:  cd infra/cloudflare && tofu init && tofu apply
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
variable "cloudflare_zone_id" {
  type = string
}
variable "root_domain" {
  type    = string
  default = "codna.ai"
}
# Fly origin hostnames (proxied behind Cloudflare).
variable "api_origin_hostname" {
  type    = string
  default = "codna-api.fly.dev"
}
# Frontend/app origin — leave empty to skip the app.codna.ai record (deferred).
variable "app_origin_hostname" {
  type    = string
  default = ""
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}
