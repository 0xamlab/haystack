#!/usr/bin/env bash
# Build Algenta kernel families for Linux inside a clean Ubuntu 22.04 container (glibc 2.35 floor)
# with the pinned Mojo toolchain, on any Docker host (Apple silicon builds linux/arm64 natively and
# linux/amd64 through Rosetta). The repository tree is exported without .git into a named volume,
# the pixi environment is installed for the container's own platform, and the staged closures land
# in --out on the host. Run from the repository root.
#
#   scripts/hf_kernels/linux_container_build.sh --arch arm64|amd64 --out <host dir> [--backend cpu|cuda] [--cuda-targets "sm_75 sm_80 sm_89 sm_90"] <family> [<family> ...]
set -euo pipefail
ARCH=""; OUT=""; BACKEND="cpu"; CUDA_TARGETS="${CUDA_TARGETS:-sm_75 sm_80 sm_89 sm_90}"; FAMILIES=()
while [ $# -gt 0 ]; do
  case "$1" in
    --arch) ARCH="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --backend) BACKEND="$2"; shift 2 ;;
    --cuda-targets) CUDA_TARGETS="$2"; shift 2 ;;
    *) FAMILIES+=("$1"); shift ;;
  esac
done
[ -n "$ARCH" ] && [ -n "$OUT" ] && [ "${#FAMILIES[@]}" -gt 0 ] || { echo "usage: $0 --arch arm64|amd64 --out DIR [--backend cpu|cuda] FAMILY..." >&2; exit 2; }
case "$OUT" in /Users/*|/home/*|/tmp/*) ;; *) echo "--out must be under a directory Docker shares with containers (/Users, /home or /tmp); got $OUT" >&2; exit 2 ;; esac
IMAGE="algenta-hfk-builder:${ARCH}"
PLATFORM="linux/${ARCH}"
SRC_VOL="hfk-src-${ARCH}"
CACHE_VOL="hfk-pixi-cache-${ARCH}"
COMMIT="$(git rev-parse HEAD)"
DIRTY=0; [ -z "$(git status --porcelain --untracked-files=no)" ] || DIRTY=1
mkdir -p "$OUT"
docker volume create "$SRC_VOL" >/dev/null
docker volume create "$CACHE_VOL" >/dev/null
# Export exactly what a family build reads (never .git, the host's pixi env, or data directories).
# Refresh the exported tree but keep the installed pixi environment between runs.
docker run --rm --platform "$PLATFORM" -v "$SRC_VOL":/work "$IMAGE" sh -c 'find /work -mindepth 1 -maxdepth 1 ! -name mojo_env -exec rm -rf {} + 2>/dev/null; find /work/mojo_env -mindepth 1 -maxdepth 1 ! -name .pixi -exec rm -rf {} + 2>/dev/null; true'
tar --exclude='*/__pycache__' -cf - mojo scripts packages/algenta mojo_env/pixi.toml mojo_env/pixi.lock LICENSE apps/runtime apps/__init__.py \
    mma_forge/generated attention_forge/generated tests/test_hf_kernel_package.py pyproject.toml \
  | docker run --rm -i --platform "$PLATFORM" -v "$SRC_VOL":/work "$IMAGE" tar -xf - -C /work
docker run --rm --platform "$PLATFORM" \
  -v "$SRC_VOL":/work -v "$CACHE_VOL":/root/.cache/rattler -v "$OUT":/out \
  -e ALGENTA_SOURCE_COMMIT="$COMMIT" -e ALGENTA_SOURCE_DIRTY="$DIRTY" -e BACKEND="$BACKEND" -e CUDA_TARGETS="$CUDA_TARGETS" \
  -e FAMILIES="${FAMILIES[*]}" \
  "$IMAGE" bash -euo pipefail -c '
    cd /work/mojo_env && pixi install --locked 2>&1 | tail -3
    PY=/work/mojo_env/.pixi/envs/default/bin/python3
    "$PY" --version; uname -m; ldd --version | head -1
    cd /work
    for fam in $FAMILIES; do
      echo "=== build $fam ($BACKEND) on $(uname -m)"
      extra=""; [ "$BACKEND" = cuda ] && extra="--cuda-targets $CUDA_TARGETS"
      "$PY" scripts/build_hf_kernel_family.py --family "$fam" --backend "$BACKEND" $extra --out "/out/${fam}_${BACKEND}" 2>&1 | tail -15
    done
    ls -la /out
  '
