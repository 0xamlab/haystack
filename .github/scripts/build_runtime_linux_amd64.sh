#!/usr/bin/env bash
# The ENTIRE linux-x86_64 leg of build-runtime.yml, executed inside an ubuntu:22.04 container
# (job `build-linux` mounts $GITHUB_WORKSPACE at /work). The pipeline is the same contract the
# wheel has always shipped under:
#   contract check -> pixi/mojo env -> shard compile (mcpu x86-64-v3, no Metal) -> stage ->
#   strip -> signed manifest -> wheel -> manylinux_2_35 audit + retag.
# No swap-provisioning step: the runner (thyn-8c, 32 GB) carries far more RAM than the measured
# 1.2-1.8 GiB per-shard peaks, so the shard compiler gets a generous fixed RSS ceiling instead
# (SHARD_MAX_RSS_MB).
#
# BUILD_VARIANT selects the accelerator tier of the compiled shards:
#   cpu  (default) — portable build, no GPU defines, exactly the historical behaviour.
#   cuda           — `-D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_90` through
#                    scripts/build_mojo_binary.sh's CUDA knob: the portable GPU kernels compile
#                    for NVIDIA hardware while metaldispatch's Metal shim machinery stays
#                    compiled out. COMPILE-GATED lane: cross-compilation needs no CUDA toolkit
#                    and no GPU (the NVPTX backend ships inside the pinned toolchain), but the
#                    result is launch-UNVERIFIED — actually running it needs an NVIDIA driver
#                    >= 580 and real hardware. The cuda wheel is therefore an artifact of the
#                    compile gate only; it is not in publish-pypi's dependency chain.
#
#                    The cuda variant ALSO bundles the engine binary that
#                    .github/scripts/build_cuda_engine_linux_amd64.sh compiled in the step before
#                    this one (mojo_build/cuda-engine/), and RECORDS the variant in the signed
#                    manifest as `build_variant` so a CPU-built worker and a CUDA-built worker are
#                    distinguishable once unpacked — they are otherwise identical in name, layout
#                    and wheel filename. A cuda build with no engine build fails closed below rather
#                    than signing another kernel-free wheel.
set -euo pipefail
cd /work

BUILD_VARIANT="${BUILD_VARIANT:-cpu}"
case "${BUILD_VARIANT}" in
    cpu | cuda) ;;
    *)
        echo "::error::unknown BUILD_VARIANT '${BUILD_VARIANT}' (expected 'cpu' or 'cuda')" >&2
        exit 1
        ;;
esac
echo "linux-x86_64 runtime build: BUILD_VARIANT=${BUILD_VARIANT}"

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
# The caller passes the per-shard timeout and RSS ceiling (SHARD_TIMEOUT / SHARD_MAX_RSS_MB);
# the ceiling stays generous next to the measured 1.2-1.8 GiB per-shard peaks. mcpu/metal are
# the linux leg's fixed values (x86-64-v3 binaries, no Metal).
export MOJO_BUILD_MCPU=x86-64-v3
export MOJO_BUILD_METAL_GPU=0
if [[ "${BUILD_VARIANT}" == "cuda" ]]; then
    # build_runtime_shards.py forwards the environment wholesale to build_mojo_binary.sh, so the
    # CUDA knob set here reaches every shard compile: portable GPU kernels in for sm_90, Metal
    # shim machinery out (no ALGENTA_METAL), no CUDA toolkit or GPU on this builder.
    export MOJO_BUILD_CUDA_GPU=1
    export MOJO_BUILD_CUDA_TARGET="${MOJO_BUILD_CUDA_TARGET:-sm_90}"
fi
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

