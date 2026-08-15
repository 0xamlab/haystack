#!/usr/bin/env bash
# The ENTIRE linux-x86_64 leg of build-runtime.yml, executed inside an amd64 ubuntu:22.04
# container on the self-hosted macOS fleet (job `build-linux` mounts $GITHUB_WORKSPACE at /work).
# Replaces the GitHub-hosted `ubuntu-22.04` leg, which is billing-blocked; every step mirrors the
# hosted pipeline 1:1 so the shipped wheel is byte-for-byte the same contract:
#   contract check -> pixi/mojo env -> shard compile (mcpu x86-64-v3, no Metal) -> stage ->
#   strip -> signed manifest -> wheel -> manylinux_2_35 audit + retag.
# The hosted leg's swap-provisioning step is deliberately NOT reproduced: it existed because the
# hosted VM has 7.8 GiB RAM; this fleet's machines carry far more, so the shard compiler gets a
# generous fixed RSS ceiling instead (SHARD_MAX_RSS_MB).
set -euo pipefail
cd /work

# shellcheck source=_linux_container_bootstrap.sh
source "$(dirname "$0")/_linux_container_bootstrap.sh"

# ── Verify generated public runtime contract ─────────────────────────────────────────────────
python3 scripts/generate_algenta_runtime_contract.py --check

# ── Pixi + Mojo environment (mirrors the hosted steps' env exactly) ─────────────────────────
export PIXI_HOME=/work/.pixi
export RATTLER_CACHE_DIR=/work/.cache/rattler/cache
curl -fsSL https://pixi.sh/install.sh | env PIXI_HOME="$PIXI_HOME" PIXI_BIN_DIR="$PIXI_HOME/bin" PIXI_NO_PATH_UPDATE=1 bash
export PATH="$PIXI_HOME/bin:$PATH"
pixi install --manifest-path mojo_env/pixi.toml

# ── Compile bounded runtime worker shards ────────────────────────────────────────────────────
# Emulation runs slower than native x86_64, so the caller passes an enlarged per-shard timeout;
# the RSS ceiling stays generous (fleet RAM >> the compiler's ~11.3 GiB peak). mcpu/metal mirror
# the hosted matrix values for the linux leg exactly (x86-64-v3 binaries, no Metal).
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

# ── Strip staged runtime artifacts (linux branch of the hosted step) ────────────────────────
cd /work/mojo_build/runtime-wheel
for artifact in *; do
  [ -f "$artifact" ] || continue
  strip --strip-unneeded "$artifact" 2>/dev/null || true
done

# ── Build + sign runtime manifest (verbatim logic of the hosted step) ───────────────────────
python3 - linux-x86_64 > manifest.json <<'PY'
import hashlib
import json
import sys
from pathlib import Path

platform = sys.argv[1]
artifacts = []
for path in sorted(Path('.').iterdir(), key=lambda p: p.name):
    if not path.is_file() or path.name in {'manifest.json', 'manifest.sig', 'algenta_release_pub.pem'}:
        continue
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    artifacts.append({'name': path.name, 'sha256': digest, 'size_bytes': path.stat().st_size})
names = {item['name'] for item in artifacts}
workers = {name for name in names if name == 'algenta-runtime-worker' or name.startswith('algenta-runtime-worker-')}
if 'algenta-runtime-worker' not in workers or len(workers) < 2:
    raise SystemExit('bounded runtime worker shards missing from staged artifacts')
if 'runtime-shards.json' not in names:
    raise SystemExit('runtime-shards.json missing from staged artifacts')
payload = {'format_version': 1, 'platform': platform, 'artifacts': artifacts}
sys.stdout.write(json.dumps(payload, sort_keys=True, separators=(',', ':')))
PY
if [ -z "${ALGENTA_SIGNING_KEY:-}" ]; then
  if [[ "${RUNTIME_RELEASE_PUBLISH:-false}" == "true" ]]; then
    echo "::error::ALGENTA_SIGNING_KEY is unset for a release publish; refusing to emit a runtime signed by an ephemeral key."
    exit 1
  fi
  echo "::warning::ALGENTA_SIGNING_KEY unset on a non-publishing build; generating an ephemeral CI-only signing key."
  KEYFILE="$(mktemp)"
  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$KEYFILE"
else
  umask 077
  KEYFILE="$(mktemp)"
  printf '%s' "$ALGENTA_SIGNING_KEY" > "$KEYFILE"
fi
trap 'rm -f "$KEYFILE"' EXIT
openssl pkey -in "$KEYFILE" -pubout -out algenta_release_pub.pem
TRUSTED_PUB="/work/packages/algenta/algenta/_keys/algenta_release_pub.pem"
if [ -n "${ALGENTA_SIGNING_KEY:-}" ] && ! cmp -s algenta_release_pub.pem "$TRUSTED_PUB"; then
  echo "::error::ALGENTA_SIGNING_KEY does not match the embedded runtime release trust anchor."
  exit 1
fi
openssl dgst -sha256 -sign "$KEYFILE" -out manifest.sig manifest.json
cd /work

# ── Build platform runtime wheel ─────────────────────────────────────────────────────────────
uv pip install --python /usr/local/bin/python3 --quiet build
python3 -P -m build --wheel packages/algenta-runtime-native --outdir /work/dist-runtime

# ── Verify manylinux compatibility + retag the Linux wheel (verbatim logic of the hosted step) ─
uv pip install --python /usr/local/bin/python3 --quiet auditwheel wheel
auditwheel show /work/dist-runtime/*.whl | grep -q 'manylinux_2_35_x86_64'
# PyPI rejects the raw linux_x86_64 tag (400 on upload). auditwheel show just proved the wheel is
# manylinux_2_35-clean -- staging already bundles the full library closure -- so RETAG without
# touching the binaries: auditwheel repair rewrites rpaths, changing bytes the signed manifest
# hashes, and the runtime verifier fails closed on any mismatch (run 31027593726 caught exactly
# that).
cd /work/dist-runtime
original=$(ls ./*.whl)
python3 -m wheel tags --platform-tag manylinux_2_35_x86_64 "$original"
rm "$original"
ls -la /work/dist-runtime/

# The container ran as root on the mounted runner workspace; hand the produced trees back to the
# workspace owner so later runner-side steps (artifact upload, the NEXT job's checkout/cleanup)
# are not locked out by root-owned files.
OWNER="$(stat -c '%u:%g' /work/.git)"
chown -R "$OWNER" /work/mojo_build /work/dist-runtime /work/.pixi /work/.cache 2>/dev/null || true
echo "linux-x86_64 runtime build OK"
