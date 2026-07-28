# Remote state in Cloudflare R2 (S3-compatible) for the codna.ai zone module.
# See ./README.md for the required env vars and the rationale; this file only sets the state key.
#
# Like the algenta-control-plane module, this one has no local state — it has never been applied from a
# checkout. Run `tofu plan` and reconcile against live state BEFORE any apply: a module that has never
# been applied will plan every resource as "to create", which for DNS means it may be describing
# records that already exist with different values. Adopt those with `import` blocks (see
# ./telys/imports.tf for the pattern) rather than letting Terraform create duplicates.
terraform {
  backend "s3" {
    bucket = "algenta-tfstate"
    key    = "cloudflare/codna/terraform.tfstate"

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
