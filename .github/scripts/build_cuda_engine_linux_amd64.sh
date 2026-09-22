#!/usr/bin/env bash
# THE CUDA ENGINE COMPILE GATE — and the step that finally puts the racing kernels where a user can
# reach them. Runs inside an ubuntu:22.04 container on a GPU-LESS linux/amd64 runner (job
# `build-linux-cuda` in build-runtime.yml mounts $GITHUB_WORKSPACE at /work), BEFORE
# build_runtime_linux_amd64.sh stages and signs the wheel.
#
# WHAT IT BUILDS, AND WHY THOSE TWO THINGS.
#   (a) benchmarks/llm_smoke/nvidia_race/tc_shim.cu -> an sm_90a object, through the campaign's OWN
#       build script (build_shim_gemma3_round7.sh), so the shim in the wheel is produced by the same
#       recipe that produced the certified arms — not by a new one invented here.
#   (b) benchmarks/llm_smoke/conform_generate_cuda.mojo -> a standalone executable at the round-19
#       CERTIFIED default configuration (BASE + R5 + R6 comptime defines, GEGLU_V2 default-ON since
#       #1072 i.e. no opt-out passed, LTALGO default-OFF i.e. no opt-in passed and the STOCK shim).
#       This is the binary class `algenta serve --backend cuda` already resolves (#1112).
#
# WHY A GPU-LESS RUNNER CAN DO THIS. nvcc cross-compiles: it needs no device, only the toolkit. And
# `mojo build --target-accelerator sm_90a` emits PTX through the NVPTX backend that ships inside the
# pinned toolchain. Neither step queries a GPU. What a GPU-less runner CANNOT do is prove the result
# RUNS — that stays the October battery's job (scripts/release/verify_cuda_release.sh), which is why
# this lane remains a compile gate and the wheel still reaches PyPI only through the release-verify
# gate in publish-pypi.
#
# WHY THE ENGINE RIDES IN THE WHEEL AT ALL. The published cuda wheel bundles only the 643 public
# JSON-callable `modules` shards: every racing kernel is a private leading-underscore symbol (the
# #854 directive) and `discover_runtime_library_modules(executable_only=True)` drops the 20
# kernel-bearing residentk modules outright, because a function-less module has nothing to dispatch.
# So the wheel a user installs carries ZERO of the 142 declared CUDA kernels, by design, and no
# shard re-pin can change that. Bundling the ENGINE BINARY — a linked executable whose device images
# those kernels are compiled into — ships them without making a single one of them JSON-callable.
# The engine is an artifact in the signed manifest, never a module in runtime_library_contract.json.
#
# OUTPUT: /work/mojo_build/cuda-engine/{conform_generate_cuda, libcudart.so.12, engine-build.json}.
# build_runtime_linux_amd64.sh's cuda branch consumes that directory; a cuda build with no engine
# fails closed there rather than silently shipping a kernel-free wheel again.
set -euo pipefail
cd /work

# The round-19 certified default configuration, verbatim from
# benchmarks/llm_smoke/nvidia_race/run_ab_gemma3_round18.sh:165-169 (BASE + R5_STACK + R6_STACK).
# R19_def — the arm certified full-scope ALL_PASS at e4c6fbe26376f817 and published as pp256 1.44x /
# pp1024 1.25x — is this stack with NO opt-out, which is why no ALGENTA_G3_PF_NO_* define appears
# here. LTALGO is default-OFF and stays off: opting in needs -D ALGENTA_G3_PF_LTALGO *and* a shim
# object built with -D ALGENTA_TC_SHIM_LT, and the stock object deliberately has no tc_lt symbols.
#
# HONESTY NOTE, because a reviewer will ask: conform_generate_cuda.mojo composes
# residentk.session_cuda (the fact-driven Qwen3 resident session), so the ALGENTA_G3_* defines are
# INERT in this binary — they gate the gemma-3 session modules, which are not in its import closure.
# The defines that are LIVE here are ALGENTA_GPU, ALGENTA_CUDA, ALGENTA_STAGE_18944 and
# ALGENTA_TC_SHIM (tc_shim_bridge.TC_SHIM_BUILD), which is what pulls the tensor-core shim in. The
# full stack is passed anyway, verbatim, so this gate proves the certified configuration still
# compiles and links as a whole and cannot silently drift from it.
BASE_DEFINES=(ALGENTA_GPU ALGENTA_CUDA ALGENTA_STAGE_18944 ALGENTA_G3_GEGLU_U4
              ALGENTA_TC_SHIM ALGENTA_G3_ATTN_FLASH ALGENTA_G3_PF_TCATTN ALGENTA_G3_STREAM)
