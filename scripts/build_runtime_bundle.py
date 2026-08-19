#!/usr/bin/env python3
"""Build the signed, self-contained Algenta managed-runtime bundle.

Produces dist/runtime-bundle/algenta-runtime-<version>-<platform>.tar.gz — the
artifact the SQAI provisioner downloads, verifies (scripts/verify_runtime_bundle.py
is the reference verifier it mirrors) and extracts to run the Algenta runtime
transparently: no venv, no repo checkout, no manual daemon management.

Bundle contents (all listed in the signed manifest):

    manifest.json      {bundle_format_version, runtime_bundle_version, platform,
                        created_at, engine_stub, artifacts:[{path, sha256, size}]}
    manifest.sig       RS256 (RSASSA-PKCS1-v1_5 + SHA-256) over the EXACT
                        manifest.json bytes as shipped — verify the raw bytes
                        first, json.loads second, never re-canonicalize before
                        verifying.
    daemon/            PyInstaller --onedir build of the runtime daemon
                        (scripts/runtime_bundle.spec, entry
                        scripts/runtime_bundle_entry.py). Runs standalone.
    engine/            The STAGED sharded runtime workers for this platform —
                        the exact artifacts scripts/stage_runtime_worker_package.py
                        produced from scripts/build_runtime_shards.py's output:
                        algenta-runtime-worker[-NNN] executables, their relinked
                        dylib closure, runtime-shards.json (module -> worker
                        routing) and a baked runtime_library_inventory.json that
                        matches the compiled module set (the daemon's bundle
                        autoconfiguration loads it; the lean bundle ships no
                        .mojo source to scan). The wheel-packaging manifest trio
                        (manifest.json / manifest.sig / algenta_release_pub.pem
                        from build-runtime's wheel step) stays OUT — the bundle
                        carries its own signature at the root.
    python/            Trimmed CPython home (stdlib only) the workers' embedded
                        CPython uses on a clean machine (PYTHONHOME, set by the
                        daemon's bundle autoconfiguration).

Signing key resolution (bundle-specific env names, same conventions as the
runtime license signer):

    ALGENTA_BUNDLE_SIGNING_PRIVATE_KEY        inline PEM        (production/CI)
    ALGENTA_BUNDLE_SIGNING_PRIVATE_KEY_FILE   path to PEM file  (production/CI)
    neither set → a DEV keypair is generated under
    dist/runtime-bundle/dev-keys/ with a loud warning. Never ship dev-signed
    bundles.

The matching PUBLIC key is always written next to the tarball
(bundle-signing-public.pem) — that is the key consumers embed for verification.

Also emits bundle-metadata.json next to the tarball:
    {version, platform, sha256 (of the tarball), url_template}
— the fragment scripts/generate_algenta_runtime_contract.py --bundle-metadata
folds into the runtime contract's runtime_bundle footer.

Run (local darwin-arm64 / linux-x64 auto-detected):

    python3 scripts/build_runtime_bundle.py --version 0.1.1-dev

CI: .github/workflows/build-runtime-bundle.yml
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import platform as _platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "dist" / "runtime-bundle"
SPEC_FILE = REPO_ROOT / "scripts" / "runtime_bundle.spec"
DEFAULT_WORKER_PACKAGE_DIR = REPO_ROOT / "mojo_build" / "runtime-wheel"
DEFAULT_LIB_ROOT = REPO_ROOT / "mojo_env" / ".pixi" / "envs" / "default" / "lib"
DAEMON_APP_NAME = "algenta-runtime-daemon"
SHARD_MAP_NAME = "runtime-shards.json"
INVENTORY_NAME = "runtime_library_inventory.json"

BUNDLE_FORMAT_VERSION = 1
MANIFEST_NAME = "manifest.json"
MANIFEST_SIG_NAME = "manifest.sig"
PUBLIC_KEY_NAME = "bundle-signing-public.pem"
METADATA_NAME = "bundle-metadata.json"

DEFAULT_VERSION = "0.1.1-dev"
DEFAULT_URL_TEMPLATE = (
    "https://github.com/{repo}/releases/download/"
    "runtime-bundle-v{{version}}/algenta-runtime-{{version}}-{{platform}}.tar.gz"
)

_ENV_PRIVATE_KEY = "ALGENTA_BUNDLE_SIGNING_PRIVATE_KEY"
_ENV_PRIVATE_KEY_FILE = "ALGENTA_BUNDLE_SIGNING_PRIVATE_KEY_FILE"

# Real worker binaries are Mach-O / ELF executables; a placeholder is not.
# Detect by magic bytes, not size.
_ELF_MAGIC = b"\x7fELF"
_MACHO_MAGICS = (
    b"\xcf\xfa\xed\xfe",  # 64-bit little-endian (arm64 / x86_64)
    b"\xce\xfa\xed\xfe",  # 32-bit little-endian
    b"\xca\xfe\xba\xbe",  # fat/universal
    b"\xbe\xba\xfe\xca",
)

# The staged worker package carries the WHEEL's signing trio (build-runtime.yml's
# manifest step). The bundle signs its OWN manifest at the root, so the trio stays
# out of the bundle staging (a second manifest.json inside engine/ would also
# confuse consumers that look for THE manifest).
_WHEEL_PACKAGING_FILES = {MANIFEST_NAME, MANIFEST_SIG_NAME, "algenta_release_pub.pem"}

_WORKER_NAME_PREFIX = "algenta-runtime-worker"


class BundleBuildError(Exception):
    """Bundle build failed. Nothing partially-signed is left in the output dir."""


# ── Platform / hashing helpers ────────────────────────────────────────────────


def detect_platform_tag() -> str:
    """The bundle platform tag for THIS machine: darwin-arm64 | linux-x64.

    linux-x64 (not linux-x86_64) because the SQAI provisioner derives its
    platform key from Node's os.arch() ("x64").
    """
    system = _platform.system().lower()
    machine = _platform.machine().lower()
    if system == "darwin" and machine == "arm64":
        return "darwin-arm64"
    if system == "linux" and machine in ("x86_64", "amd64"):
        return "linux-x64"
    raise BundleBuildError(
        f"Unsupported bundle platform: system={system!r} machine={machine!r} "
        "(supported: darwin-arm64, linux-x64)"
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_real_binary(binary: Path) -> bool:
    """True when the file is a real compiled executable (ELF / Mach-O)."""
    if not binary.exists() or not binary.is_file():
        return False
    with binary.open("rb") as handle:
        head = handle.read(4)
    if head == _ELF_MAGIC:
        return True
    return head in _MACHO_MAGICS


# ── Signing (RS256, bundle-specific env names) ───────────────────────────────


def resolve_signing_private_key() -> tuple[str, str]:
    """Return (private_key_pem, source). Source is 'env' | 'env-file' | ''.

    Inline env PEM first, then a *_FILE path. Empty source means: no
    production key configured (caller decides whether a dev key is allowed).
    """
    inline = (os.environ.get(_ENV_PRIVATE_KEY) or "").strip()
    if inline:
        return inline, "env"
    path_value = (os.environ.get(_ENV_PRIVATE_KEY_FILE) or "").strip()
    if path_value:
        pem = Path(path_value).expanduser().read_text().strip()
        if not pem:
            raise BundleBuildError(f"{_ENV_PRIVATE_KEY_FILE} points at an empty file: {path_value}")
        return pem, "env-file"
    return "", ""


def generate_dev_keypair(dev_keys_dir: Path) -> tuple[str, str]:
    """Generate (and persist) a DEV RSA keypair. Returns (private_pem, public_pem).

    Reuses an existing dev key in dev_keys_dir so repeated local builds verify
    against one key. NEVER used when the production env keys are set.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_path = dev_keys_dir / "bundle-signing-private.pem"
    public_path = dev_keys_dir / "bundle-signing-public.pem"
    if private_path.exists():
        private_pem = private_path.read_text().strip()
        public_pem = public_key_pem_from_private(private_pem)
        public_path.write_text(public_pem + "\n")
        return private_pem, public_pem

    dev_keys_dir.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    private_path.write_text(private_pem)
    private_path.chmod(0o600)
    public_path.write_text(public_pem)
    return private_pem.strip(), public_pem.strip()


