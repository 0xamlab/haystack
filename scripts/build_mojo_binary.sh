#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_BUILD_DIR="${REPO_ROOT}/mojo_build"
MOJO_SRC="${MOJO_SRC:-${REPO_ROOT}/mojo/engine/main.mojo}"
DISPATCH_GENERATOR="${REPO_ROOT}/scripts/generate_runtime_library_dispatch.py"
DISPATCH_OUTPUT_PATH="${DISPATCH_OUTPUT_PATH:-${REPO_ROOT}/mojo/engine/runtime_library_dispatch_generated.mojo}"
PIXI_ENV_DIR="${REPO_ROOT}/mojo_env"
ENV_BIN_DIR="${PIXI_ENV_DIR}/.pixi/envs/default/bin"
LIB_DIR="${PIXI_ENV_DIR}/.pixi/envs/default/lib"
ENGINE_INCLUDE_DIR="${ENGINE_INCLUDE_DIR:-${REPO_ROOT}/mojo/engine}"
PYTHON_BIN="${ENV_BIN_DIR}/python"
BINARY_PATH="${BINARY_PATH:-${DEFAULT_BUILD_DIR}/simulate}"
OBJECT_PATH="${OBJECT_PATH:-${DEFAULT_BUILD_DIR}/simulate.o}"
TEMP_OBJECT_PATH="${TEMP_OBJECT_PATH:-${DEFAULT_BUILD_DIR}/simulate.o.tmp}"
TEMP_BINARY_PATH="${TEMP_BINARY_PATH:-${DEFAULT_BUILD_DIR}/simulate.tmp}"
BUILD_DIR="$(dirname "${BINARY_PATH}")"
MOJO_RUNTIME_MODULE_FILTER_RAW="${MOJO_RUNTIME_MODULE_FILTER:-}"

PIXI_HOME_EXPLICIT=0
if [[ -n "${PIXI_HOME:-}" ]]; then
    PIXI_HOME_EXPLICIT=1
fi

