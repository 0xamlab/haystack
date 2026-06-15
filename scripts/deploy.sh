#!/usr/bin/env bash
# Full deploy: Fly apps, then the Cloudflare edge. Assumes `bootstrap.sh` already ran + secrets set.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_deploy_common.sh"
"${_here}/deploy-fly.sh" "$@"
"${_here}/deploy-cloudflare.sh"
"${_here}/status.sh"