def public_key_pem_from_private(private_key_pem: str) -> str:
    from cryptography.hazmat.primitives import serialization

    key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
    return (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
        .strip()
    )


def sign_manifest_bytes(manifest_bytes: bytes, private_key_pem: str) -> bytes:
    """RS256 (RSASSA-PKCS1-v1_5 + SHA-256) raw signature over the exact bytes."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa

    key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise BundleBuildError(
            f"Bundle signing key must be RSA (RS256), got {type(key).__name__}"
        )
    return key.sign(manifest_bytes, padding.PKCS1v15(), hashes.SHA256())


# ── Manifest ──────────────────────────────────────────────────────────────────


def _safe_relative_posix(path: Path, root: Path) -> str:
    rel = path.relative_to(root).as_posix()
    if rel.startswith("/") or ".." in rel.split("/") or rel in ("", "."):
        raise BundleBuildError(f"unsafe artifact path: {rel!r}")
    return rel


def build_manifest(
    staging_dir: Path,
    *,
    version: str,
    platform_tag: str,
    engine_stub: bool,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Walk staging_dir and build the manifest over every regular file in it.

    Symlinks are rejected outright — the bundle must be fully materialized
    (build copies dereference), so the verifier can enforce a no-symlink rule.
    """
    artifacts: list[dict[str, Any]] = []
    for path in sorted(staging_dir.rglob("*")):
        if path.is_symlink():
            raise BundleBuildError(
                f"symlink in bundle staging (dereference before manifest): {path}"
            )
        if not path.is_file():
            continue
        rel = _safe_relative_posix(path, staging_dir)
        if rel in (MANIFEST_NAME, MANIFEST_SIG_NAME):
            continue
        artifacts.append({"path": rel, "sha256": sha256_file(path), "size": path.stat().st_size})
    if not artifacts:
        raise BundleBuildError(f"no artifacts found under {staging_dir}")
    return {
        "bundle_format_version": BUNDLE_FORMAT_VERSION,
        "runtime_bundle_version": version,
        "platform": platform_tag,
        "created_at": created_at
        or _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "engine_stub": bool(engine_stub),
        "artifacts": artifacts,
    }


