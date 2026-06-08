#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIXI_MANIFEST_PATH="${ROOT_DIR}/mojo_env/pixi.toml"

if [ "$#" -eq 0 ]; then
  echo "run_repo_python.sh requires a Python command or script path." >&2
  exit 64
fi

if [ ! -f "${PIXI_MANIFEST_PATH}" ]; then
  echo "Pixi manifest not found at ${PIXI_MANIFEST_PATH}." >&2
  exit 66
fi

PIXI_HOME_EXPLICIT=0
if [ -n "${PIXI_HOME:-}" ]; then
  PIXI_HOME_EXPLICIT=1
fi

PIXI_HOME_DIR="${PIXI_HOME:-${ROOT_DIR}/.pixi}"
case "${PIXI_HOME_DIR}" in
  '~' | '~'/*) PIXI_HOME_DIR="${HOME-}${PIXI_HOME_DIR#\~}" ;;
esac

RATTLER_CACHE_DIR_VALUE="${RATTLER_CACHE_DIR:-${ROOT_DIR}/.cache/rattler/cache}"
RATTLER_AUTH_FILE_VALUE="${RATTLER_AUTH_FILE:-${ROOT_DIR}/.cache/rattler/credentials.json}"
export PIXI_HOME="${PIXI_HOME_DIR}"
export RATTLER_CACHE_DIR="${RATTLER_CACHE_DIR_VALUE}"
export RATTLER_AUTH_FILE="${RATTLER_AUTH_FILE_VALUE}"

mkdir -p "${PIXI_HOME}" "${RATTLER_CACHE_DIR}" "$(dirname "${RATTLER_AUTH_FILE}")"

declare -a candidates=()
if [ -n "${PIXI_BIN:-}" ]; then
  candidates+=("${PIXI_BIN}")
fi
if [ "${PIXI_HOME_EXPLICIT}" = "1" ]; then
  candidates+=("${PIXI_HOME}/bin/pixi")
fi

if command -v pixi >/dev/null 2>&1; then
  candidates+=("$(command -v pixi)")
fi

if [ "${PIXI_HOME_EXPLICIT}" = "0" ]; then
  candidates+=("${PIXI_HOME}/bin/pixi")
fi

for candidate in "${candidates[@]}"; do
  if [ -n "${candidate}" ] && [ -x "${candidate}" ]; then
    exec "${candidate}" run --manifest-path "${PIXI_MANIFEST_PATH}" python "$@"
  fi
done

# No pixi available — fall back to plain python3 if a system Python is on PATH.
# This keeps lightweight targets (e.g. docs-gitbook-verify) working in CI
# without forcing a full Mojo/Pixi environment install.
if command -v python3 >/dev/null 2>&1; then
  exec python3 "$@"
fi

echo "No usable pixi binary or python3 found. Run bash scripts/install_mojo.sh or set PIXI_BIN." >&2
exit 127