R5_DEFINES=(ALGENTA_G3_PF_FA ALGENTA_G3_PF_F16ATTN ALGENTA_G3_PF_F16NORM
            ALGENTA_G3_PF_F16MLP ALGENTA_G3_PF_ROPE2)
R6_DEFINES=(ALGENTA_G3_PF_FA2 ALGENTA_G3_PF_KV16 ALGENTA_G3_PF_BN32)
DEFINES=("${BASE_DEFINES[@]}" "${R5_DEFINES[@]}" "${R6_DEFINES[@]}")

ENGINE_SRC=benchmarks/llm_smoke/conform_generate_cuda.mojo
ENGINE_NAME=conform_generate_cuda
SHIM_SRC=benchmarks/llm_smoke/nvidia_race/tc_shim.cu
for required_source in "$ENGINE_SRC" "$SHIM_SRC" \
                       benchmarks/llm_smoke/nvidia_race/tc_rt_kernels.cu \
                       benchmarks/llm_smoke/nvidia_race/build_shim_gemma3_round7.sh; do
  if [ ! -f "/work/$required_source" ]; then
    echo "::error::the CUDA engine recipe needs $required_source, which is not in the checkout" >&2
    exit 1
  fi
done
# sm_90a, not sm_90: the arch-specific Hopper target. The shim's own inline PTX is Ampere-class
# (cp.async / ldmatrix / mma.sync.m16n8k16 — no wgmma, no TMA), so sm_90 would also compile; sm_90a
# is what the task specifies and what the certified arms' toolchain accepts.
CUDA_TARGET="${CUDA_TARGET:-sm_90a}"
CUDA_COMPUTE="${CUDA_COMPUTE:-compute_90}"
CUDA_TOOLKIT_SERIES="${CUDA_TOOLKIT_SERIES:-12-6}"
OUT_DIR=/work/mojo_build/cuda-engine
SHIM_DIR=/work/mojo_build/tc-shim-${CUDA_TARGET}

echo "cuda engine compile gate: target=${CUDA_TARGET} defines=${#DEFINES[@]}"

# shellcheck source=_linux_container_bootstrap.sh
source "$(dirname "$0")/_linux_container_bootstrap.sh"

# ── 1. A MINIMAL CUDA TOOLKIT: nvcc + the headers tc_shim.cu includes + the two link libraries ──
# Sub-packages, not `cuda-toolkit-12-6`: the full meta-package pulls nsight, the samples and the
# documentation for a job that needs a compiler and four headers. cuda-cudart-dev supplies
# cuda_runtime.h / cuda_fp16.h / mma.h, libcublas-dev supplies cublas_v2.h.
#
# tc_shim.cu's `#include <cublasLt.h>` sits inside `#ifdef ALGENTA_TC_SHIM_LT` (:4353-4354) and this
# build does NOT define it, so the stock object needs no cublasLt header — but libcublas.so.12 does
# DT_NEED libcublasLt.so.12 at load time, which is why both appear in the declared host libraries.
curl -fsSL "https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb" \
  -o /tmp/cuda-keyring.deb
