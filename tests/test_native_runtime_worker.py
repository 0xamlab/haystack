from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import types
from collections.abc import Iterable
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

_ALGENTA_PKG = Path(__file__).resolve().parents[1] / "packages" / "algenta"
if str(_ALGENTA_PKG) not in sys.path:
    sys.path.insert(0, str(_ALGENTA_PKG))

from algenta import paths  # noqa: E402
from algenta.native import loader as package_loader  # noqa: E402
from algenta.native import worker as package_worker  # noqa: E402

from apps.runtime import native_manifest  # noqa: E402
from apps.runtime import native_worker as app_worker  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("ALGENTA_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("ALGENTA_RUNTIME_FALLBACK_MODE", "deny")
    for name in (
        "ALGENTA_NATIVE_KERNEL",
        "ALGENTA_NATIVE_WORKER",
        "ALGENTA_RUNTIME_WORKER",
        "ALGENTA_MOJO_BINARY",
        "ALGENTA_RELEASE_PUBKEY",
        "ALGENTA_RELEASE_PUBKEY_FILE",
    ):
        monkeypatch.delenv(name, raising=False)
    package_loader._LIB = None
    package_loader._LIB_PATH = None
    package_loader._LIB_SOURCE = None
    package_loader._HANDLE = None
    yield
    package_loader._LIB = None
    package_loader._LIB_PATH = None
    package_loader._LIB_SOURCE = None
    package_loader._HANDLE = None


def _keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return key, pub


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_signed_bundle(
    directory: Path,
    *,
    platform_tag: str | None = None,
    extra_artifacts: Iterable[tuple[str, bytes]] = (),
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    worker = directory / package_worker.WORKER_BASENAME
    worker.write_text('#!/bin/sh\nprintf \'{"ok":true,"runtime":"worker"}\'\n', encoding="utf-8")
    worker.chmod(0o755)

    for name, content in extra_artifacts:
        artifact = directory / name
        artifact.write_bytes(content)
        artifact.chmod(0o644)

    artifacts = []
    for artifact in sorted(directory.iterdir(), key=lambda p: p.name):
        if artifact.name in {"manifest.json", "manifest.sig", "algenta_release_pub.pem"}:
            continue
        if artifact.is_file():
            artifacts.append(
                {
                    "name": artifact.name,
                    "sha256": _sha256(artifact),
                    "size_bytes": artifact.stat().st_size,
                }
            )
    manifest = json.dumps(
        {
            "format_version": 1,
            "platform": platform_tag or paths.platform_tag(),
            "artifacts": artifacts,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    key, pub = _keypair()
    (directory / "manifest.json").write_bytes(manifest)
    (directory / "manifest.sig").write_bytes(
        key.sign(manifest, padding.PKCS1v15(), hashes.SHA256())
    )
    (directory / "algenta_release_pub.pem").write_bytes(pub)
    return worker


def _patch_runtime_package(monkeypatch: pytest.MonkeyPatch, directory: Path) -> None:
    def _files(package: str):
        if package == "algenta_runtime_native":
            return directory
        raise ModuleNotFoundError(package)

    monkeypatch.setattr(package_worker.resources, "files", _files)
    monkeypatch.setattr(app_worker.resources, "files", _files)


def _install_hatchling_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    package_names = (
        "hatchling",
        "hatchling.builders",
        "hatchling.builders.hooks",
        "hatchling.builders.hooks.plugin",
    )
    for package_name in package_names:
        module = types.ModuleType(package_name)
        module.__path__ = []  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, package_name, module)

    interface = types.ModuleType("hatchling.builders.hooks.plugin.interface")

    class BuildHookInterface:
        root = ""

    interface.BuildHookInterface = BuildHookInterface
    monkeypatch.setitem(sys.modules, "hatchling.builders.hooks.plugin.interface", interface)


def test_runtime_native_build_hook_rejects_empty_wheel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_hatchling_stub(monkeypatch)
    monkeypatch.delenv("ALGENTA_BUNDLE_RUNTIME", raising=False)
    monkeypatch.delenv("ALGENTA_ALLOW_EMPTY_RUNTIME_NATIVE_WHEEL", raising=False)
    module_path = (
        Path(__file__).resolve().parents[1]
        / "packages"
        / "algenta-runtime-native"
        / "hatch_build.py"
    )
    spec = importlib.util.spec_from_file_location("test_algenta_hatch_build", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    hook = module.CustomBuildHook()
    hook.root = str(module_path.parent)

    with pytest.raises(RuntimeError, match="cannot be built as an empty wheel"):
        hook.initialize("standard", {})


def test_package_loader_executes_verified_bundled_worker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runtime_dir = tmp_path / "algenta_runtime_native"
    _write_signed_bundle(runtime_dir)
    _patch_runtime_package(monkeypatch, runtime_dir)
    monkeypatch.setattr(package_loader, "_resolve_native_lib", lambda: None)

    assert package_loader.available() is True
    result = package_loader.execute({"engine_type": "runtime_smoke", "runs": 1})
    assert result == {"ok": True, "runtime": "worker"}

    info = package_loader.info()
    assert info["runtime_source"] == "bundled runtime"
    assert info["mode"] == "bundled worker"
    assert info["loaded"] is True
    assert info["verified"] is True
    assert info["fallback"] == "deny"
    assert info["tcp_listeners"] == []


def test_package_worker_rejects_tampered_signed_dependency(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_dir = tmp_path / "algenta_runtime_native"
    _write_signed_bundle(
        runtime_dir, extra_artifacts=(("libKGENCompilerRTShared.so", b"original"),)
    )
    (runtime_dir / "libKGENCompilerRTShared.so").write_bytes(b"tampered")
    _patch_runtime_package(monkeypatch, runtime_dir)

    with pytest.raises(package_worker.NativeWorkerUnavailable) as exc_info:
        package_worker.require_worker(require_verified=True)

    msg = str(exc_info.value).lower()
    assert "bundled algenta runtime failed integrity verification" in msg
    for forbidden in ("install mojo", "install modular", "make build-mojo", "sidecar"):
        assert forbidden not in msg


def test_app_runtime_worker_resolves_verified_bundled_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_dir = tmp_path / "algenta_runtime_native"
    worker = _write_signed_bundle(runtime_dir)
    _patch_runtime_package(monkeypatch, runtime_dir)

    resolved = app_worker.require_native_worker(require_verified=True)

    assert resolved.source == "bundled runtime"
    assert resolved.path == worker
    assert resolved.verified is True
    assert resolved.executable is True


def test_native_manifest_verifies_every_signed_artifact(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "algenta_runtime_native"
    worker = _write_signed_bundle(
        runtime_dir, extra_artifacts=(("libAsyncRTMojoBindings.so", b"original"),)
    )

    native_manifest.verify_bundled_artifact(
        str(worker),
        str(runtime_dir / "manifest.json"),
        str(runtime_dir / "manifest.sig"),
        expected_name=worker.name,
    )

    (runtime_dir / "libAsyncRTMojoBindings.so").write_bytes(b"tampered")
    with pytest.raises(native_manifest.NativeVerificationError):
        native_manifest.verify_bundled_artifact(
            str(worker),
            str(runtime_dir / "manifest.json"),
            str(runtime_dir / "manifest.sig"),
            expected_name=worker.name,
        )


def test_package_worker_rejects_wrong_platform_bundle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_dir = tmp_path / "algenta_runtime_native"
    _write_signed_bundle(runtime_dir, platform_tag="linux-arm64")
    _patch_runtime_package(monkeypatch, runtime_dir)

    with pytest.raises(package_worker.NativeWorkerUnavailable) as exc_info:
        package_worker.require_worker(require_verified=True)

    assert "bundled Algenta runtime failed integrity verification" in str(exc_info.value)