def canonical_manifest_bytes(manifest: dict[str, Any]) -> bytes:
    """Canonical JSON bytes — what gets signed AND what ships as manifest.json.

    The signature always covers these exact shipped bytes; the canonical form
    just makes builds deterministic.
    """
    return (
        json.dumps(manifest, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode("utf-8")


# ── Bundle assembly ───────────────────────────────────────────────────────────


def write_signed_bundle(
    staging_dir: Path,
    output_tarball: Path,
    *,
    version: str,
    platform_tag: str,
    engine_stub: bool,
    private_key_pem: str,
) -> dict[str, Any]:
    """Manifest + sign + tar staging_dir into output_tarball. Returns the manifest.

    Library entry point (also used by tests with tiny fake daemon/engine files).
    """
    manifest = build_manifest(
        staging_dir, version=version, platform_tag=platform_tag, engine_stub=engine_stub
    )
    manifest_bytes = canonical_manifest_bytes(manifest)
    signature = sign_manifest_bytes(manifest_bytes, private_key_pem)
    (staging_dir / MANIFEST_NAME).write_bytes(manifest_bytes)
    (staging_dir / MANIFEST_SIG_NAME).write_bytes(signature)

    output_tarball.parent.mkdir(parents=True, exist_ok=True)
    tmp_tarball = output_tarball.with_suffix(".tmp")
    member_paths = [MANIFEST_NAME, MANIFEST_SIG_NAME] + [
        a["path"] for a in manifest["artifacts"]
    ]
    with tarfile.open(tmp_tarball, "w:gz") as tar:
        for rel in member_paths:
            source = staging_dir / rel
            info = tar.gettarinfo(str(source), arcname=rel)
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            with source.open("rb") as handle:
                tar.addfile(info, handle)
    tmp_tarball.replace(output_tarball)
    return manifest


def write_bundle_metadata(
    output_tarball: Path,
    *,
    version: str,
    platform_tag: str,
    url_template: str,
    metadata_path: Path | None = None,
) -> Path:
    """Emit bundle-metadata.json next to the tarball (contract-footer fragment)."""
    metadata = {
        "version": version,
        "platform": platform_tag,
        "sha256": sha256_file(output_tarball),
        "url_template": url_template,
    }
    target = metadata_path or (output_tarball.parent / METADATA_NAME)
    target.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


# ── PyInstaller daemon build ──────────────────────────────────────────────────


def build_daemon_with_pyinstaller(work_dir: Path) -> Path:
    """Run PyInstaller against scripts/runtime_bundle.spec. Returns the onedir app dir."""
    dist_dir = work_dir / "pyinstaller-dist"
    build_dir = work_dir / "pyinstaller-build"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(build_dir),
        str(SPEC_FILE),
    ]
    print(f"[bundle] building daemon: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(REPO_ROOT), check=False)  # noqa: S603
    if result.returncode != 0:
        raise BundleBuildError(f"PyInstaller failed with exit code {result.returncode}")
    app_dir = dist_dir / DAEMON_APP_NAME
    if not (app_dir / DAEMON_APP_NAME).exists():
        raise BundleBuildError(f"PyInstaller output missing: {app_dir / DAEMON_APP_NAME}")
    return app_dir


def verify_daemon_standalone(daemon_dir: Path) -> None:
    """Run the frozen daemon from a temp cwd (no repo on sys.path) as a smoke check."""
    exe = daemon_dir / DAEMON_APP_NAME
    with tempfile.TemporaryDirectory(prefix="algenta-daemon-smoke-") as tmp:
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        for args, expect in (
            (["--help"], "algenta-runtime-daemon"),
            (["status"], "Algenta Runtime"),
        ):
            proc = subprocess.run(  # noqa: S603
                [str(exe), *args],
                cwd=tmp,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if proc.returncode != 0 or expect not in proc.stdout:
                raise BundleBuildError(
                    f"standalone daemon smoke check failed for {args}: "
                    f"rc={proc.returncode} stdout={proc.stdout[:400]!r} "
                    f"stderr={proc.stderr[:400]!r}"
                )
    print(f"[bundle] standalone daemon smoke check OK ({exe})")


# ── Engine staging (sharded workers) ─────────────────────────────────────────


def _copy_tree_dereferenced(source: Path, target: Path) -> None:
    """Copy a tree, materializing symlinks as real files (manifest requires it)."""
    shutil.copytree(source, target, symlinks=False)


def _stage_engine(staging_engine_dir: Path, worker_package_dir: Path) -> bool:
    """Copy the staged sharded worker package into engine/. Returns engine_stub flag.

    The input is scripts/stage_runtime_worker_package.py's output: the shard
    workers + their relinked dylib closure + runtime-shards.json, flat in one
    directory. The wheel-packaging manifest trio is excluded (the bundle signs
    its own root manifest).
    """
    if not worker_package_dir.is_dir():
        raise BundleBuildError(
            f"staged worker package not found at {worker_package_dir}. Run the "
            "shard build + staging first (scripts/build_runtime_shards.py + "
            "scripts/stage_runtime_worker_package.py)."
        )
    staging_engine_dir.mkdir(parents=True, exist_ok=True)
    workers: list[Path] = []
    shard_map = None
    for path in sorted(worker_package_dir.iterdir()):
        if not path.is_file():
            continue
        if path.name in _WHEEL_PACKAGING_FILES:
            continue
        target = staging_engine_dir / path.name
        shutil.copy2(path, target)
        if path.name == _WORKER_NAME_PREFIX or path.name.startswith(_WORKER_NAME_PREFIX + "-"):
            target.chmod(target.stat().st_mode | 0o111)
            workers.append(target)
        if path.name == SHARD_MAP_NAME:
            shard_map = target
    if not workers:
        raise BundleBuildError(
            f"no {_WORKER_NAME_PREFIX}* shards found in {worker_package_dir}"
        )
    if shard_map is None:
        raise BundleBuildError(
            f"{SHARD_MAP_NAME} missing from {worker_package_dir} — the bundle must "
            "carry the shard routing map next to the workers"
        )
    engine_stub = not all(is_real_binary(worker) for worker in workers)
    if not engine_stub:
        _stage_library_inventory(staging_engine_dir)
        _validate_shard_coverage(staging_engine_dir, workers)
    return engine_stub


def _validate_shard_coverage(staging_engine_dir: Path, workers: list[Path]) -> None:
    """The shard map must route every worker and name only staged workers."""
    payload = json.loads((staging_engine_dir / SHARD_MAP_NAME).read_text(encoding="utf-8"))
    module_workers = payload.get("module_workers")
    if not isinstance(module_workers, dict) or not module_workers:
        raise BundleBuildError("bundle shard map has no module routing entries")
    worker_names = {worker.name for worker in workers}
    routed = set(module_workers.values())
    if routed != worker_names:
        raise BundleBuildError(
            "bundle shard map and staged workers disagree: "
            f"routed={sorted(routed)} staged={sorted(worker_names)}"
        )
    default_worker = payload.get("default_worker")
    if default_worker not in worker_names:
        raise BundleBuildError(f"bundle shard map default worker missing: {default_worker!r}")


def _stage_library_inventory(staging_engine_dir: Path) -> None:
    """Bake a library inventory matching the COMPILED module set next to the workers.

    The lean bundle ships no .mojo source, so the daemon can't scan for library
    modules; it reads this prebuilt inventory instead (see
    apps.runtime.mojo_inventory.load_prebuilt_inventory + the daemon's
    _autoconfigure_bundle_runtime). The sharded CI cut compiles the FULL
    catalog across the shards, so the baked inventory is the full discovery —
    restricted by MOJO_RUNTIME_MODULE_FILTER when that env is set, so a
    filtered build (job-level env, hoisted so BOTH the compile and this baking
    step see the same set) never advertises a function the workers can't run.
    """
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        from apps.runtime.mojo_inventory import (
            DEFAULT_ENGINE_DIR,
            _RUNTIME_LIBRARY_CACHE_SCHEMA_VERSION,
            _runtime_module_to_dict,
            discover_runtime_library_modules,
        )
    except Exception as exc:  # pragma: no cover - discovery unavailable
        raise BundleBuildError(
            f"could not import apps.runtime.mojo_inventory to bake the library inventory: {exc}"
        ) from exc

    filter_raw = os.environ.get("MOJO_RUNTIME_MODULE_FILTER", "").strip()
    compiled = {m.strip() for m in filter_raw.split(",") if m.strip()} if filter_raw else None
    modules = discover_runtime_library_modules(executable_only=True)
    if compiled is not None:
        modules = tuple(
            m
            for m in modules
            if getattr(m, "lib_id", "") in compiled or getattr(m, "import_path", "") in compiled
        )
    if not modules:
        raise BundleBuildError("library inventory baking discovered zero modules")
    payload_modules = [_runtime_module_to_dict(m, DEFAULT_ENGINE_DIR) for m in modules]
    blob = json.dumps(payload_modules, sort_keys=True, separators=(",", ":"))
    inventory = {
        "schema_version": _RUNTIME_LIBRARY_CACHE_SCHEMA_VERSION,
        "engine_root": str(DEFAULT_ENGINE_DIR),
        "fingerprint": "bundled-precompiled",
        "content_hash": "sha256:" + hashlib.sha256(blob.encode()).hexdigest(),
        "executable_only": True,
        "module_count": len(payload_modules),
        "modules": payload_modules,
    }
    target = staging_engine_dir / INVENTORY_NAME
    target.write_text(json.dumps(inventory), encoding="utf-8")
    fn_count = sum(len(m.functions) for m in modules)
    print(
        f"[bundle] baked library inventory: {len(modules)} modules / {fn_count} functions "
        f"→ engine/{INVENTORY_NAME}"
    )


# ── CPython home staging ──────────────────────────────────────────────────────

_PYTHON_HOME_PRUNE_DIRS = (
    "site-packages",  # installed packages — not needed for CPython init (the bulk)
    "test",
    "idlelib",
    "tkinter",
    "ensurepip",
    "turtledemo",
    "lib2to3",
    "pydoc_data",
)


def _stage_python_home(staging_dir: Path, lib_root: Path) -> None:
    """Stage a trimmed CPython home into the bundle at python/lib/pythonX.Y.

    The workers embed CPython and call Py_Initialize at startup, so they need a
    Python home (stdlib) on a clean machine — the daemon's bundle
    autoconfiguration points PYTHONHOME at <bundle>/python. Only what CPython
    init needs ships: the stdlib minus test suites, site-packages, and GUI/dev
    extras.
    """
    homes = sorted(
        entry
        for entry in lib_root.iterdir()
        if entry.is_dir() and entry.name.startswith("python3.") and (entry / "os.py").is_file()
    ) if lib_root.is_dir() else []
    if not homes:
        print(
            "[bundle] WARNING: no CPython home found under the lib root — the workers "
            "will need a system interpreter on the target machine."
        )
        return
    src_python_home = homes[-1]  # highest version if several exist
    dst = staging_dir / "python" / "lib" / src_python_home.name
    dst.mkdir(parents=True, exist_ok=True)

    def _ignore(directory: str, names: list[str]) -> set[str]:
        skip = {name for name in names if name == "__pycache__"}
        if Path(directory) == src_python_home:
            skip |= {name for name in names if name in _PYTHON_HOME_PRUNE_DIRS}
        skip |= {name for name in names if name == "tests" and (Path(directory) / name).is_dir()}
        return skip

    shutil.copytree(src_python_home, dst, ignore=_ignore, dirs_exist_ok=True)
    # An empty site-packages keeps site.py initialization happy.
    (dst / "site-packages").mkdir(exist_ok=True)
    total = sum(f.stat().st_size for f in dst.rglob("*") if f.is_file())
    print(
        f"[bundle] staged trimmed CPython home {src_python_home.name} "
        f"({total / 1e6:.0f} MB) → python/lib/{src_python_home.name}"
    )


# ── Full build ────────────────────────────────────────────────────────────────


def build_bundle(
    *,
    version: str,
    output_dir: Path,
    url_template: str,
    worker_package_dir: Path,
    lib_root: Path,
    skip_daemon_build: bool = False,
    prebuilt_daemon_dir: Path | None = None,
) -> dict[str, Any]:
    """End-to-end build. Returns a small report dict."""
    platform_tag = detect_platform_tag()
    output_dir.mkdir(parents=True, exist_ok=True)

    private_key_pem, key_source = resolve_signing_private_key()
    dev_signed = False
    if private_key_pem:
        public_key_pem = public_key_pem_from_private(private_key_pem)
        print(f"[bundle] signing with production key from {key_source} ({_ENV_PRIVATE_KEY}*)")
    else:
        dev_signed = True
        dev_dir = output_dir / "dev-keys"
        private_key_pem, public_key_pem = generate_dev_keypair(dev_dir)
        print(
            "\n"
            "############################################################\n"
            "# WARNING: no ALGENTA_BUNDLE_SIGNING_PRIVATE_KEY(_FILE)    #\n"
            "# set — signing with a locally generated DEV keypair at    #\n"
            f"#   {dev_dir}\n"
            "# DO NOT distribute this bundle. Production builds must    #\n"
            "# sign with the release key (CI secret).                   #\n"
            "############################################################\n"
        )

    with tempfile.TemporaryDirectory(prefix="algenta-bundle-") as tmp:
        work_dir = Path(tmp)
        staging = work_dir / "staging"
        staging.mkdir()

        # daemon/ — self-contained PyInstaller app
        if skip_daemon_build:
            daemon_src = prebuilt_daemon_dir
            if daemon_src is None or not daemon_src.is_dir():
                raise BundleBuildError("--skip-daemon-build requires --prebuilt-daemon-dir")
        else:
            daemon_src = build_daemon_with_pyinstaller(work_dir)
            verify_daemon_standalone(daemon_src)
        _copy_tree_dereferenced(daemon_src, staging / "daemon")

        # engine/ — the staged sharded workers + shard map + baked inventory
        engine_stub = _stage_engine(staging / "engine", worker_package_dir)
        if engine_stub:
            print(
                "[bundle] WARNING: staged workers are placeholders — bundle is "
                'marked "engine_stub": true (CI with the Mojo toolchain ships real workers)'
            )
        else:
            print("[bundle] real compiled shard workers detected — engine_stub: false")

        # python/ — trimmed stdlib home for the workers' embedded CPython
        if not engine_stub:
            _stage_python_home(staging, lib_root)

        tarball = output_dir / f"algenta-runtime-{version}-{platform_tag}.tar.gz"
        manifest = write_signed_bundle(
            staging,
            tarball,
            version=version,
            platform_tag=platform_tag,
            engine_stub=engine_stub,
            private_key_pem=private_key_pem,
        )

    (output_dir / PUBLIC_KEY_NAME).write_text(public_key_pem + "\n")
    metadata_path = write_bundle_metadata(
        tarball, version=version, platform_tag=platform_tag, url_template=url_template
    )

    report = {
        "tarball": str(tarball),
        "tarball_sha256": sha256_file(tarball),
        "tarball_size": tarball.stat().st_size,
        "metadata": str(metadata_path),
        "public_key": str(output_dir / PUBLIC_KEY_NAME),
        "platform": platform_tag,
        "version": version,
        "engine_stub": manifest["engine_stub"],
        "artifact_count": len(manifest["artifacts"]),
        "dev_signed": dev_signed,
    }
    print(f"[bundle] built {tarball} ({report['tarball_size'] / (1 << 20):.1f} MiB, "
          f"{report['artifact_count']} artifacts, engine_stub={report['engine_stub']}, "
          f"dev_signed={dev_signed})")
    return report


def _default_url_template() -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip() or "thyn-ai/algenta"
    return os.environ.get(
        "ALGENTA_BUNDLE_URL_TEMPLATE", DEFAULT_URL_TEMPLATE.format(repo=repo)
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the signed Algenta managed-runtime bundle."
    )
    parser.add_argument("--version", default=DEFAULT_VERSION,
                        help=f"runtime_bundle_version (default: {DEFAULT_VERSION})")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--worker-package",
        type=Path,
        default=DEFAULT_WORKER_PACKAGE_DIR,
        help="staged sharded worker package directory "
             "(scripts/stage_runtime_worker_package.py output)",
    )
    parser.add_argument(
        "--lib-root",
        type=Path,
        default=DEFAULT_LIB_ROOT,
        help="toolchain lib dir the trimmed CPython home is staged from",
    )
    parser.add_argument(
        "--url-template",
        default=_default_url_template(),
        help="download URL template with {version} and {platform} placeholders "
             "(default from ALGENTA_BUNDLE_URL_TEMPLATE / GITHUB_REPOSITORY)",
    )
    parser.add_argument(
        "--skip-daemon-build",
        action="store_true",
        help="skip PyInstaller and use --prebuilt-daemon-dir (CI reuse / debugging)",
    )
    parser.add_argument("--prebuilt-daemon-dir", type=Path, default=None)
    args = parser.parse_args()

    version = args.version.removeprefix("runtime-bundle-v")
    report = build_bundle(
        version=version,
        output_dir=args.output_dir,
        url_template=args.url_template,
        worker_package_dir=args.worker_package,
        lib_root=args.lib_root,
        skip_daemon_build=args.skip_daemon_build,
        prebuilt_daemon_dir=args.prebuilt_daemon_dir,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BundleBuildError as exc:
        print(f"[bundle] ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
