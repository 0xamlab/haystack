#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Algenta Decision Engine — Mojo Engine Setup
#
# Installs pixi (Modular's recommended package manager for Mojo 0.26+),
# creates a pixi environment with Mojo, and builds the native binary.
#
# Usage:
#   bash scripts/install_mojo.sh
#
# After success:
#   mojo_build/simulate is built and ready.
#   Restart make dev-api — engine_version will show "0.2.0-mojo-native"
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

# ── Step 1: Install pixi ──────────────────────────────────────────────────────
step "Installing pixi package manager"

if command -v pixi &>/dev/null; then
    info "pixi already installed: $(pixi --version 2>/dev/null || echo 'version unknown')"
else
    info "Downloading pixi from https://pixi.sh/install.sh ..."
    curl -fsSL https://pixi.sh/install.sh | bash
    # Add pixi to PATH for this session
    export PATH="${HOME}/.pixi/bin:${PATH}"
fi

if ! command -v pixi &>/dev/null; then
    export PATH="${HOME}/.pixi/bin:${PATH}"
fi

command -v pixi &>/dev/null || error "pixi not found. Open a new terminal and re-run, or add ~/.pixi/bin to PATH."
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
pixi run mojo --version 2>/dev/null && info "Mojo version: $(pixi run mojo --version 2>/dev/null)"

# ── Step 3: Build the Mojo binary ─────────────────────────────────────────────
step "Building Mojo engine binary"
mkdir -p "${BUILD_DIR}"

cd "${PIXI_ENV_DIR}"
if pixi run mojo build "${MOJO_SRC}" -o "${BINARY}" 2>&1; then
    info "Build succeeded!"
else
    error "Build failed. Check mojo/engine/main.mojo for syntax errors."
fi

chmod +x "${BINARY}"
info "Binary: ${BINARY} ($(du -sh "${BINARY}" 2>/dev/null | cut -f1))"

# ── Step 4: Smoke-test ────────────────────────────────────────────────────────
step "Smoke-test (500 scenarios)"
SMOKE='{"runs":500,"variables":[{"name":"rev","distribution":"normal","params":{"mean":100000,"std":20000}}],"objective_function":"rev"}'
RESULT=$(echo "${SMOKE}" | "${BINARY}" 2>/dev/null)

if echo "${RESULT}" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['engine_version'] == '0.2.0-mojo-native' and d['scenarios_run'] == 500" 2>/dev/null; then
    MEAN=$(echo "${RESULT}" | python3 -c "import json,sys; print(round(json.load(sys.stdin)['summary']['mean'],0))" 2>/dev/null || echo "?")
    info "Smoke-test PASSED  engine_version=0.2.0-mojo-native  mean=${MEAN}"
else
    error "Smoke-test failed.\nBinary output:\n${RESULT}"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
info "────────────────────────────────────────────────────────────────"
info "✅  Mojo engine is ready: ${BINARY}"
info "    Restart the API server: make dev-api"
info "    Responses will show engine_version: 0.2.0-mojo-native"
info "────────────────────────────────────────────────────────────────"
