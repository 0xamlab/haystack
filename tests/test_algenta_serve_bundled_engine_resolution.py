"""`algenta serve`'s resolution of the CUDA engine BUNDLED IN THE RUNTIME WHEEL.

A NEW FILE rather than an extension of ``tests/test_algenta_serve_entry.py``: that file pins the
entry's contract (exit codes, refusal vocabulary, the engine's output literals, the resolution
chain's operator-facing steps). What is tested here is a different subject with different fixtures —
a fabricated but genuinely SIGNED runtime directory, and a host-capability predicate — and mixing
the two would make both harder to read. Nothing in the older file is edited.

THE BEHAVIOUR UNDER TEST. ``resolve_engine("cuda")`` walks
``--engine-binary`` → ``$ALGENTA_CUDA_ENGINE`` → ``$ALGENTA_CONFORM_CUDA_DRIVER`` →
``$BENCH_BIN_DIR`` → the bundled runtime → ``$PATH``. The bundled step is the only one that
consults evidence rather than presence, because it is the only one whose answer decides whether a
user runs the certified kernels: it requires the directory's signed manifest to verify, to say
``build_variant == "cuda"``, and this host to be cuda-capable by the gate's own predicate. Every
decline is recorded in ``EngineResolution.searched`` with its reason, so the resulting
``cuda_engine_binary_unresolved`` refusal says WHICH of the three said no.

Why the manifest and not the file's existence: the runtime wheel ships in two build variants whose
workers are otherwise indistinguishable — same names, same layout, same wheel filename. Before
``build_variant`` was recorded there was no way to tell them apart once unpacked, so "a binary
called conform_generate_cuda is present" was the only available evidence, and it is exactly the
evidence a CPU-variant wheel would also satisfy if anyone ever staged one there.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

ROOT = Path(__file__).resolve().parents[1]
_ALGENTA_PKG = ROOT / "packages" / "algenta"
for entry in (str(ROOT), str(_ALGENTA_PKG)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from algenta import paths  # noqa: E402
from algenta.native import worker as package_worker  # noqa: E402
from algenta.serve import engine as engine_module  # noqa: E402
from algenta.serve.engine import (  # noqa: E402
    CUDA_BUILD_VARIANT,
    CUDA_ENGINE_BINARY_NAME,
    engine_refusals,
    engine_stage,
    resolve_engine,
)
from algenta.serve.gating import NvidiaHostFacts  # noqa: E402

ENGINE_SOURCE = "benchmarks/llm_smoke/conform_generate_cuda.mojo"
ENGINE_BYTES = b"\x7fELF\x02\x01\x01\x00 fake bundled cuda engine\n"

# A host the cuda backend's declared floor accepts: linux, driver >= 580, compute capability >= 7.5
# (model_capabilities.BACKEND_HOST_REQUIREMENTS["cuda"]). Written out rather than probed, so these
# tests say something about an H200 box from a laptop with no NVIDIA driver.
CUDA_CAPABLE_HOST = NvidiaHostFacts(
    probed=True,
    probe_source="nvidia-smi",
    driver_version="580.65.06",
    driver_version_tuple=(580, 65, 6),
    device_count=1,
    device_names=("NVIDIA H200",),
    compute_capabilities=((9, 0),),
)
GPU_LESS_HOST = NvidiaHostFacts(probed=False, probe_error="no NVIDIA driver interface on this host")
LINUX = "linux"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _keypair() -> tuple[rsa.RSAPrivateKey, bytes]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return key, public


def _write_signed_bundle(
    directory: Path,
    *,
    build_variant: str | None = CUDA_BUILD_VARIANT,
    engine: bytes | None = ENGINE_BYTES,
    declare_engine: bool = True,
    platform_tag: str | None = None,
    trusted_key: rsa.RSAPrivateKey | None = None,
) -> Path:
    """Fabricate a runtime artifact directory that passes the SDK's OWN verifier.

    Not a mock: the manifest is really signed, the shard map is really well-formed, and
    ``algenta.native.worker._verify_bundled_worker`` really runs against it. A resolver test that
    stubbed verification would prove nothing about the path a user's wheel takes.
    """
    directory.mkdir(parents=True, exist_ok=True)
    workers = {
        package_worker.WORKER_BASENAME: b"#!/bin/sh\nexit 0\n",
        "algenta-runtime-worker-001": b"#!/bin/sh\nexit 0\n",
    }
    for name, content in workers.items():
        shard = directory / name
        shard.write_bytes(content)
        shard.chmod(0o755)
    (directory / package_worker.SHARD_MAP_NAME).write_text(
        json.dumps(
            {
                "schema_version": 1,
                "module_count": len(workers),
                "shard_count": len(workers),
                "default_worker": package_worker.WORKER_BASENAME,
                "module_workers": {
                    f"runtime_smoke_{index}": name for index, name in enumerate(sorted(workers))
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    if engine is not None:
        binary = directory / CUDA_ENGINE_BINARY_NAME
        binary.write_bytes(engine)
        binary.chmod(0o755)

    artifacts = [
        {
            "name": artifact.name,
            "sha256": _sha256(artifact),
            "size_bytes": artifact.stat().st_size,
        }
        for artifact in sorted(directory.iterdir(), key=lambda item: item.name)
        if artifact.is_file()
    ]
    payload: dict = {
        "format_version": 1,
        "platform": platform_tag or paths.platform_tag(),
        "artifacts": artifacts,
    }
    if build_variant is not None:
        payload["build_variant"] = build_variant
    if build_variant == CUDA_BUILD_VARIANT:
        payload["cuda_target"] = "sm_90a"
    if declare_engine and engine is not None:
        entry = next(item for item in artifacts if item["name"] == CUDA_ENGINE_BINARY_NAME)
        payload["engine"] = {
            "name": CUDA_ENGINE_BINARY_NAME,
            "sha256": entry["sha256"],
            "size_bytes": entry["size_bytes"],
            "source": ENGINE_SOURCE,
            "cuda_target": "sm_90a",
            "comptime_defines": ["ALGENTA_GPU", "ALGENTA_CUDA", "ALGENTA_TC_SHIM"],
            "host_shared_libraries": ["libcublas.so.12", "libcublasLt.so.12"],
        }

    manifest = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signing_key, public_pem = _keypair()
    (directory / "manifest.json").write_bytes(manifest)
    (directory / "manifest.sig").write_bytes(
        (trusted_key or signing_key).sign(manifest, padding.PKCS1v15(), hashes.SHA256())
    )
    (directory / "algenta_release_pub.pem").write_bytes(public_pem)
    return directory / CUDA_ENGINE_BINARY_NAME


@pytest.fixture
def bundled_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Point the SDK's runtime resolution at a fabricated signed bundle; yield its directory."""
    package_worker.shutdown()
    package_worker._VERIFIED_RUNTIME_DIRS.clear()
    directory = tmp_path / "algenta_runtime_native"
    _write_signed_bundle(directory)

    def _files(package: str):
        if package == "algenta_runtime_native":
            return directory
        raise ModuleNotFoundError(package)

    monkeypatch.setattr(package_worker.resources, "files", _files)
    monkeypatch.setenv("ALGENTA_RELEASE_PUBKEY_FILE", str(directory / "algenta_release_pub.pem"))
    monkeypatch.delenv("ALGENTA_RELEASE_PUBKEY", raising=False)
    # The rest of the chain must be empty, or a test could pass by resolving from $PATH.
    for name in ("ALGENTA_CUDA_ENGINE", "ALGENTA_CONFORM_CUDA_DRIVER", "BENCH_BIN_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(engine_module.shutil, "which", lambda _name: None)
    yield directory
    package_worker._VERIFIED_RUNTIME_DIRS.clear()


def _searched(resolution) -> str:
    return " | ".join(resolution.searched)


# ── the happy path: no flag, no environment, just an installed cuda wheel ─────


def test_the_bundled_engine_is_resolved_with_no_flag_on_a_cuda_host(bundled_runtime: Path) -> None:
    resolution = resolve_engine("cuda", environ={}, host=CUDA_CAPABLE_HOST, platform=LINUX)
    assert resolution.path == bundled_runtime / CUDA_ENGINE_BINARY_NAME
    assert resolution.source == "bundled runtime"


def test_the_stage_hands_the_gate_the_same_binary(bundled_runtime: Path) -> None:
    """What `plan_serve` does: one stage, host facts passed in, gate and launch agree."""
    stage = engine_stage(environ={}, host=CUDA_CAPABLE_HOST, platform=LINUX)
    assert stage.engine_refusals("cuda") == []
    assert stage.resolve("cuda").path == bundled_runtime / CUDA_ENGINE_BINARY_NAME


def test_a_probe_is_used_when_no_host_facts_are_supplied(bundled_runtime: Path) -> None:
    """The resolver must not shell out to nvidia-smi when the caller already knows the answer."""
    calls: list[int] = []

    def _probe():
        calls.append(1)
        return CUDA_CAPABLE_HOST

    resolution = resolve_engine("cuda", environ={}, host_probe=_probe, platform=LINUX)
    assert resolution.path is not None
    assert calls == [1]


# ── each of the three conditions, declined on its own ────────────────────────


def test_a_cpu_variant_wheel_declines_its_bundled_engine(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """THE central case: same file, same name, same directory — a different signed variant.

    A CPU-variant wheel that happened to carry a binary with this name must not be launched as a
    CUDA engine. The refusal names the variant it read, so an operator is told which of the three
    conditions said no.
    """
    directory = tmp_path / "algenta_runtime_native"
    _write_signed_bundle(directory, build_variant="cpu", declare_engine=False)
    _install_runtime(monkeypatch, directory)

    resolution = resolve_engine("cuda", environ={}, host=CUDA_CAPABLE_HOST, platform=LINUX)
    assert resolution.path is None
    assert "build_variant='cpu'" in _searched(resolution)
    assert "not 'cuda'" in _searched(resolution)


def test_a_manifest_with_no_variant_at_all_declines(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An OLD wheel is not read as either variant — it is declined, and says so."""
    directory = tmp_path / "algenta_runtime_native"
    _write_signed_bundle(directory, build_variant=None)
    _install_runtime(monkeypatch, directory)

    resolution = resolve_engine("cuda", environ={}, host=CUDA_CAPABLE_HOST, platform=LINUX)
    assert resolution.path is None
    assert "build_variant=None" in _searched(resolution)


def test_a_gpu_less_host_declines_the_bundled_engine(bundled_runtime: Path) -> None:
    """The binary is there and signed; the HOST is not able to run it. Say that, not "not found"."""
    resolution = resolve_engine("cuda", environ={}, host=GPU_LESS_HOST, platform=LINUX)
    assert resolution.path is None
    searched = _searched(resolution)
    assert "not cuda-capable" in searched
    assert "no_nvidia_gpu" in searched


def test_a_host_below_the_driver_floor_declines_the_bundled_engine(
    bundled_runtime: Path,
) -> None:
    old_driver = NvidiaHostFacts(
        probed=True,
        probe_source="nvidia-smi",
        driver_version="535.183.01",
        driver_version_tuple=(535, 183, 1),
        device_count=1,
        device_names=("NVIDIA A100",),
        compute_capabilities=((8, 0),),
    )
    resolution = resolve_engine("cuda", environ={}, host=old_driver, platform=LINUX)
    assert resolution.path is None
    assert "nvidia_driver_too_old" in _searched(resolution)


def test_a_non_linux_platform_declines_the_bundled_engine(bundled_runtime: Path) -> None:
    resolution = resolve_engine("cuda", environ={}, host=CUDA_CAPABLE_HOST, platform="darwin")
    assert resolution.path is None
    assert "unsupported_platform" in _searched(resolution)


def test_a_declared_but_absent_engine_is_refused_by_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    directory = tmp_path / "algenta_runtime_native"
    _write_signed_bundle(directory, engine=None, declare_engine=False)
    _install_runtime(monkeypatch, directory)

    resolution = resolve_engine("cuda", environ={}, host=CUDA_CAPABLE_HOST, platform=LINUX)
    assert resolution.path is None
    assert CUDA_ENGINE_BINARY_NAME in _searched(resolution)


# ── integrity: the manifest must be TRUSTED, not merely present ───────────────


def test_a_tampered_bundled_engine_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    directory = tmp_path / "algenta_runtime_native"
    _write_signed_bundle(directory)
    _install_runtime(monkeypatch, directory)
    # One byte of the engine, after the manifest that covers it was signed.
    binary = directory / CUDA_ENGINE_BINARY_NAME
    binary.write_bytes(ENGINE_BYTES + b"tampered")
    binary.chmod(0o755)

    resolution = resolve_engine("cuda", environ={}, host=CUDA_CAPABLE_HOST, platform=LINUX)
    assert resolution.path is None
    assert "failed integrity verification" in _searched(resolution)


def test_a_manifest_signed_by_another_key_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The bundle ships its own public key; the trust anchor must be the embedded one."""
    directory = tmp_path / "algenta_runtime_native"
    stranger = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    _write_signed_bundle(directory, trusted_key=stranger)
    _install_runtime(monkeypatch, directory)

    resolution = resolve_engine("cuda", environ={}, host=CUDA_CAPABLE_HOST, platform=LINUX)
    assert resolution.path is None
    assert "failed integrity verification" in _searched(resolution)


def test_an_unsigned_manifest_beside_a_signed_runtime_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    directory = tmp_path / "algenta_runtime_native"
    _write_signed_bundle(directory)
    _install_runtime(monkeypatch, directory)
    (directory / "manifest.sig").unlink()

    resolution = resolve_engine("cuda", environ={}, host=CUDA_CAPABLE_HOST, platform=LINUX)
    assert resolution.path is None
    assert "failed integrity verification" in _searched(resolution)


# ── what the chain does NOT gate ─────────────────────────────────────────────


def test_an_explicit_override_wins_without_consulting_the_manifest(
    bundled_runtime: Path, tmp_path: Path
) -> None:
    """Naming a binary IS the operator taking responsibility for it.

    This is the escape hatch on a host whose probe is wrong, and on a developer build that was never
    staged into a wheel. It must keep working even when the bundled engine is being declined.
    """
    override = tmp_path / "my-engine"
    override.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    override.chmod(0o755)

    resolution = resolve_engine(
        "cuda", override=override, environ={}, host=GPU_LESS_HOST, platform=LINUX
    )
    assert resolution.path == override
    assert resolution.source == "--engine-binary"


def test_an_env_override_wins_on_a_gpu_less_host(bundled_runtime: Path, tmp_path: Path) -> None:
    override = tmp_path / "env-engine"
    override.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    override.chmod(0o755)

    resolution = resolve_engine(
        "cuda",
        environ={"ALGENTA_CUDA_ENGINE": str(override)},
        host=GPU_LESS_HOST,
        platform=LINUX,
    )
    assert resolution.path == override
    assert resolution.source == "$ALGENTA_CUDA_ENGINE"


def test_an_unsigned_dev_directory_still_resolves_on_presence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A developer's own build directory has no signed manifest, and must not start needing one.

    ``$BENCH_BIN_DIR`` and ``$PATH`` already resolve on presence alone; the repo's ``mojo_build/``
    and an operator's ``ALGENTA_NATIVE_WORKER`` parent are the same kind of directory. Only the
    PACKAGED runtime — the candidate the SDK itself marks ``must_verify`` — is held to the manifest.
    """
    dev_dir = tmp_path / "mojo_build"
    dev_dir.mkdir()
    (dev_dir / "simulate").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (dev_dir / "simulate").chmod(0o755)
    engine = dev_dir / CUDA_ENGINE_BINARY_NAME
    engine.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    engine.chmod(0o755)

    monkeypatch.setenv("ALGENTA_NATIVE_WORKER", str(dev_dir / "simulate"))
    monkeypatch.delenv("ALGENTA_CUDA_ENGINE", raising=False)
    monkeypatch.delenv("ALGENTA_CONFORM_CUDA_DRIVER", raising=False)
    monkeypatch.delenv("BENCH_BIN_DIR", raising=False)
    monkeypatch.setattr(engine_module.shutil, "which", lambda _name: None)

    resolution = resolve_engine("cuda", environ={}, host=GPU_LESS_HOST, platform=LINUX)
    assert resolution.path == engine
    assert resolution.source == "bundled runtime"


# ── the refusal an operator actually reads ───────────────────────────────────


def test_the_refusal_names_the_manifest_condition(bundled_runtime: Path) -> None:
    resolution = resolve_engine("cuda", environ={}, host=GPU_LESS_HOST, platform=LINUX)
    refusals = engine_refusals("cuda", resolution=resolution)
    assert [refusal.code for refusal in refusals] == ["cuda_engine_binary_unresolved"]
    message = refusals[0].message()
    # The chain the operator is told about, and the two conditions that gate its last step.
    for expected in (
        "ALGENTA_CUDA_ENGINE",
        "ALGENTA_CONFORM_CUDA_DRIVER",
        "BENCH_BIN_DIR",
        "manifest.json",
        "build_variant",
        "cuda-capable",
    ):
        assert expected in message, expected


def test_nothing_resolves_when_no_runtime_is_installed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Regression guard on the pre-existing behaviour: an absent runtime is a typed refusal."""
    empty = tmp_path / "nowhere"
    empty.mkdir()

    def _files(package: str):
        raise ModuleNotFoundError(package)

    monkeypatch.setattr(package_worker.resources, "files", _files)
    monkeypatch.setattr(package_worker, "_repo_root", lambda: empty)
    monkeypatch.setattr(engine_module.shutil, "which", lambda _name: None)
    for name in (
        "ALGENTA_CUDA_ENGINE",
        "ALGENTA_CONFORM_CUDA_DRIVER",
        "BENCH_BIN_DIR",
        "ALGENTA_NATIVE_WORKER",
        "ALGENTA_RUNTIME_WORKER",
        "ALGENTA_MOJO_BINARY",
    ):
        monkeypatch.delenv(name, raising=False)

    resolution = resolve_engine("cuda", environ={}, host=CUDA_CAPABLE_HOST, platform=LINUX)
    assert resolution.path is None
    assert [refusal.code for refusal in engine_refusals("cuda", resolution=resolution)] == [
        "cuda_engine_binary_unresolved"
    ]


def _install_runtime(monkeypatch: pytest.MonkeyPatch, directory: Path) -> None:
    """Point the SDK's runtime resolution at `directory` and empty the rest of the chain."""
    package_worker.shutdown()
    package_worker._VERIFIED_RUNTIME_DIRS.clear()

    def _files(package: str):
        if package == "algenta_runtime_native":
            return directory
        raise ModuleNotFoundError(package)

    monkeypatch.setattr(package_worker.resources, "files", _files)
    monkeypatch.setenv("ALGENTA_RELEASE_PUBKEY_FILE", str(directory / "algenta_release_pub.pem"))
    monkeypatch.delenv("ALGENTA_RELEASE_PUBKEY", raising=False)
    for name in ("ALGENTA_CUDA_ENGINE", "ALGENTA_CONFORM_CUDA_DRIVER", "BENCH_BIN_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(engine_module.shutil, "which", lambda _name: None)
    monkeypatch.setattr(package_worker, "_repo_root", lambda: directory / "no-repo")
