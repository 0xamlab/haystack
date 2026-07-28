# Remote state in Cloudflare R2 (S3-compatible), with native object-lock concurrency.
#
# ── WHY ─────────────────────────────────────────────────────────────────────────────────────────────
# This directory previously had NO backend, so `tofu apply` wrote state to whatever working copy it was
# run from. After the first real apply that meant a single local file was the ONLY record that
# telys-control-plane-ratelimit / -cache / -config are Terraform-managed. Lose it and the next apply
# re-CREATES those three rulesets — but a zone permits only one entrypoint ruleset per phase, so the
# apply either fails or clobbers live edge config. The `import` blocks in imports.tf protect the
# pre-existing resources; they do not protect anything this module created.
#
# Same exposure applies to the sibling modules, which is not hypothetical: ../algenta-control-plane has
# never been applied from any checkout, and api.algenta.ai duly drifted from its declaration.
#
# ── SECRETS: NOTHING SENSITIVE IS COMMITTED HERE ────────────────────────────────────────────────────
# The R2 S3 endpoint embeds the Cloudflare ACCOUNT ID, which is not present in any committed file in
# this repo, so it is deliberately NOT hardcoded below. Supply it — and the credentials — by env var:
#
#   export AWS_ENDPOINT_URL_S3="https://<account_id>.r2.cloudflarestorage.com"   # = CLOUDFLARE_S3_COMPATIBLE_ENDPOINT
#   export AWS_ACCESS_KEY_ID="$CLOUDFLARE_R2_S3_ACCESS_KEY_ID"
#   export AWS_SECRET_ACCESS_KEY="$CLOUDFLARE_SECRET_ACCESS_KEY"
#
#   # R2 rejects the AWS SDK's default trailing checksums; without these, PutObject 501s / 400s.
#   export AWS_REQUEST_CHECKSUM_CALCULATION=when_required
#   export AWS_RESPONSE_CHECKSUM_VALIDATION=when_required
#
# Equivalent without env vars:
#   tofu init -backend-config="endpoints={s3=\"https://<account_id>.r2.cloudflarestorage.com\"}"
#
# ── LOCKING ─────────────────────────────────────────────────────────────────────────────────────────
# `use_lockfile = true` is OpenTofu's native S3-object lock (>= 1.10). It writes a sibling
# `<key>.tflock` object and needs no DynamoDB, which R2 does not have. This matters more than usual
# here: two people applying edge config at once could otherwise interleave writes to a zone that
# fronts device registration and license minting.
#
# ── KNOWN GAP: R2 HAS NO OBJECT VERSIONING ──────────────────────────────────────────────────────────
# The S3 backend's usual safety net — bucket versioning, to roll back a corrupted state file — is
# unavailable: R2 exposes no versioning API (confirmed 2026-07-28, the Cloudflare endpoint returns
# "No route matches this url"). Remote + locked is still a large improvement over one file in a
# throwaway worktree, but it is NOT a substitute for backups. OpenTofu writes a local
# `terraform.tfstate.<serial>.backup` next to the module on each state change; treat that as the
# rollback path, and consider a scheduled copy of the R2 object if this grows beyond one zone.
terraform {
  backend "s3" {
    bucket = "algenta-tfstate"
    key    = "cloudflare/telys/terraform.tfstate"

    # R2 is not AWS: it has no regions, no IMDS, no STS. These skips stop the AWS SDK from trying to
    # validate against services R2 does not implement. `region` must still be set to something.
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