# ── Bundle the CUDA engine binary (cuda variant ONLY) ───────────────────────────────────────────
# WHY THIS EXISTS. The wheel this script signs carries only the 643 public JSON-callable `modules`
# shards. Every racing kernel is a private leading-underscore symbol (the #854 directive), and
# discover_runtime_library_modules(executable_only=True) drops all 20 kernel-bearing residentk
# modules because a module with no public executable function has nothing to dispatch. So a user who
# installs the cuda wheel gets ZERO of the 142 declared CUDA kernels — by design, and no shard re-pin
# can change it. The engine binary built by build_cuda_engine_linux_amd64.sh is the artifact that
# carries them: a linked executable with the kernels compiled in as device images, shipped WITHOUT
# making a single one of them JSON-callable. It is an artifact in the signed manifest, never a module
# in runtime_library_contract.json (which this script checks is unchanged, above).
#
# It lands in the staged directory BEFORE the strip and the manifest, so it is stripped, hashed and
# signed exactly like the workers, and the wheel's hatch build hook force-includes every manifest
# artifact into algenta_runtime_native/ — the directory `algenta serve`'s resolver already searches
# for a binary named `conform_generate_cuda` (packages/algenta/algenta/serve/engine.py).
ENGINE_BUILD_JSON=""
if [[ "${BUILD_VARIANT}" == "cuda" ]]; then
    ENGINE_DIR=/work/mojo_build/cuda-engine
    ENGINE_BUILD_JSON="$ENGINE_DIR/engine-build.json"
    if [[ ! -f "$ENGINE_BUILD_JSON" ]]; then
        # FAIL CLOSED, loudly. A cuda wheel without the engine is exactly the kernel-free wheel this
        # step exists to stop shipping, and it is indistinguishable from the real one by filename.
        echo "::error::BUILD_VARIANT=cuda but $ENGINE_BUILD_JSON is missing — the CUDA engine"
        echo "::error::compile gate (.github/scripts/build_cuda_engine_linux_amd64.sh) did not run"
        echo "::error::or did not produce an engine. Refusing to sign a kernel-free cuda wheel."
        exit 1
    fi
    ENGINE_NAME="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["name"])' "$ENGINE_BUILD_JSON")"
    if [[ ! -x "$ENGINE_DIR/$ENGINE_NAME" ]]; then
        echo "::error::the engine build sidecar names $ENGINE_NAME but $ENGINE_DIR/$ENGINE_NAME is absent" >&2
        exit 1
    fi
    # The engine's own $ORIGIN rpath means its bundled libraries must sit beside it, which in the
    # wheel means beside the workers in the staged directory.
    cp "$ENGINE_DIR/$ENGINE_NAME" "/work/mojo_build/runtime-wheel/$ENGINE_NAME"
    chmod 0755 "/work/mojo_build/runtime-wheel/$ENGINE_NAME"
    for bundled_lib in "$ENGINE_DIR"/lib*.so*; do
        [[ -e "$bundled_lib" ]] || continue
        cp -L "$bundled_lib" "/work/mojo_build/runtime-wheel/$(basename "$bundled_lib")"
    done
    echo "bundled CUDA engine: $ENGINE_NAME (+ $(ls -1 "$ENGINE_DIR"/lib*.so* 2>/dev/null | wc -l) libraries)"
fi

# ── Strip staged runtime artifacts (linux branch of the hosted step) ────────────────────────
cd /work/mojo_build/runtime-wheel
for artifact in *; do
  [ -f "$artifact" ] || continue
  strip --strip-unneeded "$artifact" 2>/dev/null || true
done

# ── Build + sign runtime manifest ─────────────────────────────────────────────────────────────
# The payload is generated by scripts/generate_runtime_bundle_manifest.py (it was an inline heredoc
# here until the manifest grew a build_variant and an engine block) so that its schema is asserted by
# tests/test_runtime_bundle_manifest_variant.py on a machine with no GPU, no CUDA toolkit and no Linux.
MANIFEST_ARGS=(
  --artifact-dir /work/mojo_build/runtime-wheel
  --platform linux-x86_64
  --build-variant "${BUILD_VARIANT}"
  --output /work/mojo_build/runtime-wheel/manifest.json
)
if [[ -n "$ENGINE_BUILD_JSON" ]]; then
    # The comptime define stack and the host shared libraries come from the build that actually
    # happened (the sidecar), not from a list restated here: a manifest that declares a configuration
    # the binary was not built with is worse than no manifest.
    while IFS= read -r arg; do
        MANIFEST_ARGS+=("$arg")
    done < <(python3 - "$ENGINE_BUILD_JSON" <<'PY'
import json
import sys

build = json.load(open(sys.argv[1], encoding="utf-8"))
print("--engine")
print(build["name"])
print("--engine-source")
print(build["source"])
print("--cuda-target")
print(build["cuda_target"])
if build.get("shim_object_sha256"):
    print("--engine-shim-object")
    print("tc_shim.cu@%s sha256:%s" % (build["cuda_target"], build["shim_object_sha256"][:16]))
for define in build["comptime_defines"]:
    print("--comptime-define")
    print(define)
for library in build["host_shared_libraries"]:
    print("--host-shared-library")
    print(library)
PY
    )
fi
cd /work
python3 scripts/generate_runtime_bundle_manifest.py "${MANIFEST_ARGS[@]}"
cd /work/mojo_build/runtime-wheel

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
# The wheel's hatch build hook refuses an empty wheel unless these point at the staged+signed
# artifacts (the hosted workflow set them as step `env:`; here they are exported inline).
export ALGENTA_BUNDLE_RUNTIME=1
export ALGENTA_RUNTIME_SRC=/work/mojo_build/runtime-wheel
uv pip install --python /usr/local/bin/python3 --quiet build
python3 -P -m build --wheel packages/algenta-runtime-native --outdir /work/dist-runtime

