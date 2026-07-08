"""Algenta on-disk path + platform conventions (stdlib-only; no crypto, no engine, no native import).

Single source of truth for WHERE things live and the canonical platform tag, shared by the CLI, the lazy
native loader, and ``algenta runtime doctor``. Mirrors telys-sdk ``telys/paths.py`` (adapted to ALGENTA_*).
"""
from __future__ import annotations

import os
import platform
import sys

# Native artifact + manifest names (the basenames the manifest, bundler, and loader agree on).
RUNTIME_STEM = "libalgenta_runtime"
MANIFEST_NAME = "manifest.json"
MANIFEST_SIG_NAME = "manifest.sig"
LICENSE_NAME = "license.jwt"


def algenta_home() -> str:
    """Root of Algenta on-disk state. Override with $ALGENTA_HOME (tests / multi-tenant installs)."""
    return os.path.abspath(
        os.environ.get("ALGENTA_HOME") or os.path.join(os.path.expanduser("~"), ".algenta")
    )


def platform_tag() -> str:
    """Canonical ``<os>-<arch>`` tag, matching the build-runtime.yml targets (macos-arm64, linux-x86_64)."""
    m = platform.machine().lower()
    arch = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x86_64", "amd64": "x86_64"}.get(m, m)
    if sys.platform == "darwin":
        osn = "macos"
    elif sys.platform.startswith("linux"):
        osn = "linux"
    elif sys.platform.startswith("win"):
        osn = "windows"
    else:
        osn = sys.platform
    return f"{osn}-{arch}"


def lib_ext() -> str:
    """Shared-library extension for this platform (matches what the build emits)."""
    if sys.platform == "darwin":
        return "dylib"
    if sys.platform.startswith("win"):
        return "dll"
    return "so"


def runtime_lib_filename() -> str:
    return f"{RUNTIME_STEM}.{lib_ext()}"


def sidecar_native_dir() -> str | None:
    """Directory of the installed ``algenta-runtime-native`` sidecar package (its native lib + signed
    manifest), resolved via importlib.resources so it lives in its OWN import namespace — never inside the
    ``algenta/`` package (avoids cross-distribution file ownership). None if the sidecar isn't installed.
    """
    try:
        from importlib import resources

        return str(resources.files("algenta_runtime_native"))
    except (ModuleNotFoundError, ImportError, TypeError, FileNotFoundError, NotADirectoryError):
        return None


# ── Control-plane hosts. `algenta login` is the ONLY networked step; execution never touches the network.
# All overridable (env) so the client is testable against a local mock or a pre-cutover host.
DEFAULT_ACCOUNTS_URL = "https://accounts.thyn.ai"  # shared identity portal (Supabase OAuth / device-code)
DEFAULT_API_URL = "https://api.algenta.ai"  # control plane (api keys, device register, license)


def accounts_url() -> str:
    return (os.environ.get("ALGENTA_ACCOUNTS_URL") or DEFAULT_ACCOUNTS_URL).rstrip("/")


def api_url() -> str:
    # Accept the legacy engine env names too (the SDK/MCP already do).
    return (
        os.environ.get("ALGENTA_API_URL")
        or os.environ.get("ALGENTA_BASE_URL")
        or DEFAULT_API_URL
    ).rstrip("/")


def token_path() -> str:
    return os.path.join(algenta_home(), "token")


def api_key_path() -> str:
    return os.path.join(algenta_home(), "api_key")


def device_key_path() -> str:
    return os.path.join(algenta_home(), "device_key.pem")


def device_id_path() -> str:
    return os.path.join(algenta_home(), "device_id")


def license_path() -> str:
    return os.path.join(algenta_home(), LICENSE_NAME)
