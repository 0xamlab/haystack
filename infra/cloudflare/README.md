# Cloudflare edge modules — remote state setup

Three OpenTofu modules live here, one per zone. **All three share one R2 state bucket, with a distinct
key per module** — never a shared key, or two zones would fight over one state file.

| Module | Zone | State key | Applied? |
|---|---|---|---|
| [`.`](.) | `codna.ai` | `cloudflare/codna/terraform.tfstate` | never |
| [`algenta-control-plane/`](algenta-control-plane) | `algenta.ai` | `cloudflare/algenta-control-plane/terraform.tfstate` | never |
| [`telys/`](telys) | `telys.ai` | `cloudflare/telys/terraform.tfstate` | **yes** — 2026-07-28 |

(`license-signer/` is a Cloudflare Worker deployed with `wrangler`, not Terraform.)

## Why remote state

These modules previously had **no backend**, so `tofu apply` wrote state to whatever working copy it ran
from. After `telys/` was first applied, a single local file in an ad-hoc worktree was the only record
that `telys-control-plane-ratelimit` / `-cache` / `-config` are Terraform-managed. Lose it and the next
apply re-**creates** those rulesets — but a zone permits only one entrypoint ruleset per phase, so the
apply either fails or clobbers live edge config.

`import` blocks protect *pre-existing* resources. They do not protect anything a module **created**.

The two never-applied modules make the cost concrete: nothing recorded that
`api.algenta.ai`'s declared CNAME was never realised, and it silently drifted to a different Fly app.

## Required environment

Credentials and the endpoint are **not** committed: the R2 S3 endpoint embeds the Cloudflare account id,
which appears in no committed file in this repo. Export from `.env`:

```sh
# state backend (R2, S3-compatible)
export AWS_ENDPOINT_URL_S3="$CLOUDFLARE_S3_COMPATIBLE_ENDPOINT"   # https://<account_id>.r2.cloudflarestorage.com
export AWS_ACCESS_KEY_ID="$CLOUDFLARE_R2_S3_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$CLOUDFLARE_SECRET_ACCESS_KEY"

# R2 rejects the AWS SDK's default trailing checksums; without these, PutObject fails
export AWS_REQUEST_CHECKSUM_CALCULATION=when_required
export AWS_RESPONSE_CHECKSUM_VALIDATION=when_required

# the Cloudflare provider itself
export TF_VAR_cloudflare_api_token="$CLOUDFLARE_API_TOKEN"
export TF_VAR_cloudflare_account_id="$CLOUDFLARE_ACCOUNT_ID"
export TF_VAR_telys_zone_id=…        # or algenta_zone_id / cloudflare_zone_id per module
```

Then, per module:

```sh
cd infra/cloudflare/<module>
tofu init
tofu plan          # ALWAYS. See each module's own notes before applying.
```

## Locking

`use_lockfile = true` is OpenTofu's native S3-object lock (requires **>= 1.10**; verified on v1.12.3).
It writes a sibling `<key>.tflock` object and needs no DynamoDB, which R2 does not provide. This matters
here more than usual: two concurrent applies against a zone that fronts device registration and license
minting could otherwise interleave writes.

## ⚠️ Known gap: R2 has no object versioning

The S3 backend's usual safety net — bucket versioning, to roll back a corrupted state file — is
**unavailable**. R2 exposes no versioning API (confirmed 2026-07-28; the Cloudflare endpoint returns
`No route matches this url`). Remote + locked state is a large improvement over one file in a throwaway
worktree, but it is **not** a backup.

Mitigations, in order of preference:

1. OpenTofu writes `terraform.tfstate.<serial>.backup` locally on each state change — that is the
   immediate rollback path. Do not delete those.
2. Before any risky apply: `tofu state pull > /tmp/<module>-$(date +%s).tfstate`.
3. If this grows past one applied zone, schedule a copy of the R2 objects somewhere versioned.

## Bucket

`algenta-tfstate` (R2, location hint `ENAM`), created 2026-07-28. It holds **only** Terraform state —
do not put artifacts in it. Artifact buckets are separate: `codna-artifacts`, `telys-runtime`,
`sqai-runtime`.

## Provider pinning (a remaining soft spot)

`.terraform.lock.hcl` is **not committed**, matching existing convention here. Now that these modules
share remote state that is a mild risk: two operators on different provider versions can write state the
other reads. Version drift is bounded by `required_providers { cloudflare = "~> 4.40" }` in each
module's `providers.tf`, which is adequate but not exact.

Committing the lock file would close it properly — but only if generated for every platform anyone uses,
otherwise it hard-fails for everyone else:

```sh
tofu providers lock -platform=darwin_arm64 -platform=linux_amd64
```

Worth doing as its own change. A lock file generated on one platform and committed blindly is worse than
none.