dpkg -i /tmp/cuda-keyring.deb >/dev/null
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
  "cuda-nvcc-${CUDA_TOOLKIT_SERIES}" \
  "cuda-cudart-dev-${CUDA_TOOLKIT_SERIES}" \
  "libcublas-dev-${CUDA_TOOLKIT_SERIES}" >/dev/null

# `/usr/local/cuda` is owned by the cuda-toolkit-*-config-common packages, which a sub-package
# install does not necessarily pull — resolve the real prefix instead of assuming the symlink.
CUDA_HOME=""
for candidate in /usr/local/cuda-12.* /usr/local/cuda; do
  [ -x "${candidate}/bin/nvcc" ] && { CUDA_HOME="$candidate"; break; }
done
if [ -z "$CUDA_HOME" ]; then
  echo "::error::no nvcc after installing cuda-nvcc-${CUDA_TOOLKIT_SERIES}" >&2
  exit 1
fi
CUDA_LIBDIR="${CUDA_HOME}/lib64"
[ -d "$CUDA_LIBDIR" ] || CUDA_LIBDIR="${CUDA_HOME}/targets/x86_64-linux/lib"
export CUDA_HOME
echo "CUDA_HOME=${CUDA_HOME} CUDA_LIBDIR=${CUDA_LIBDIR}"
"${CUDA_HOME}/bin/nvcc" --version | tail -1
for header in cuda_runtime.h cuda_fp16.h mma.h cublas_v2.h; do
  if [ ! -e "${CUDA_HOME}/include/${header}" ]; then
    echo "::error::${header} is missing from the minimal CUDA toolkit install" >&2
    dpkg -S "${CUDA_HOME}/include/${header}" || true
    exit 1
  fi
done

# ── 2. Pixi + the pinned Mojo toolchain (same env the runtime leg uses; /work persists between the
#       two container runs, so whichever runs second is a fast no-op) ─────────────────────────────
export PIXI_HOME=/work/.pixi
export RATTLER_CACHE_DIR=/work/.cache/rattler/cache
curl -fsSL https://pixi.sh/install.sh | env PIXI_HOME="$PIXI_HOME" PIXI_BIN_DIR="$PIXI_HOME/bin" PIXI_NO_PATH_UPDATE=1 bash
export PATH="$PIXI_HOME/bin:$PATH"
pixi install --manifest-path mojo_env/pixi.toml
# MAX 26.5 ships precompiled lib/mojo/{linalg,pipeline,quantization,kv_cache}.mojoc that Mojo
# resolves AHEAD of -I, colliding with same-named repo modules. build_mojo_binary.sh runs this on
# every build; this leg does not go through that script, so it runs it explicitly.
bash scripts/shadow_max_pkg_name_collisions.sh /work/mojo_env/.pixi/envs/default/lib

# ── 3. (a) tc_shim.cu -> sm_90a object, via the campaign's own shim build ───────────────────────
# That script generates the embedded-PTX header tc_rt_ptx.h from tc_rt_kernels.cu FIRST: tc_shim.cu
# includes it unconditionally at :4953, and a missing header is the single most repeated failure in
# this lane's history (it killed chain5c, chain5d and the round-6 re-stage).
mkdir -p "$SHIM_DIR" "$OUT_DIR"
PTXD="$SHIM_DIR" SM="$CUDA_TARGET" COMPUTE="$CUDA_COMPUTE" CUDA_HOME="$CUDA_HOME" \
  NR="/work/benchmarks/llm_smoke/nvidia_race" \
  REGLOG="$SHIM_DIR/ptxas_v.log" \
  OBJNAME="tc_shim.o" \
  bash benchmarks/llm_smoke/nvidia_race/build_shim_gemma3_round7.sh
SHIM_OBJ="$SHIM_DIR/tc_shim.o"
if [ ! -s "$SHIM_OBJ" ]; then
  echo "::error::the shim build reported success but produced no object at $SHIM_OBJ" >&2
  tail -60 "$SHIM_DIR/ptxas_v.log" || true
  exit 1
