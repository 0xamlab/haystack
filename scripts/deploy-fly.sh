#!/usr/bin/env bash
# Deploy the two Fly apps from prebuilt GHCR images. Engine first (so the sidecar is live before the
# api references codna-engine.internal), then api (its release_command runs `alembic upgrade head`).
# Usage: scripts/deploy-fly.sh [IMAGE_TAG]   (default tag = git-<short-sha> of HEAD)
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_deploy_common.sh"
need flyctl; need git

TAG="${1:-git-$(git -C "$_repo_root" rev-parse --short HEAD)}"
API_IMAGE="${IMAGE_REPO}/api:${TAG}"
ENGINE_IMAGE="${IMAGE_REPO}/engine:${TAG}"

# Private GHCR pull auth at DEPLOY time (not just runtime). Skip if the images are public.
if [ -n "${GHCR_PULL_TOKEN:-}" ]; then
  log "authenticating Fly's pull to GHCR"
  echo "$GHCR_PULL_TOKEN" | fly auth docker --stdin 2>/dev/null \
    || log "  (fly auth docker unavailable; ensure GHCR images are public or pre-pulled)"
fi

log "deploy engine → $ENGINE_IMAGE (single warm Machine + volume)"
fly deploy -c "${_repo_root}/fly.engine.toml" -a "$CODNA_ENGINE_APP" -i "$ENGINE_IMAGE" --regions "$FLY_REGION" --ha=false
fly scale count 1 -a "$CODNA_ENGINE_APP" --yes   # exactly one Machine (single volume); no scale-to-zero

log "deploy api → $API_IMAGE (runs alembic upgrade head, then rolls)"
fly deploy -c "${_repo_root}/fly.api.toml" -a "$CODNA_API_APP" -i "$API_IMAGE"
fly scale count "${API_MIN_COUNT:-1}" -a "$CODNA_API_APP" --yes

log "fly deploy complete (engine=$ENGINE_IMAGE api=$API_IMAGE)"