# ── Verify manylinux compatibility + retag the Linux wheel (verbatim logic of the hosted step) ─
uv pip install --python /usr/local/bin/python3 --quiet auditwheel wheel
AUDIT_SHOW="$(auditwheel show /work/dist-runtime/*.whl 2>&1)" || true
echo "$AUDIT_SHOW"
if [[ "${BUILD_VARIANT}" == "cpu" ]]; then
  # The historical assertion, byte for byte: the shippable wheel must be manylinux_2_35 with no
  # exceptions of any kind. Nothing about the cpu path changed in this refactor.
  echo "$AUDIT_SHOW" | grep -q 'manylinux_2_35_x86_64'
else
  # THE CUDA VARIANT'S ABI GATE, AND WHY IT IS NOT THE SAME LINE.
  #
  # The bundled engine links the tensor-core shim, which calls cuBLAS directly, so the binary carries
  # DT_NEEDED libcublas.so.12 (+ its own libcublasLt.so.12). cuBLAS is in NO manylinux allowlist, so a
  # plain `auditwheel show` downgrades the whole wheel to linux_x86_64 — and PyPI rejects that tag. It
  # cannot be bundled either: nvidia-cublas-cu12 is 581,240,110 bytes for linux x86_64 against a 42 MB
  # wheel. So cuBLAS is host-provided, exactly as libcuda.so.1 already is (the shim dlopens it), and it
  # is DECLARED as such in the signed manifest's engine.host_shared_libraries.
  #
  # This gate is the fail-closed half of that declaration. `auditwheel repair --exclude` on a THROWAWAY
  # COPY computes the wheel's policy while treating precisely the declared libraries as intentionally
  # external; if the produced wheel is not manylinux_2_35_x86_64 then something OTHER than the declared
  # host libraries is unresolved, and the build dies here. The copy is discarded: the shipped wheel's
  # bytes are never touched, because repair rewrites rpaths and the signed manifest hashes what it
  # signed (run 31027593726 caught exactly that). The exclude list is DERIVED from the engine build's
  # own sidecar, not restated here, so a new external dependency cannot slip in silently.
  EXCLUDE_ARGS=()
  while IFS= read -r host_lib; do
    [[ -n "$host_lib" ]] && EXCLUDE_ARGS+=(--exclude "$host_lib")
  done < <(python3 -c '
import json, sys
build = json.load(open(sys.argv[1], encoding="utf-8"))
print("\n".join(build["host_shared_libraries"]))
' "$ENGINE_BUILD_JSON")
  if [[ "${#EXCLUDE_ARGS[@]}" -eq 0 ]]; then
    echo "::error::the cuda engine declared no host shared libraries; refusing to audit the wheel"
    echo "::error::against an empty exclude list (that would silently bless any external dependency)."
    exit 1
  fi
  echo "cuda ABI gate: declared host libraries -> ${EXCLUDE_ARGS[*]}"
  rm -rf /work/mojo_build/abi-probe
  auditwheel repair "${EXCLUDE_ARGS[@]}" -w /work/mojo_build/abi-probe /work/dist-runtime/*.whl
  if ! ls /work/mojo_build/abi-probe/*manylinux_2_35_x86_64.whl >/dev/null 2>&1; then
    echo "::error::the cuda wheel is not manylinux_2_35 once the DECLARED host libraries"
    echo "::error::(${EXCLUDE_ARGS[*]}) are excluded — something else in it is unresolved."
    ls -la /work/mojo_build/abi-probe/ || true
    exit 1
  fi
  rm -rf /work/mojo_build/abi-probe
fi
# PyPI rejects the raw linux_x86_64 tag (400 on upload). auditwheel just proved the wheel is
# manylinux_2_35-clean -- staging already bundles the full library closure, and the cuda variant's
# only external libraries are the ones its signed manifest declares -- so RETAG without
# touching the binaries: auditwheel repair rewrites rpaths, changing bytes the signed manifest
# hashes, and the runtime verifier fails closed on any mismatch (run 31027593726 caught exactly
# that).
cd /work/dist-runtime
original=$(ls ./*.whl)
python3 -m wheel tags --platform-tag manylinux_2_35_x86_64 "$original"
rm "$original"
ls -la /work/dist-runtime/

# The container ran as root on the mounted runner workspace, and `umask 077` above makes the
# wheel root-owned 0600 inside a 0700 dist-runtime/; hand the produced trees back to the
# workspace owner so the runner-side artifact upload (a non-root user) can read them.
OWNER="$(stat -c '%u:%g' /work/.git)"
chown -R "$OWNER" /work/mojo_build /work/dist-runtime /work/.pixi /work/.cache 2>/dev/null || true
echo "linux-x86_64 runtime build OK (${BUILD_VARIANT} variant)"