fi
# The stock flavour assertion, from the object rather than from the flags we intended to pass: with
# no -D ALGENTA_TC_SHIM_LT the cublasLt block has NO #else stubs, so tc_shim_lt_tune must be absent.
# Its PRESENCE would mean this gate certified a shim that is not the stock one.
if nm "$SHIM_OBJ" 2>/dev/null | grep -q "tc_shim_lt_tune"; then
  echo "::error::the shim object carries cublasLt symbols but this build declared the stock flavour" >&2
  exit 1
fi
SHIM_SYMBOLS="$(nm "$SHIM_OBJ" 2>/dev/null | grep -c ' T tc_shim_' || true)"
SHIM_SYMBOLS="${SHIM_SYMBOLS:-0}"
echo "shim object: $(stat -c %s "$SHIM_OBJ") bytes, ${SHIM_SYMBOLS} exported tc_shim_* entry points"
if [ "${SHIM_SYMBOLS}" -lt 20 ]; then
  echo "::error::only ${SHIM_SYMBOLS} tc_shim_* entry points; the shim did not compile its kernels in" >&2
  exit 1
fi

# ── 4. (b) the engine executable ────────────────────────────────────────────────────────────────
# `pixi run mojo build` from inside mojo_env/ (never the env's mojo binary directly: that skips
# conda's activate.d and dies with "unable to locate module 'std'"). Absolute .so paths rather than
# -Xlinker -L: every in-repo recipe puts -L AFTER the -l flags, which GNU ld does not apply
# retroactively, and that only ever worked because the race VMs had the toolkit on a default path.
#
# THE rpath FORM IS LOAD-BEARING — read before "simplifying" it back to -Wl,. `-Xlinker X` hands X
# to the linker VERBATIM as ONE token; it does not go through gcc/clang's -Wl, comma splitting. So
# `-Xlinker "-Wl,-rpath,$ORIGIN"` handed ld the single literal option `-Wl,-rpath,$ORIGIN`, and
# `-Wl,` is a DRIVER prefix ld has never understood. The link died:
#   /usr/bin/ld: unrecognized option '-Wl,-rpath,$ORIGIN'
#   collect2: error: ld returned 1 exit status
#   mojo: error: failed to link executable
# (build-runtime.yml run 35650281651, job "build bundled runtime wheel (linux-x86_64, CUDA compile
# gate)"). `collect2` in that trace names the path: mojo links through the container's gcc, gcc runs
# collect2, collect2 runs /usr/bin/ld — and an -Xlinker token is forwarded down that chain unsplit,
# so nothing ever strips the -Wl,. `-Wl,-rpath,$ORIGIN` expands to EXACTLY two ld tokens, `-rpath`
# and `$ORIGIN`, which is what the two -Xlinker flags below pass; same linker command line, no
# driver prefix to strip. This is also the campaign's own convention — the race recipes in
# benchmarks/llm_smoke/REALRACE_RESULTS.md spell `-framework Metal` as
# `-Xlinker -framework -Xlinker Metal`, one linker token per -Xlinker.
# The `\$ORIGIN` escape keeps the dollar out of the shell: it must reach the ELF DT_RUNPATH as the
# literal string the dynamic loader expands at load time, exactly as the failing log showed it
# arriving. `-Xlinker -ldl` stays one token on purpose — GNU ld accepts `-l<namespec>` directly,
# so unlike -Wl, it needs no splitting.
MOJO_DEFINES=()
for define in "${DEFINES[@]}"; do MOJO_DEFINES+=(-D "$define"); done
ENGINE_BIN="$OUT_DIR/$ENGINE_NAME"
# THE RPATH, PASSED THE WAY `ld` SPELLS IT AND NOT THE WAY A COMPILER DRIVER SPELLS IT.
# `-Xlinker X` hands X to the linker VERBATIM, so this used to read
# `-Xlinker "-Wl,-rpath,$ORIGIN"` -- and `-Wl,` is gcc/clang's prefix for "forward the rest to the
# linker", which is meaningless once you are ALREADY talking to the linker. GNU ld rejected it with
# `unrecognized option '-Wl,-rpath,$ORIGIN'`, the engine failed to link, and the whole cuda compile
# gate (and therefore every cuda wheel) was red on main. `-Wl,-rpath,$ORIGIN` expands to exactly the
# two linker arguments used below, so this is the intended flag, correctly spelled. It went uncaught
# because build-runtime.yml has no `pull_request` trigger: the PR that added this step never ran it.
# NOTE the comment lives OUTSIDE the command on purpose: a `#` inside a backslash-continued argument
# list ends the logical line, which would silently drop every flag after it.
(
  cd /work/mojo_env && pixi run mojo build \
    "${MOJO_DEFINES[@]}" \
    --target-accelerator "$CUDA_TARGET" \
    -I /work/mojo/engine -I /work/attention_forge \
    "/work/$ENGINE_SRC" \
    -o "$ENGINE_BIN" \
    -Xlinker "$SHIM_OBJ" \
    -Xlinker "$CUDA_LIBDIR/libcublas.so" \
    -Xlinker "$CUDA_LIBDIR/libcudart.so" \
    -Xlinker "-rpath" \
    -Xlinker "\$ORIGIN" \
    -Xlinker -ldl
)
if [ ! -x "$ENGINE_BIN" ]; then
  echo "::error::the engine build reported success but produced no executable at $ENGINE_BIN" >&2
  exit 1
