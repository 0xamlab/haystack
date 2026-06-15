#!/usr/bin/env bash
# Apply the Cloudflare edge (DNS, TLS Full-Strict, cache rules, WAF/rate-limit) via OpenTofu.
# Requires: tofu (or terraform) + TF_VAR_cloudflare_api_token / _account_id / _zone_id in the env.
# The optional edge Worker (wrangler) is deferred; pass --worker to deploy it if infra/cloudflare
# contains a wrangler.toml.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_deploy_common.sh"

TF="tofu"; command -v tofu >/dev/null 2>&1 || TF="terraform"
need "$TF"
: "${TF_VAR_cloudflare_api_token:?set TF_VAR_cloudflare_api_token (the CLOUDFLARE_API_TOKEN)}"
: "${TF_VAR_cloudflare_account_id:?set TF_VAR_cloudflare_account_id}"
: "${TF_VAR_cloudflare_zone_id:?set TF_VAR_cloudflare_zone_id}"

cd "${_repo_root}/infra/cloudflare"
log "tofu init"; "$TF" init -input=false
log "tofu apply"; "$TF" apply -input=false "${TF_AUTO_APPROVE:+-auto-approve}"

if [ "${1:-}" = "--worker" ] && [ -f "${_repo_root}/infra/cloudflare/wrangler.toml" ]; then
  need npx
  log "wrangler deploy (edge worker)"
  ( cd "${_repo_root}/infra/cloudflare" && npx wrangler deploy )
fi
log "cloudflare apply complete"
