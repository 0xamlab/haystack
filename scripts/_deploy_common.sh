#!/usr/bin/env bash
# Shared config + helpers for the codna Fly/Cloudflare deploy scripts.
# Override any value via the environment or a local (gitignored) scripts/.deploy.env.
set -euo pipefail

_here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_repo_root="$(cd "${_here}/.." && pwd)"
[ -f "${_here}/.deploy.env" ] && set -a && . "${_here}/.deploy.env" && set +a
# Source the repo .env if present (gitignored), so FLY_IO_TOKEN / CLOUDFLARE_API_TOKEN etc. are picked up.
[ -f "${_repo_root}/.env" ] && set -a && . "${_repo_root}/.env" && set +a
# flyctl reads FLY_API_TOKEN; accept the repo's FLY_IO_TOKEN name too.
export FLY_API_TOKEN="${FLY_API_TOKEN:-${FLY_IO_TOKEN:-}}"
# OpenTofu reads TF_VAR_cloudflare_api_token; map from the repo's CLOUDFLARE_API_TOKEN if set.
export TF_VAR_cloudflare_api_token="${TF_VAR_cloudflare_api_token:-${CLOUDFLARE_API_TOKEN:-}}"

# ── App + registry config ────────────────────────────────────────────────────
CODNA_API_APP="${CODNA_API_APP:-codna-api}"
CODNA_ENGINE_APP="${CODNA_ENGINE_APP:-codna-engine}"
FLY_REGION="${FLY_REGION:-iad}"
IMAGE_REPO="${IMAGE_REPO:-ghcr.io/thyn-ai/algenta}"
ENGINE_VOLUME="${ENGINE_VOLUME:-codna_engine_data}"
ENGINE_VOLUME_SIZE_GB="${ENGINE_VOLUME_SIZE_GB:-10}"
API_HOSTNAME="${API_HOSTNAME:-api.codna.ai}"

die() { echo "error: $*" >&2; exit 1; }
log() { echo "▸ $*" >&2; }

need() { command -v "$1" >/dev/null 2>&1 || die "missing required tool: $1"; }

# `fly` with the token from the environment (FLY_API_TOKEN). Never echo the token.
fly() { command flyctl "$@"; }

fly_app_exists() { fly apps list 2>/dev/null | awk '{print $1}' | grep -qx "$1"; }