fi
file "$ENGINE_BIN"
echo "engine: $(stat -c %s "$ENGINE_BIN") bytes"

# ── 5. What the engine actually needs from the host, DERIVED not declared ───────────────────────
# The wheel bundles libcudart.so.12 (~1 MB) beside the engine with an $ORIGIN rpath. It CANNOT
# bundle cuBLAS: nvidia-cublas-cu12 is 581,240,110 bytes for linux x86_64 against a 42 MB wheel, and
# cuBLAS is in no manylinux allowlist. So cublas/cublasLt stay host-provided and are RECORDED in the
# signed manifest (engine.host_shared_libraries) — the posture the runtime already takes for
# libcuda.so.1, which the shim dlopens rather than links. build_runtime_linux_amd64.sh refuses to
# sign a cuda manifest whose declared host libraries are not exactly this derived set, and its
# auditwheel gate refuses any external library that is not on that list.
# LD_LIBRARY_PATH must name the toolkit here: the engine's rpath is $ORIGIN and $OUT_DIR holds no
# CUDA library yet, so a bare `ldd` would report "not found" for both and the derivation below would
# classify libcudart as a host requirement instead of bundling it.
LD_LIBRARY_PATH="$CUDA_LIBDIR" ldd "$ENGINE_BIN" > "$OUT_DIR/engine.ldd" || true
cat "$OUT_DIR/engine.ldd"
HOST_LIBS=()
BUNDLED_LIBS=()
while read -r soname resolved; do
  case "$soname" in
    libcublas.so.*|libcublasLt.so.*)
      # Never bundled: 581 MB of cuBLAS against a 42 MB wheel. Declared as a host requirement.
      HOST_LIBS+=("$soname")
      ;;
    libcudart.so.*)
      case "$resolved" in
        /*)
          if [ -e "$resolved" ]; then
            cp -L "$resolved" "$OUT_DIR/$soname"
            BUNDLED_LIBS+=("$soname")
          else
            HOST_LIBS+=("$soname")
          fi
          ;;
        *) HOST_LIBS+=("$soname") ;;
      esac
      ;;
  esac
done < <(awk '/=>/ {print $1, $3} !/=>/ {print $1, "-"}' "$OUT_DIR/engine.ldd")

if [ "${#HOST_LIBS[@]}" -eq 0 ]; then
  echo "::error::the engine declared no host cuBLAS dependency — did the shim actually link?" >&2
  exit 1
fi
if [ "${#BUNDLED_LIBS[@]}" -eq 0 ]; then
  echo "::warning::no libcudart was bundled beside the engine; it becomes a host requirement too"
  HOST_LIBS+=("libcudart.so.12")
fi
echo "engine host libraries (declared in the signed manifest): ${HOST_LIBS[*]}"
echo "engine bundled libraries: ${BUNDLED_LIBS[*]:-<none>}"

# The GPU-less smoke: the dynamic loader resolves every DT_NEEDED before main(), so this only runs
# if the closure is complete. No arguments -> the usage path -> exit 2 (conform_generate_cuda.mojo).
# It is NOT a claim the engine generates anything: with no accelerator the engine exits 4 by design,
# and cuBLAS is reachable here only because this step installed the toolkit — on a user's host it is
# the declared host requirement the manifest records.
set +e
( cd "$OUT_DIR" && LD_LIBRARY_PATH="$OUT_DIR:$CUDA_LIBDIR" ./"$ENGINE_NAME" )
SMOKE_RC=$?
set -e
if [ "$SMOKE_RC" -ne 2 ]; then
  echo "::error::the engine's GPU-less usage-path smoke exited ${SMOKE_RC}, expected 2" >&2
  exit 1
fi
echo "engine smoke OK (exit 2 on the usage path, GPU-less)"

# ── 6. The sidecar build_runtime_linux_amd64.sh reads ───────────────────────────────────────────
ENGINE_DEFINES="${DEFINES[*]}"
export ENGINE_DEFINES
python3 - "$OUT_DIR" "$ENGINE_NAME" "$ENGINE_SRC" "$CUDA_TARGET" "$SHIM_OBJ" \
           "${HOST_LIBS[@]}" <<'PY'
import hashlib
import json
import os
import subprocess
import sys

out_dir, name, source, target, shim_obj = sys.argv[1:6]
host_libs = [item for item in sys.argv[6:] if item]
defines = os.environ["ENGINE_DEFINES"].split()


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


payload = {
    "schema_version": 1,
    "name": name,
    "source": source,
    "cuda_target": target,
    "comptime_defines": defines,
    "host_shared_libraries": sorted(set(host_libs)),
    "bundled_shared_libraries": sorted(
        entry for entry in os.listdir(out_dir) if entry.startswith("libcudart.so")
    ),
    "engine_sha256": sha256(os.path.join(out_dir, name)),
    "engine_bytes": os.path.getsize(os.path.join(out_dir, name)),
    "shim_object_sha256": sha256(shim_obj),
    "shim_object_bytes": os.path.getsize(shim_obj),
    "nvcc_version": subprocess.run(  # noqa: S603 - fixed argv, no shell
        [os.path.join(os.environ["CUDA_HOME"], "bin", "nvcc"), "--version"],
        check=True, capture_output=True, text=True,
    ).stdout.strip().splitlines()[-1],
}
with open(os.path.join(out_dir, "engine-build.json"), "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)
    handle.write("\n")
print("engine-build.json: variant=cuda target=%s host_libs=%s"
      % (target, ",".join(payload["host_shared_libraries"])))
PY

# The container ran as root on the mounted runner workspace; hand the tree back to the workspace
# owner so the next step (and the runner-side artifact upload, a non-root user) can read it.
OWNER="$(stat -c '%u:%g' /work/.git)"
chown -R "$OWNER" /work/mojo_build /work/.pixi /work/.cache /work/mojo_env/.pixi 2>/dev/null || true
echo "cuda engine compile gate OK (${CUDA_TARGET}, $(stat -c %s "$ENGINE_BIN") bytes)"
