#!/usr/bin/env bash
# The linux-x64 leg of build-runtime-bundle.yml, executed inside an ubuntu:22.04 container
# (the job mounts $GITHUB_WORKSPACE at /work).
# Mirrors .github/scripts/build_runtime_linux_amd64.sh (the wheel pipeline's linux leg)
# through the shard compile + staging, then diverges: instead of building a wheel it
# freezes the runtime daemon with PyInstaller and packs the signed managed-runtime
# bundle (scripts/build_runtime_bundle.py).
#
# OS baseline: the daemon binary is PyInstaller-built ON ubuntu:22.04, so its floor is
# ubuntu:22.04's glibc (2.35) — the workflow's acceptance gate re-runs the built bundle
# inside a CLEAN ubuntu:22.04 container to prove it.
#
# Signing: ALGENTA_BUNDLE_SIGNING_PRIVATE_KEY is passed through from the job env (repo
# secret). Without it, build_runtime_bundle.py falls back to a LOUDLY-flagged dev keypair
# (fork/dry-run only — a tag cut with the dev key would fail the SQAI trust root).
set -euo pipefail
cd /work

# shellcheck source=_linux_container_bootstrap.sh
source "$(dirname "$0")/_linux_container_bootstrap.sh"

# ── Pixi + Mojo environment (mirrors build_runtime_linux_amd64.sh exactly) ──────────────────
export PIXI_HOME=/work/.pixi
export RATTLER_CACHE_DIR=/work/.cache/rattler/cache
curl -fsSL https://pixi.sh/install.sh | env PIXI_HOME="$PIXI_HOME" PIXI_BIN_DIR="$PIXI_HOME/bin" PIXI_NO_PATH_UPDATE=1 bash
export PATH="$PIXI_HOME/bin:$PATH"
pixi install --manifest-path mojo_env/pixi.toml

# ── Compile bounded runtime worker shards (full catalog, portable x86-64-v3, no Metal) ─────
export MOJO_BUILD_MCPU=x86-64-v3
export MOJO_BUILD_METAL_GPU=0
python3 scripts/build_runtime_shards.py \
  --out /work/mojo_build/runtime-shards \
  --shard-size 24 \
  --timeout-seconds "${SHARD_TIMEOUT:-2700}" \
  --max-rss-mb "${SHARD_MAX_RSS_MB:-32768}"

# ── Stage self-contained runtime package ─────────────────────────────────────────────────────
python3 scripts/stage_runtime_worker_package.py \
  --worker-dir /work/mojo_build/runtime-shards \
  --shard-map /work/mojo_build/runtime-shards/runtime-shards.json \
  --lib-root /work/mojo_env/.pixi/envs/default/lib \
  --out /work/mojo_build/runtime-wheel \
  --platform linux

# ── Strip staged runtime artifacts (linux branch of build-runtime's hosted step) ────────────
cd /work/mojo_build/runtime-wheel
for artifact in *; do
  [ -f "$artifact" ] || continue
  strip --strip-unneeded "$artifact" 2>/dev/null || true
done
cd /work

# ── Daemon deps + PyInstaller (the frozen daemon's third-party closure) ─────────────────────
# scripts/runtime_bundle.spec: structlog, grpcio, protobuf, PyJWT, cryptography, pydantic +
# pydantic_settings (the AuthContext chain). apps.api_server's FastAPI/SQLAlchemy stack stays
# excluded from the bundle.
uv pip install --python /usr/local/bin/python3 --quiet \
  pyinstaller structlog grpcio protobuf PyJWT cryptography pydantic pydantic_settings
python3 -m PyInstaller --version

# ── Build the signed bundle (dev-key fallback is loudly flagged; never for a tag cut) ───────
python3 scripts/build_runtime_bundle.py \
  --version "${BUNDLE_VERSION:?BUNDLE_VERSION must be set}" \
  --output-dir /work/dist/runtime-bundle

# ── Verify bundle (reference verifier) ───────────────────────────────────────────────────────
python3 scripts/verify_runtime_bundle.py \
  /work/dist/runtime-bundle/algenta-runtime-*-linux-x64.tar.gz \
  --public-key /work/dist/runtime-bundle/bundle-signing-public.pem

# The container ran as root on the mounted runner workspace; hand the produced trees back to
# the workspace owner so the runner-side steps (the metadata `cp` INTO dist/runtime-bundle and
# the artifact upload, both as a non-root user) are not locked out by root-owned files.
OWNER="$(stat -c '%u:%g' /work/.git)"
chown -R "$OWNER" /work/mojo_build /work/dist /work/.pixi /work/.cache 2>/dev/null || true
echo "linux-x64 runtime bundle built + verified"