PIXI_HOME_DIR="${PIXI_HOME:-${REPO_ROOT}/.pixi}"
case "${PIXI_HOME_DIR}" in
    '~' | '~'/*) PIXI_HOME_DIR="${HOME-}${PIXI_HOME_DIR#\~}" ;;
esac

RATTLER_CACHE_DIR_VALUE="${RATTLER_CACHE_DIR:-${REPO_ROOT}/.cache/rattler/cache}"
RATTLER_AUTH_FILE_VALUE="${RATTLER_AUTH_FILE:-${REPO_ROOT}/.cache/rattler/credentials.json}"
export PIXI_HOME="${PIXI_HOME_DIR}"
export RATTLER_CACHE_DIR="${RATTLER_CACHE_DIR_VALUE}"
export RATTLER_AUTH_FILE="${RATTLER_AUTH_FILE_VALUE}"

mkdir -p "${PIXI_HOME}" "${RATTLER_CACHE_DIR}" "$(dirname "${RATTLER_AUTH_FILE}")"

resolve_pixi_bin() {
    local candidates=()
    local candidate

    if [[ -n "${PIXI_BIN:-}" ]]; then
        candidates+=("${PIXI_BIN}")
    fi
    if [[ "${PIXI_HOME_EXPLICIT}" == "1" ]]; then
        candidates+=("${PIXI_HOME}/bin/pixi")
    fi
    if command -v pixi >/dev/null 2>&1; then
        candidates+=("$(command -v pixi)")
    fi
    if [[ "${PIXI_HOME_EXPLICIT}" == "0" ]]; then
        candidates+=("${PIXI_HOME}/bin/pixi")
    fi

    for candidate in "${candidates[@]}"; do
        if [[ -n "${candidate}" && -x "${candidate}" ]]; then
            printf '%s\n' "${candidate}"
            return 0
        fi
    done

    return 1
}

if [[ ! -f "${MOJO_SRC}" ]]; then
    echo "Mojo entrypoint not found at ${MOJO_SRC}" >&2
    exit 1
fi

if [[ ! -f "${DISPATCH_GENERATOR}" ]]; then
    echo "Runtime library dispatch generator not found at ${DISPATCH_GENERATOR}" >&2
    exit 1
fi

if [[ ! -d "${ENGINE_INCLUDE_DIR}" ]]; then
    echo "Mojo engine include directory not found at ${ENGINE_INCLUDE_DIR}" >&2
    exit 1
fi

if [[ ! -d "${PIXI_ENV_DIR}" ]]; then
    echo "Mojo environment not found at ${PIXI_ENV_DIR}. Run: make setup-mojo" >&2
    exit 1
fi

if [[ ! -d "${LIB_DIR}" ]]; then
    echo "Mojo runtime library directory missing at ${LIB_DIR}. Run: make setup-mojo" >&2
    exit 1
fi

PIXI_BIN_RESOLVED="$(resolve_pixi_bin || true)"
if [[ -z "${PIXI_BIN_RESOLVED}" || ! -x "${PIXI_BIN_RESOLVED}" ]]; then
    echo "pixi not found. Run: make setup-mojo" >&2
    exit 1
fi

if [[ -x "${PYTHON_BIN}" ]]; then
    PYTHON_RUNTIME_STEM="$("${PYTHON_BIN}" - <<'PY'
import sys
print(f"python{sys.version_info.major}.{sys.version_info.minor}")
PY
)"
else
    PYTHON_RUNTIME_STEM="$(
        (
            cd "${PIXI_ENV_DIR}"
            "${PIXI_BIN_RESOLVED}" run python - <<'PY'
import sys
print(f"python{sys.version_info.major}.{sys.version_info.minor}")
PY
        )
    )"
fi
if [[ -z "${PYTHON_RUNTIME_STEM}" ]]; then
    echo "Failed to detect the Python runtime version from ${PIXI_ENV_DIR}" >&2
    exit 1
fi

CLANG_BIN="${CLANG_BIN:-}"
if [[ -z "${CLANG_BIN}" ]]; then
    CLANG_BIN="$(xcrun --find clang 2>/dev/null || command -v clang 2>/dev/null || true)"
fi
if [[ -z "${CLANG_BIN}" || ! -x "${CLANG_BIN}" ]]; then
    echo "clang not found; cannot link Mojo object into an executable" >&2
    exit 1
fi

SDKROOT_PATH="${SDKROOT:-}"
if [[ -z "${SDKROOT_PATH}" ]]; then
    SDKROOT_PATH="$(xcrun --show-sdk-path 2>/dev/null || true)"
fi

mkdir -p \
    "${BUILD_DIR}" \
    "$(dirname "${OBJECT_PATH}")" \
    "$(dirname "${TEMP_OBJECT_PATH}")" \
    "$(dirname "${TEMP_BINARY_PATH}")" \
    "$(dirname "${DISPATCH_OUTPUT_PATH}")"
rm -f "${TEMP_OBJECT_PATH}" "${TEMP_BINARY_PATH}"

DISPATCH_GENERATOR_ARGS=(--output "${DISPATCH_OUTPUT_PATH}")
if [[ -n "${MOJO_RUNTIME_MODULE_FILTER_RAW}" ]]; then
    IFS=',' read -r -a RAW_MODULE_FILTER <<< "${MOJO_RUNTIME_MODULE_FILTER_RAW}"
    MODULE_FILTER=()
    for module_name in "${RAW_MODULE_FILTER[@]}"; do
        module_name="${module_name//[[:space:]]/}"
        if [[ -n "${module_name}" ]]; then
            MODULE_FILTER+=("${module_name}")
        fi
    done
    if [[ "${#MODULE_FILTER[@]}" -gt 0 ]]; then
        DISPATCH_GENERATOR_ARGS+=(--modules "${MODULE_FILTER[@]}")
    fi
fi

python3 "${DISPATCH_GENERATOR}" "${DISPATCH_GENERATOR_ARGS[@]}" >/dev/null

# Mojo compile must run inside the pixi-managed environment so std/package
# roots resolve exactly as they do for runtime-owned test and server invocations.
(
    cd "${PIXI_ENV_DIR}"
    "${PIXI_BIN_RESOLVED}" run mojo build \
        -I "${ENGINE_INCLUDE_DIR}" \
        "${MOJO_SRC}" \
        --emit object \
        -o "${TEMP_OBJECT_PATH}"
)

RPATH_RELATIVE='@executable_path/../mojo_env/.pixi/envs/default/lib'

case "$(uname -s)" in
    Darwin)
        PYTHON_RUNTIME_LIB="${LIB_DIR}/lib${PYTHON_RUNTIME_STEM}.dylib"
        if [[ -z "${SDKROOT_PATH}" || ! -d "${SDKROOT_PATH}" ]]; then
            echo "macOS SDK not found; cannot link Mojo executable" >&2
            exit 1
        fi
        if [[ ! -f "${PYTHON_RUNTIME_LIB}" ]]; then
            echo "Python runtime library not found at ${PYTHON_RUNTIME_LIB}" >&2
            exit 1
        fi
        "${CLANG_BIN}" "${TEMP_OBJECT_PATH}" -o "${TEMP_BINARY_PATH}" \
            -isysroot "${SDKROOT_PATH}" \
            -L "${LIB_DIR}" \
            -Wl,-syslibroot,"${SDKROOT_PATH}" \
            -Wl,-rpath,"${RPATH_RELATIVE}" \
            -Wl,-rpath,"${LIB_DIR}" \
            -lKGENCompilerRTShared \
            -lAsyncRTRuntimeGlobals \
            -lAsyncRTMojoBindings \
            -lMSupportGlobals \
            -l"${PYTHON_RUNTIME_STEM}" \
            -lc++
        ;;
    Linux)
        PYTHON_RUNTIME_LIB="$(find "${LIB_DIR}" -maxdepth 1 -name "lib${PYTHON_RUNTIME_STEM}.so*" | sort | head -n 1)"
        if [[ -z "${PYTHON_RUNTIME_LIB}" ]]; then
            echo "Python runtime library not found under ${LIB_DIR} for ${PYTHON_RUNTIME_STEM}" >&2
            exit 1
        fi
        # The linux pixi env ships GNU libstdc++ (libstdcxx in pixi.lock), NOT libc++ — so the
        # Mojo runtime libs are built against libstdc++ and we link -lstdc++ (the macOS branch
        # uses -lc++, its system C++ runtime). conda runtime packages ship only the versioned
        # libstdc++.so.N, so create the unversioned linker symlink in LIB_DIR — the link then
        # binds the SAME libstdc++ the $ORIGIN rpath loads at runtime (no system/ABI skew).
        if ! [[ -e "${LIB_DIR}/libstdc++.so" ]]; then
            stdcxx_versioned="$(find "${LIB_DIR}" -maxdepth 1 -name "libstdc++.so.*" | sort -V | tail -n 1)"
            if [[ -n "${stdcxx_versioned}" ]]; then
                ln -sf "$(basename "${stdcxx_versioned}")" "${LIB_DIR}/libstdc++.so"
            fi
        fi
        echo "[build_mojo_binary] C++ runtime libs in ${LIB_DIR}:" >&2
        ls -la "${LIB_DIR}"/libstdc++* "${LIB_DIR}"/libc++* >&2 2>&1 || true
        "${CLANG_BIN}" "${TEMP_OBJECT_PATH}" -o "${TEMP_BINARY_PATH}" \
            -L "${LIB_DIR}" \
            -Wl,-rpath,'$ORIGIN/../mojo_env/.pixi/envs/default/lib' \
            -Wl,-rpath,"${LIB_DIR}" \
            -lKGENCompilerRTShared \
            -lAsyncRTRuntimeGlobals \
            -lAsyncRTMojoBindings \
            -lMSupportGlobals \
            -l"${PYTHON_RUNTIME_STEM}" \
            -lstdc++ \
            -ldl \
            -lpthread \
            -lm
        ;;
    *)
        echo "Unsupported platform for native Mojo link: $(uname -s)" >&2
        exit 1
        ;;
esac

chmod +x "${TEMP_BINARY_PATH}"
mv "${TEMP_BINARY_PATH}" "${BINARY_PATH}"
rm -f "${TEMP_OBJECT_PATH}" "${OBJECT_PATH}"

echo "${BINARY_PATH}"
