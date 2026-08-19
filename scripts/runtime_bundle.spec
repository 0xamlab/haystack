# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the self-contained Algenta runtime daemon (managed-runtime bundle).

Built by scripts/build_runtime_bundle.py:

    pyinstaller --noconfirm --distpath <work>/dist --workpath <work>/build \
        scripts/runtime_bundle.spec

Produces a --onedir app at dist/algenta-runtime-daemon/ containing the daemon
executable plus its minimal dependency closure. The closure is the import graph of
apps/runtime/daemon.py + the modules it lazy-imports (executor, server, client,
license, metering, credits, ledger, proto, ...):

  first-party:  apps.runtime.* (except the relay server), apps.privacy_policy,
                apps.platform_contract_constants, and the small
                apps.api_server.{services.auth_service,config,services.plan_limits}
                chain that apps/runtime/server.py imports for AuthContext
  third-party:  structlog, grpcio (grpc + grpc.aio), protobuf, PyJWT (jwt),
                cryptography, pydantic + pydantic_settings (pulled by the
                AuthContext chain above)

The rest of apps.api_server (routers, FastAPI/SQLAlchemy stack) is EXCLUDED: the
daemon's only touchpoint is the AuthContext TypedDict chain, and the excludes below
keep PyInstaller's bytecode scan from dragging the API-server stack in through lazy
imports elsewhere.
"""

import os
import sys
from pathlib import Path

# SPECPATH is provided by PyInstaller: the directory containing this spec file.
REPO_ROOT = Path(SPECPATH).resolve().parent  # noqa: F821 — SPECPATH is injected
ENTRY_SCRIPT = REPO_ROOT / "scripts" / "runtime_bundle_entry.py"

APP_NAME = "algenta-runtime-daemon"

# Lazy (function-level) first-party imports the daemon reaches at runtime.
# PyInstaller's bytecode scan finds these on its own, but pinning them keeps
# the closure explicit and immune to import-hoisting refactors.
HIDDEN_IMPORTS = [
    "apps",
    "apps.privacy_policy",
    "apps.platform_contract_constants",
    "apps.runtime",
    "apps.runtime._dev_license_stub",
    "apps.runtime.capacity",
    "apps.runtime.client",
    "apps.runtime.coordination",
    "apps.runtime.credits",
    "apps.runtime.daemon",
    "apps.runtime.device",
    "apps.runtime.device_keypair",
    "apps.runtime.entitlement",
    "apps.runtime.executor",
    "apps.runtime.hardware_key_store",
    "apps.runtime.host_class",
    "apps.runtime.ledger",
    "apps.runtime.license",
    "apps.runtime.license_verify",
    "apps.runtime.metering",
    "apps.runtime.mojo_binary_freshness",
    "apps.runtime.mojo_capability_manifest",
    "apps.runtime.mojo_count_relations",
    "apps.runtime.mojo_inventory",
    "apps.runtime.mojo_library_runner",
    "apps.runtime.native_manifest",
    "apps.runtime.native_worker",
    "apps.runtime.node_broker",
    "apps.runtime.offline_ceremony",
    "apps.runtime.privacy_guard",
    "apps.runtime.proto",
    "apps.runtime.proto.runtime_pb2",
    "apps.runtime.proto.runtime_pb2_grpc",
    "apps.runtime.relay_delegation",
    "apps.runtime.relay_lease",
    "apps.runtime.relay_lease_store",
    "apps.runtime.sdk",
    "apps.runtime.server",
    "apps.runtime.trusted_time",
    "apps.runtime.worker_broker",
    # The AuthContext chain apps/runtime/server.py imports at module level.
    "apps.api_server",
    "apps.api_server.services",
    "apps.api_server.services.auth_service",
    "apps.api_server.services.plan_limits",
    "apps.api_server.config",
    # third-party closure
    "grpc",
    "grpc.aio",
    "structlog",
    "jwt",
    "cryptography",
    "cryptography.fernet",
    "cryptography.hazmat.primitives.asymmetric.ed25519",
    "cryptography.hazmat.primitives.asymmetric.ec",
    "pydantic",
    "pydantic_settings",
]

# Everything the daemon must NOT pull in. The FastAPI/SQLAlchemy stack is the
# load-bearing exclude (see module docstring); the rest are heavyweight packages
# reachable only through the excluded apps or present in the build environment
# by chance.
EXCLUDES = [
    "apps.api_server.routers",
    "apps.api_server.main",
    "apps.api_server.app",
    "apps.api_server.middleware",
    "apps.api_server.dependencies",
    "apps.control_plane",
    "apps.worker",
    "apps.mcp_server",
    "apps.cli",
    "apps.operator_http",
    "apps.runtime.relay_server",
    "fastapi",
    "starlette",
    "uvicorn",
    "sqlalchemy",
    "alembic",
    "asyncpg",
    "psycopg2",
    "numpy",
    "pandas",
    "pyarrow",
    "scipy",
    "matplotlib",
    "IPython",
    "jinja2",
    "httpx",
    "anyio",
    "redis",
    "stripe",
    "sentry_sdk",
    "boto3",
    "botocore",
    "tkinter",
    "pytest",
    "setuptools",
]

a = Analysis(
    [str(ENTRY_SCRIPT)],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)
