# Remote state in Cloudflare R2 (S3-compatible). See ../README.md for the required env vars and the
# rationale; this file only sets the state key for THIS module.
#
# This module has never been applied from any checkout, so there is no local state to migrate — the
# first `tofu init` here simply starts a fresh remote state. That absence is not a curiosity: it is why
# api.algenta.ai drifted from its declaration in the first place, with nothing recording that the
# declared CNAME was never realised.
#
# ⚠️ BEFORE YOU `tofu apply` THIS MODULE, read the DO NOT APPLY warning at the top of dns.tf. Live
# api.algenta.ai is an A record to codna-api (the full app, 218 paths), NOT the CNAME to
# algenta-control-plane declared here. Applying as-written would repoint the hostname at the
# engine-free control plane and 404 every engine caller (/v1/simulate, /v1/recommend, /v1/query, /mcp).
# Configuring remote state does NOT make that safe; it only makes the outcome recorded.
#
# Also outstanding in this module: cache-rules.tf caches the signed CRL for 3600s with
# `override_origin`, so a revoked device keeps validating at the edge for up to an hour on a fail-open
# path. ../telys/cache-rules.tf splits JWKS (3600s) from the CRL (120s) for exactly this reason; the
# same fix is wanted here.
terraform {
  backend "s3" {
    bucket = "algenta-tfstate"
    key    = "cloudflare/algenta-control-plane/terraform.tfstate"

    region                      = "auto"
    use_path_style              = true
    use_lockfile                = true
    skip_credentials_validation = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    skip_metadata_api_check     = true
    skip_s3_checksum            = true
  }
}
