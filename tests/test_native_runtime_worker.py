from __future__ import annotations

import hashlib
import importlib.util
import json
import os
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

    monkeypatch.setattr(
        module,
        "sys_tags",
        lambda: iter([types.SimpleNamespace(platform="manylinux_2_35_x86_64")]),
    )
    assert module._platform_wheel_tag() == "py3-none-manylinux_2_35_x86_64"


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


def test_worker_environment_prefers_caller_prefix_libpython(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # The embedded interpreter must be the SAME distribution as the stdlib + C extension modules
    # it loads from PYTHONHOME. The wheel's bundled libpython comes from the build toolchain and
    # mismatches the caller's extensions (observed: `import socket` -> "failed to create socket"
    # on bare amd64 containers), so the launcher prefers the caller's own libpython and forces
    # the dynamic loader to it (the worker's $ORIGIN rpath otherwise loads the bundled copy).
    monkeypatch.delenv("MOJO_PYTHON_LIBRARY", raising=False)
    monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
    base_prefix = tmp_path / "base_prefix"
    (base_prefix / "lib").mkdir(parents=True)
    caller_libpython = base_prefix / "lib" / "libpython3.14.so.1.0"
    caller_libpython.write_bytes(b"")
    monkeypatch.setattr(sys, "base_prefix", str(base_prefix))

    artifact_dir = tmp_path / "runtime"
    artifact_dir.mkdir()
    bundled = artifact_dir / "libpython3.14.so.1.0"
    bundled.write_bytes(b"")
    worker_path = artifact_dir / package_worker.WORKER_BASENAME
    worker_path.write_bytes(b"")
    resolution = package_worker.NativeWorkerResolution("bundled runtime", worker_path, True)

    env = package_worker._worker_environment(resolution)

    assert env["MOJO_PYTHON_LIBRARY"] == str(caller_libpython)
    assert env["LD_LIBRARY_PATH"].split(os.pathsep)[0] == str(base_prefix / "lib")


def test_worker_environment_falls_back_to_bundled_libpython(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Caller interpreters that ship no shared libpython (static builds) fall back to the copy
    # bundled beside the worker, keeping the runtime self-contained.
    monkeypatch.delenv("MOJO_PYTHON_LIBRARY", raising=False)
    base_prefix = tmp_path / "base_prefix"
    base_prefix.mkdir()
    monkeypatch.setattr(sys, "base_prefix", str(base_prefix))

    artifact_dir = tmp_path / "runtime"
    artifact_dir.mkdir()
    bundled = artifact_dir / "libpython3.14.so.1.0"
    bundled.write_bytes(b"")
    worker_path = artifact_dir / package_worker.WORKER_BASENAME
    worker_path.write_bytes(b"")
    resolution = package_worker.NativeWorkerResolution("bundled runtime", worker_path, True)

    env = package_worker._worker_environment(resolution)

    assert env["MOJO_PYTHON_LIBRARY"] == str(bundled)


def test_worker_environment_keeps_caller_mojo_python_library(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("MOJO_PYTHON_LIBRARY", "/custom/libpython3.14.so")
    artifact_dir = tmp_path / "runtime"
    artifact_dir.mkdir()
    (artifact_dir / "libpython3.14.so.1.0").write_bytes(b"")
    worker_path = artifact_dir / package_worker.WORKER_BASENAME
    worker_path.write_bytes(b"")
    resolution = package_worker.NativeWorkerResolution("bundled runtime", worker_path, True)

    env = package_worker._worker_environment(resolution)

    assert env["MOJO_PYTHON_LIBRARY"] == "/custom/libpython3.14.so"


def test_worker_environment_omits_hint_without_any_libpython(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("MOJO_PYTHON_LIBRARY", raising=False)
    base_prefix = tmp_path / "base_prefix"
    base_prefix.mkdir()
    monkeypatch.setattr(sys, "base_prefix", str(base_prefix))

    artifact_dir = tmp_path / "runtime"
    artifact_dir.mkdir()
    worker_path = artifact_dir / package_worker.WORKER_BASENAME
    worker_path.write_bytes(b"")
    resolution = package_worker.NativeWorkerResolution("bundled runtime", worker_path, True)

    env = package_worker._worker_environment(resolution)

    assert "MOJO_PYTHON_LIBRARY" not in env


def test_worker_environment_non_bundled_source_gets_no_python_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("PYTHONHOME", raising=False)
    monkeypatch.delenv("MOJO_PYTHON_LIBRARY", raising=False)
    worker_path = tmp_path / "system-worker"
    worker_path.write_bytes(b"")
    resolution = package_worker.NativeWorkerResolution("system worker", worker_path, True)

    env = package_worker._worker_environment(resolution)

    assert "PYTHONHOME" not in env
    assert "MOJO_PYTHON_LIBRARY" not in env


# ── multiarch libpython discovery (the Ubuntu/Debian out-of-the-box defect) ────────────────────
#
# Debian/Ubuntu keep shared libraries in lib/<multiarch-triplet>/, not lib/. The launcher used
# to glob <prefix>/lib/ only, so on a plain Ubuntu server it never saw the distro's
# /usr/lib/x86_64-linux-gnu/libpython3.14.so.1.0, the worker loaded the wheel's bundled
# toolchain libpython against deadsnakes' stdlib, and `import socket` killed it before it
# could bind (doctor said READY anyway). Discovery must see the multiarch layout.


@pytest.mark.parametrize("triplet", ["x86_64-linux-gnu", "aarch64-linux-gnu"])
def test_prefix_libpython_finds_debian_multiarch_layout(
    tmp_path: Path, triplet: str
) -> None:
    prefix = tmp_path / "prefix"
    multiarch_dir = prefix / "lib" / triplet
    multiarch_dir.mkdir(parents=True)
    system_libpython = multiarch_dir / "libpython3.14.so.1.0"
    system_libpython.write_bytes(b"")

    found = package_worker._prefix_libpython(prefix, "3.14")

    assert found == system_libpython


def test_prefix_libpython_finds_lib64_layout(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    (prefix / "lib64").mkdir(parents=True)
    libpython = prefix / "lib64" / "libpython3.14.so.1.0"
    libpython.write_bytes(b"")

    assert package_worker._prefix_libpython(prefix, "3.14") == libpython


def test_prefix_libpython_keeps_plain_lib_layout(tmp_path: Path) -> None:
    # The historical layout (macOS frameworks, conda/pixi envs) must keep working.
    prefix = tmp_path / "prefix"
    (prefix / "lib").mkdir(parents=True)
    libpython = prefix / "lib" / "libpython3.14.dylib"
    libpython.write_bytes(b"")

    assert package_worker._prefix_libpython(prefix, "3.14") == libpython


def test_prefix_libpython_none_when_no_shared_library(tmp_path: Path) -> None:
    # deadsnakes without apt's libpython package: the prefix exists, even with a multiarch
    # dir, but no shared libpython is installed — discovery must say so (None), not invent one.
    prefix = tmp_path / "prefix"
    (prefix / "lib" / "x86_64-linux-gnu").mkdir(parents=True)
    (prefix / "lib" / "python3.14").mkdir(parents=True)  # stdlib dir is not a shared lib

    assert package_worker._prefix_libpython(prefix, "3.14") is None


def test_prefix_libpython_filters_by_required_version(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    multiarch_dir = prefix / "lib" / "x86_64-linux-gnu"
    multiarch_dir.mkdir(parents=True)
    wrong_version = multiarch_dir / "libpython3.13.so.1.0"
    wrong_version.write_bytes(b"")

    assert package_worker._prefix_libpython(prefix, "3.14") is None
    assert package_worker._prefix_libpython(prefix, "3.13") == wrong_version
    # No version requirement keeps the historical any-python-3 behaviour.
    assert package_worker._prefix_libpython(prefix) == wrong_version


def test_prefix_libpython_version_filter_is_exact_major_minor(tmp_path: Path) -> None:
    # Required 3.1 must not claim libpython3.14 (prefix match on digits alone is a bug).
    assert package_worker._is_libpython_for_version("libpython3.14.so.1.0", "3.1") is False
    assert package_worker._is_libpython_for_version("libpython3.14.so.1.0", "3.14") is True
    assert package_worker._is_libpython_for_version("libpython3.14.dylib", "3.14") is True
    assert package_worker._is_libpython_for_version("libpython3.14m.so.1.0", "3.14") is True
    assert package_worker._is_libpython_for_version("libpython2.7.so.1.0", "3.14") is False


def test_required_libpython_version_reads_bundled_artifact(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "runtime"
    artifact_dir.mkdir()
    (artifact_dir / "libpython3.14.so.1.0").write_bytes(b"")

    assert package_worker._required_libpython_version(artifact_dir) == "3.14"


def test_required_libpython_version_falls_back_to_caller(tmp_path: Path) -> None:
    empty_dir = tmp_path / "runtime"
    empty_dir.mkdir()

    expected = f"{sys.version_info.major}.{sys.version_info.minor}"
    assert package_worker._required_libpython_version(empty_dir) == expected
    assert package_worker._required_libpython_version(None) == expected


def _bundled_runtime_resolution(
    tmp_path: Path, *, bundled_libpython: str | None
) -> package_worker.NativeWorkerResolution:
    artifact_dir = tmp_path / "runtime"
    artifact_dir.mkdir()
    if bundled_libpython is not None:
        (artifact_dir / bundled_libpython).write_bytes(b"")
    worker_path = artifact_dir / package_worker.WORKER_BASENAME
    worker_path.write_bytes(b"")
    return package_worker.NativeWorkerResolution("bundled runtime", worker_path, True)


def test_worker_environment_prefers_multiarch_system_libpython(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # THE field defect: on Ubuntu the system libpython lives in lib/x86_64-linux-gnu/, which
    # the old <prefix>/lib/-only glob never searched, so the worker kept loading the wheel's
    # bundled toolchain libpython (ABI mismatch -> dead worker). The launcher must find the
    # multiarch copy, force the dynamic loader to it via LD_LIBRARY_PATH (searched BEFORE the
    # worker's $ORIGIN DT_RUNPATH), and set MOJO_PYTHON_LIBRARY for binaries that honor it.
    monkeypatch.delenv("MOJO_PYTHON_LIBRARY", raising=False)
    monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
    base_prefix = tmp_path / "base_prefix"
    system_libpython = base_prefix / "lib" / "x86_64-linux-gnu" / "libpython3.14.so.1.0"
    system_libpython.parent.mkdir(parents=True)
    system_libpython.write_bytes(b"")
    monkeypatch.setattr(sys, "base_prefix", str(base_prefix))

    resolution = _bundled_runtime_resolution(tmp_path, bundled_libpython="libpython3.14.so.1.0")

    env = package_worker._worker_environment(resolution)

    assert env["MOJO_PYTHON_LIBRARY"] == str(system_libpython)
    assert env["LD_LIBRARY_PATH"].split(os.pathsep)[0] == str(system_libpython.parent)


def test_worker_environment_ignores_wrong_version_system_libpython(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # A system libpython for a DIFFERENT Python (e.g. the distro's 3.10/3.13) must not be
    # forced into the worker: keep the bundled copy and leave LD_LIBRARY_PATH alone.
    monkeypatch.delenv("MOJO_PYTHON_LIBRARY", raising=False)
    monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
    base_prefix = tmp_path / "base_prefix"
    wrong_libpython = base_prefix / "lib" / "x86_64-linux-gnu" / "libpython3.13.so.1.0"
    wrong_libpython.parent.mkdir(parents=True)
    wrong_libpython.write_bytes(b"")
    monkeypatch.setattr(sys, "base_prefix", str(base_prefix))

    resolution = _bundled_runtime_resolution(tmp_path, bundled_libpython="libpython3.14.so.1.0")

    env = package_worker._worker_environment(resolution)

    bundled = resolution.path.parent / "libpython3.14.so.1.0"
    assert env["MOJO_PYTHON_LIBRARY"] == str(bundled)
    assert "LD_LIBRARY_PATH" not in env
