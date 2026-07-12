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
    package_worker.shutdown()
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
    package_worker.shutdown()
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
    module_workers: dict[str, str] | None = None,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    worker = directory / package_worker.WORKER_BASENAME
    worker.write_text('#!/bin/sh\nprintf \'{"ok":true,"runtime":"worker"}\'\n', encoding="utf-8")
    worker.chmod(0o755)

    routes = module_workers or {"runtime_smoke": package_worker.WORKER_BASENAME}
    for worker_name in sorted(set(routes.values())):
        shard_worker = directory / worker_name
        if not shard_worker.exists():
            shard_worker.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            shard_worker.chmod(0o755)
    (directory / package_worker.SHARD_MAP_NAME).write_text(
        json.dumps(
            {
                "schema_version": 1,
                "module_count": len(routes),
                "shard_count": len(set(routes.values())),
                "default_worker": package_worker.WORKER_BASENAME,
                "module_workers": routes,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

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
    monkeypatch.setenv(
        "ALGENTA_RELEASE_PUBKEY_FILE", str(directory / "algenta_release_pub.pem")
    )


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

    assert module._platform_wheel_tag().startswith("py3-none-")

    with pytest.raises(RuntimeError, match="cannot be built as an empty wheel"):
        hook.initialize("standard", {})


def test_runtime_native_build_hook_packages_every_signed_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_hatchling_stub(monkeypatch)
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    artifact_names = (
        package_worker.WORKER_BASENAME,
        package_worker.SHARD_MAP_NAME,
        "libKGENCompilerRTShared.dylib",
    )
    for name in artifact_names:
        (runtime_dir / name).write_bytes(b"artifact")
    (runtime_dir / "manifest.json").write_text(
        json.dumps({"artifacts": [{"name": name} for name in artifact_names]}),
        encoding="utf-8",
    )
    (runtime_dir / "manifest.sig").write_bytes(b"signature")
    (runtime_dir / "algenta_release_pub.pem").write_bytes(b"public key")
    monkeypatch.setenv("ALGENTA_BUNDLE_RUNTIME", "1")
    monkeypatch.setenv("ALGENTA_RUNTIME_SRC", str(runtime_dir))

    module_path = (
        Path(__file__).resolve().parents[1]
        / "packages"
        / "algenta-runtime-native"
        / "hatch_build.py"
    )
    spec = importlib.util.spec_from_file_location("test_algenta_hatch_build_complete", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    hook = module.CustomBuildHook()
    hook.root = str(module_path.parent)
    build_data: dict = {}

    hook.initialize("standard", build_data)

    included = set(build_data["force_include"].values())
    assert {f"algenta_runtime_native/{name}" for name in artifact_names} <= included
    assert build_data["tag"].startswith("py3-none-")
    assert build_data["pure_python"] is False
    assert build_data["infer_tag"] is False


def test_package_loader_executes_verified_bundled_worker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runtime_dir = tmp_path / "algenta_runtime_native"
    _write_signed_bundle(runtime_dir)
    _patch_runtime_package(monkeypatch, runtime_dir)
    monkeypatch.setattr(package_loader, "_resolve_native_lib", lambda: None)

    class _FakeSession:
        worker_path = runtime_dir / package_worker.WORKER_BASENAME
        ready = True

        @staticmethod
        def execute(request: dict, timeout: float) -> dict:
            assert request == {"engine_type": "runtime_smoke", "runs": 1}
            assert timeout == 60.0
            return {"ok": True, "runtime": "worker"}

    monkeypatch.setattr(package_worker, "_session_for", lambda resolution: _FakeSession())

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


def test_worker_frame_round_trip_over_private_socket() -> None:
    client, server = package_worker.socket.socketpair()
    try:
        expected = {"engine_type": "library_execute", "args": [1.0, 2.0]}
        package_worker._send_frame(client, expected)
        assert package_worker._recv_frame(server) == expected
    finally:
        client.close()
        server.close()


def test_bundled_worker_uses_running_python_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("PYTHONHOME", "/untrusted/python")
    resolution = package_worker.NativeWorkerResolution(
        source="bundled runtime",
        path=tmp_path / package_worker.WORKER_BASENAME,
        verified=True,
    )

    env = package_worker._worker_environment(resolution)

    assert env["PYTHONHOME"] == sys.base_prefix
    assert env is not package_worker.os.environ


def test_override_worker_preserves_explicit_python_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("PYTHONHOME", "/internal/python")
    resolution = package_worker.NativeWorkerResolution(
        source="env override",
        path=tmp_path / package_worker.WORKER_BASENAME,
        verified=False,
    )

    env = package_worker._worker_environment(resolution)

    assert env["PYTHONHOME"] == "/internal/python"


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


def test_package_worker_rejects_untrusted_runtime_release_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_dir = tmp_path / "algenta_runtime_native"
    _write_signed_bundle(runtime_dir)
    _patch_runtime_package(monkeypatch, runtime_dir)
    _, untrusted_pub = _keypair()
    monkeypatch.setenv("ALGENTA_RELEASE_PUBKEY", untrusted_pub.decode("ascii"))

    with pytest.raises(
        package_worker.verify.VerificationError,
        match="does not match the embedded Algenta trust anchor",
    ):
        package_worker._verify_bundled_worker(
            runtime_dir / package_worker.WORKER_BASENAME
        )

    with pytest.raises(package_worker.NativeWorkerUnavailable) as exc_info:
        package_worker.require_worker(require_verified=True)

    assert "failed integrity verification" in str(exc_info.value)
    assert "trust anchor" not in str(exc_info.value)


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


def test_native_manifest_verifies_every_signed_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_dir = tmp_path / "algenta_runtime_native"
    worker = _write_signed_bundle(
        runtime_dir, extra_artifacts=(("libAsyncRTMojoBindings.so", b"original"),)
    )
    monkeypatch.setenv(
        "ALGENTA_RELEASE_PUBKEY_FILE", str(runtime_dir / "algenta_release_pub.pem")
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


def test_package_worker_routes_modules_to_signed_shards(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_dir = tmp_path / "algenta_runtime_native"
    shard_name = "algenta-runtime-worker-001"
    _write_signed_bundle(
        runtime_dir,
        module_workers={
            "alpha": package_worker.WORKER_BASENAME,
            "vector_kernels.dot": shard_name,
        },
    )
    _patch_runtime_package(monkeypatch, runtime_dir)

    default_resolution = package_worker.require_worker(require_verified=True)
    shard_resolution = package_worker.require_worker(
        module_name="vector_kernels.dot", require_verified=True
    )

    assert default_resolution.path.name == package_worker.WORKER_BASENAME
    assert shard_resolution.path.name == shard_name
    assert package_worker.runtime_module_filter() == ("alpha", "vector_kernels.dot")
    assert package_worker._session_for(default_resolution) is not package_worker._session_for(
        shard_resolution
    )


def test_package_worker_rejects_tampered_shard_map(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_dir = tmp_path / "algenta_runtime_native"
    _write_signed_bundle(runtime_dir)
    (runtime_dir / package_worker.SHARD_MAP_NAME).write_text("{}", encoding="utf-8")
    _patch_runtime_package(monkeypatch, runtime_dir)

    with pytest.raises(package_worker.NativeWorkerUnavailable, match="integrity verification"):
        package_worker.require_worker(require_verified=True)
