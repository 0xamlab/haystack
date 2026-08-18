#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Codna Decision Engine — Mojo Engine Setup
#
# Installs pixi (Modular's recommended package manager for Mojo 0.26+),
# creates a pixi environment with Mojo, and builds the native binary.
#
# Usage:
#   bash scripts/install_mojo.sh
#
# After success:
#   Mojo is installed in the repo-local pixi environment.
#   If mojo/engine/main.mojo exists, mojo_build/simulate is also built.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${GREEN}[mojo-setup]${NC} $1"; }
warn()  { echo -e "${YELLOW}[mojo-setup]${NC} $1"; }
error() { echo -e "${RED}[mojo-setup]${NC} $1"; exit 1; }
step()  { echo -e "\n${BOLD}${GREEN}━━ $1 ━━${NC}"; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${REPO_ROOT}/mojo_build"
BINARY="${BUILD_DIR}/simulate"
MOJO_SRC="${REPO_ROOT}/mojo/engine/main.mojo"
PIXI_ENV_DIR="${REPO_ROOT}/mojo_env"
PIXI_HOME_DIR="${PIXI_HOME:-${REPO_ROOT}/.pixi}"

case "${PIXI_HOME_DIR}" in
    '~' | '~'/*) PIXI_HOME_DIR="${HOME-}${PIXI_HOME_DIR#\~}" ;;
esac

PIXI_BIN_DIR="${PIXI_BIN_DIR:-${PIXI_HOME_DIR}/bin}"
PIXI_NO_PATH_UPDATE="${PIXI_NO_PATH_UPDATE:-1}"
RATTLER_CACHE_DIR="${RATTLER_CACHE_DIR:-${REPO_ROOT}/.cache/rattler/cache}"
RATTLER_AUTH_FILE="${RATTLER_AUTH_FILE:-${REPO_ROOT}/.cache/rattler/credentials.json}"
export PIXI_HOME="${PIXI_HOME_DIR}"
export PIXI_BIN_DIR
export PIXI_NO_PATH_UPDATE
export RATTLER_CACHE_DIR
export RATTLER_AUTH_FILE

mkdir -p "${PIXI_BIN_DIR}" "${RATTLER_CACHE_DIR}" "$(dirname "${RATTLER_AUTH_FILE}")"

# ── Step 1: Install pixi ──────────────────────────────────────────────────────
step "Installing pixi package manager"

if command -v pixi &>/dev/null; then
    info "pixi already installed: $(pixi --version 2>/dev/null || echo 'version unknown')"
else
    info "Downloading pixi from https://pixi.sh/install.sh ..."
    info "Installing pixi into ${PIXI_BIN_DIR}"
    curl -fsSL https://pixi.sh/install.sh | bash
    # Add pixi to PATH for this session
    export PATH="${PIXI_BIN_DIR}:${PATH}"
fi

if ! command -v pixi &>/dev/null; then
    export PATH="${PIXI_BIN_DIR}:${PATH}"
fi

command -v pixi &>/dev/null || error "pixi not found. Re-run with PIXI_HOME set, or add ${PIXI_BIN_DIR} to PATH."
info "pixi: $(pixi --version 2>/dev/null)"

# ── Step 2: Create pixi env with Mojo ────────────────────────────────────────
step "Setting up pixi environment with Mojo (nightly)"

if [[ -d "${PIXI_ENV_DIR}" ]]; then
    info "pixi environment already exists at ${PIXI_ENV_DIR}"
else
    info "Creating pixi environment..."
    pixi init "${PIXI_ENV_DIR}" \
        -c "https://conda.modular.com/max-nightly/" \
        -c "conda-forge"
    cd "${PIXI_ENV_DIR}" && pixi add mojo
    info "Mojo installed in pixi environment."
fi

# Verify mojo is available
cd "${PIXI_ENV_DIR}"
pixi install
pixi run mojo --version 2>/dev/null && info "Mojo version: $(pixi run mojo --version 2>/dev/null)"

# MAX 26.5 ships precompiled packages named linalg/pipeline/quantization/kv_cache that shadow this
# repo's runtime-library modules of the same names; hide them right after install so `mojo run`
# lanes that never touch build_mojo_binary.sh see the engine's modules too. scripts/build_mojo_binary.sh
# re-runs this on every build as well (a later `pixi install` restores the packages).
bash "${REPO_ROOT}/scripts/shadow_max_pkg_name_collisions.sh" "${PIXI_ENV_DIR}/.pixi/envs/default/lib"

# ── Step 3: Build the Mojo binary when the source entrypoint exists ───────────
# Defaults to a small filtered build (a single, arbitrary runtime-library module --
# the smoke test below never calls it, it only needs *some* value so
# build_mojo_binary.sh takes the filtered/bounded path). An unfiltered first-time
# setup build would compile the FULL runtime-library catalog (640+ modules as of
# this writing) into one translation unit alongside main.mojo, which reliably hits
# a confirmed upstream Mojo compiler stack-overflow on the pinned toolchain past
# ~550 modules (see the guard + citations in build_mojo_binary.sh) -- i.e. it would
# never have succeeded here at all. Override MOJO_RUNTIME_MODULE_FILTER yourself
# for a different bounded subset, or run `make build-mojo-shards` afterwards for
# the full catalog via the already-production-authoritative sharded builder.
MOJO_RUNTIME_MODULE_FILTER="${MOJO_RUNTIME_MODULE_FILTER:-vector_kernels.dot}"
if [[ ! -f "${MOJO_SRC}" ]]; then
    warn "Mojo entrypoint not found at ${MOJO_SRC}; skipping native binary build."
else
    step "Building Mojo engine binary"
    mkdir -p "${BUILD_DIR}"

    # Setting MOJO_RUNTIME_MODULE_FILTER alone is NOT enough to bound this build: main.mojo
    # `#include`s its sibling dispatch table by its OWN directory, not via -I, so unless MOJO_SRC
    # is ALSO staged as a copy next to a freshly-filtered dispatch file, main.mojo still pulls in
    # mojo/engine/runtime_library_dispatch_generated.mojo -- the full, tracked, ~114k-line catalog
    # -- regardless of the filter, defeating it silently (confirmed the hard way: this is exactly
    # what happened before this staging was added here). CI (.github/workflows/ci.yml) and
    # scripts/build_runtime_shards.py both already stage this way; mirror it.
    SETUP_STAGE_DIR="${BUILD_DIR}/.setup-stage"
    mkdir -p "${SETUP_STAGE_DIR}"
    cp "${MOJO_SRC}" "${SETUP_STAGE_DIR}/main.mojo"

    if PIXI_BIN="$(command -v pixi 2>/dev/null || true)" \
        && PIXI_BIN="${PIXI_BIN}" MOJO_RUNTIME_MODULE_FILTER="${MOJO_RUNTIME_MODULE_FILTER}" \
            MOJO_SRC="${SETUP_STAGE_DIR}/main.mojo" \
            DISPATCH_OUTPUT_PATH="${SETUP_STAGE_DIR}/runtime_library_dispatch_generated.mojo" \
            bash "${REPO_ROOT}/scripts/build_mojo_binary.sh" >/dev/null; then
        info "Build succeeded! (filtered: MOJO_RUNTIME_MODULE_FILTER=${MOJO_RUNTIME_MODULE_FILTER})"
        rm -rf "${SETUP_STAGE_DIR}"
    else
        error "Build failed. Check ${MOJO_SRC} for syntax errors."
    fi

    chmod +x "${BINARY}"
    info "Binary: ${BINARY} ($(du -sh "${BINARY}" 2>/dev/null | cut -f1))"

    # ── Step 4: Smoke-test ────────────────────────────────────────────────────
    step "Smoke-test (500 scenarios)"
    SMOKE='{"runs":500,"variables":[{"name":"rev","distribution":"normal","params":{"mean":100000,"std":20000}}],"objective_function":"rev"}'
    RESULT=$(echo "${SMOKE}" | "${BINARY}" 2>/dev/null)

    if echo "${RESULT}" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['engine_version'] and d['scenarios_run'] == 500" 2>/dev/null; then
        MEAN=$(echo "${RESULT}" | python3 -c "import json,sys; print(round(json.load(sys.stdin)['summary']['mean'],0))" 2>/dev/null || echo "?")
        ENGINE_VERSION=$(echo "${RESULT}" | python3 -c "import json,sys; print(json.load(sys.stdin)['engine_version'])" 2>/dev/null || echo "?")
        info "Smoke-test PASSED  engine_version=${ENGINE_VERSION}  mean=${MEAN}"
    else
        error "Smoke-test failed.\nBinary output:\n${RESULT}"
    fi
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
info "────────────────────────────────────────────────────────────────"
if [[ -x "${BINARY}" ]]; then
    info "✅  Mojo toolchain and binary are ready: ${BINARY}"
    info "    Restart the API server: make dev-api"
    info "    Responses will show engine_version: 0.2.0-mojo-native"
else
    info "✅  Mojo toolchain is ready in ${PIXI_ENV_DIR}"
    info "    Native binary build was skipped because ${MOJO_SRC} is absent."
    info "    Mojo CLI: ${PIXI_ENV_DIR}/.pixi/envs/default/bin/mojo"
fi
info "────────────────────────────────────────────────────────────────"
