#!/usr/bin/env bash
# Roll an app back to a previous image tag. Usage: scripts/rollback.sh <api|engine> <IMAGE_TAG>
# e.g. scripts/rollback.sh api git-1a2b3c4   (list candidates with `fly releases -a codna-api`)
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_deploy_common.sh"
need flyctl
[ $# -eq 2 ] || die "usage: rollback.sh <api|engine> <IMAGE_TAG>"
case "$1" in
  api)    app="$CODNA_API_APP";    cfg="${_repo_root}/fly.api.toml";    img="${IMAGE_REPO}/api:$2" ;;
  engine) app="$CODNA_ENGINE_APP"; cfg="${_repo_root}/fly.engine.toml"; img="${IMAGE_REPO}/engine:$2" ;;
  *) die "first arg must be api or engine" ;;
esac
log "rolling $app back to $img"
fly deploy -c "$cfg" -a "$app" -i "$img"
log "rollback complete"
