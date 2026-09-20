#!/usr/bin/env bash
# Gate a BUILT container image on the absence of the HS256 dev-licence secret (secret-scanning #14).
#
# Exports the image's filesystem (docker create + docker export; no process in the image is started)
# and streams it through scripts/verify_no_dev_secret.py, which fails if the dev stub, the strip tool
# or any byte-level copy of the secret is present. The needle itself is never printed.
#
#   bash scripts/verify_no_dev_secret.sh <image-ref>
#
# Exit 0 = clean; 1 = the artifact is NOT hardened (findings on stderr); 64 = usage.
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: scripts/verify_no_dev_secret.sh <image-ref>" >&2
  exit 64
fi

image="$1"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Production images are linux/amd64 (the Fly target); pin the platform so an arm64 host inspects
# the image that ships, not a host-arch variant.
platform="${VERIFY_NO_DEV_SECRET_PLATFORM:-linux/amd64}"

container="$(docker create --platform "$platform" "$image")"
trap 'docker rm -v "$container" >/dev/null 2>&1 || true' EXIT

docker export "$container" | python3 "$here/verify_no_dev_secret.py" --tar - --label "$image"
