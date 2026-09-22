#!/usr/bin/env bash
# Build Algenta kernel families for Linux inside a clean Ubuntu 22.04 container (glibc 2.35 floor)
# with the pinned Mojo toolchain, on any Docker host (Apple silicon builds linux/arm64 natively and
# linux/amd64 through Rosetta). The repository tree is exported without .git into a named volume,
# the pixi environment is installed for the container's own platform, and the staged closures land
# in --out on the host. Run from the repository root.
#
#   scripts/hf_kernels/linux_container_build.sh --arch arm64|amd64 --out <host dir> [--backend cpu|cuda] [--cuda-targets "sm_75 sm_80 sm_89 sm_90"] [--stage-tier default|6144|8192] <family> [<family> ...]
#
# --stage-tier (or the STAGE_TIER environment variable) is the resident decode staging tier of a CUDA build
# (build_hf_kernel_family.py --stage-tier: a compile-time presence flag, one binary per tier); the published
# algenta-llm GPU variants are built at 6144 (Qwen3-1.7B). It is forwarded to every family build of the run.
set -euo pipefail
ARCH=""; OUT=""; BACKEND="cpu"; CUDA_TARGETS="${CUDA_TARGETS:-sm_75 sm_80 sm_89 sm_90}"; STAGE_TIER="${STAGE_TIER:-default}"; FAMILIES=()
# patchelf: the retag (SONAME / DT_NEEDED / RUNPATH=$ORIGIN) must never run with ubuntu:22.04's apt package
# (0.14.3). When a rewrite has to grow a segment it leaves a zero-size PT_LOAD whose address and offset differ
# by a non-page multiple, and glibc refuses the library on every real Linux host ("ELF load command
# address/offset not page-aligned") -- the 2026-09-22 algenta-llm x86_64 defect, invisible on macOS and in the
# arm64 builds. The pinned PyPI build (manylinux wheel of upstream 0.19.1) is installed into /usr/local/bin,
# which precedes /usr/bin on the image's PATH, and its exact version is gated inside the container; the family
# build then refuses any artifact whose program headers are misaligned (scripts/hf_kernels/elf_check.py).
PATCHELF_PIN="${PATCHELF_PIN:-patchelf==0.19.1.0}"
while [ $# -gt 0 ]; do
  case "$1" in
    --arch) ARCH="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --backend) BACKEND="$2"; shift 2 ;;
    --cuda-targets) CUDA_TARGETS="$2"; shift 2 ;;
    --stage-tier) STAGE_TIER="$2"; shift 2 ;;
    *) FAMILIES+=("$1"); shift ;;
  esac
done
[ -n "$ARCH" ] && [ -n "$OUT" ] && [ "${#FAMILIES[@]}" -gt 0 ] || { echo "usage: $0 --arch arm64|amd64 --out DIR [--backend cpu|cuda] [--cuda-targets \"sm_75 ...\"] [--stage-tier default|6144|8192] FAMILY..." >&2; exit 2; }
case "$STAGE_TIER" in default|6144|8192) ;; *) echo "--stage-tier must be default, 6144 or 8192; got $STAGE_TIER" >&2; exit 2 ;; esac
case "$OUT" in /Users/*|/home/*|/tmp/*) ;; *) echo "--out must be under a directory Docker shares with containers (/Users, /home or /tmp); got $OUT" >&2; exit 2 ;; esac
# NOTE: the list above is only a sanity check — the path must actually be in Docker Desktop's file-sharing
# list. On some installs /tmp and /private/tmp mount as EMPTY directories (writes vanish with the
# container while the build still reports success); /Users always works. The guard at the end of this
# script fails loudly if nothing landed in --out.
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
  -e STAGE_TIER="$STAGE_TIER" -e FAMILIES="${FAMILIES[*]}" -e PATCHELF_PIN="$PATCHELF_PIN" \
  "$IMAGE" bash -euo pipefail -c '
    python3 -m pip install --quiet --disable-pip-version-check --no-cache-dir "$PATCHELF_PIN"
    hash -r
    want="${PATCHELF_PIN##*==}"; want="${want%.*}"   # PyPI 0.19.1.0 wraps upstream patchelf 0.19.1
    have="$(patchelf --version)"
    echo "patchelf: $have at $(command -v patchelf) (pinned $PATCHELF_PIN; apt ships $(dpkg-query -W patchelf 2>/dev/null | cut -f2))"
    [ "$have" = "patchelf $want" ] || { echo "FATAL: patchelf $want must win on PATH, got: $have" >&2; exit 4; }
    cd /work/mojo_env && pixi install --locked 2>&1 | tail -3
    PY=/work/mojo_env/.pixi/envs/default/bin/python3
    # sed, never "| head -1": ldd is a bash script, and head closing the pipe early kills it with SIGPIPE
    # (exit 141) under pipefail -- the "container died silently after the toolchain install" failures.
    "$PY" --version; uname -m; ldd --version | sed -n 1p
    cd /work
    for fam in $FAMILIES; do
      echo "=== build $fam ($BACKEND, stage tier $STAGE_TIER) on $(uname -m)"
      extra=""; [ "$BACKEND" = cuda ] && extra="--cuda-targets $CUDA_TARGETS"
      "$PY" scripts/build_hf_kernel_family.py --family "$fam" --backend "$BACKEND" $extra --stage-tier "$STAGE_TIER" --out "/out/${fam}_${BACKEND}" 2>&1 | tail -15
    done
    ls -la /out
  '

# Fail loudly if the bind mount silently dropped the artifacts (unshared host path).
[ -n "$(ls -A "$OUT" 2>/dev/null)" ] || { echo "ERROR: the build reported success but NOTHING landed in $OUT — that host path is not shared with Docker Desktop (use a /Users path)" >&2; exit 3; }
echo "artifacts on host: $(find "$OUT" -name 'libalgenta_*' -type f | wc -l | tr -d ' ') family librar(ies) under $OUT"
