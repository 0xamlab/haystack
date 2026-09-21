"""The signed bundled-runtime manifest's BUILD_VARIANT + ENGINE schema.

WHY THIS FILE EXISTS. The runtime wheel ships in two build variants whose contents are
otherwise indistinguishable: both unpack to ``algenta_runtime_native/algenta-runtime-worker*``
plus the same library closure, and — because the CUDA lane is the same package on the same
platform tag — both even have the SAME WHEEL FILENAME. Before this schema there was no
machine-readable way to tell a CPU-built worker from a CUDA-built one once unpacked, which is
exactly the ambiguity ``algenta serve --backend cuda`` has to resolve before it will launch the
engine binary bundled beside the worker.

These tests run on CPU, with no GPU, no CUDA toolkit and no Linux: the manifest is data, so its
schema is provable anywhere, and the build that produces it
(``.github/scripts/build_cuda_engine_linux_amd64.sh``) is the part that needs a runner.

The invariants asserted here, and why each one is load-bearing:

* ``build_variant`` is REQUIRED and closed over ``{cpu, cuda}``. An absent or unknown variant is
  refused rather than defaulted, because defaulting is how a kernel-free wheel gets shipped as a
  CUDA one — the failure this whole workstream exists to stop.
* an ``engine`` block may only appear in a ``cuda`` manifest, and only for an artifact that is
  actually staged, with a digest that matches the artifact list. The engine's sha256 appears in
  TWO places in one payload; if they can disagree, the signature covers a contradiction.
* the engine's ``host_shared_libraries`` are sonames, never paths. They are the declaration the
  build's auditwheel gate is checked against: cuBLAS is ~581 MB against a 42 MB wheel and is in no
  manylinux allowlist, so it is host-provided and MUST be named — an unnamed external library is
  an undeclared runtime failure on a user's machine.
* the canonical rendering is byte-stable, because the release signature covers those exact bytes
  and a re-serialization would invalidate it.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.generate_runtime_bundle_manifest as bundle_manifest  # noqa: E402
import scripts.validate_runtime_release as release_validation  # noqa: E402

ENGINE_NAME = "conform_generate_cuda"
ENGINE_SOURCE = "benchmarks/llm_smoke/conform_generate_cuda.mojo"
# The round-19 certified default stack (BASE + R5 + R6), verbatim.
CERTIFIED_DEFINES = (
    "ALGENTA_GPU",
    "ALGENTA_CUDA",
    "ALGENTA_STAGE_6144",
    "ALGENTA_G3_GEGLU_U4",
    "ALGENTA_TC_SHIM",
    "ALGENTA_G3_ATTN_FLASH",
    "ALGENTA_G3_PF_TCATTN",
    "ALGENTA_G3_STREAM",
    "ALGENTA_G3_PF_FA",
    "ALGENTA_G3_PF_F16ATTN",
    "ALGENTA_G3_PF_F16NORM",
    "ALGENTA_G3_PF_F16MLP",
    "ALGENTA_G3_PF_ROPE2",
    "ALGENTA_G3_PF_FA2",
    "ALGENTA_G3_PF_KV16",
    "ALGENTA_G3_PF_BN32",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stage_runtime(directory: Path, *, engine: bytes | None = None) -> Path:
    """A minimal staged runtime directory: two workers, a shard map, optionally the engine.

    Two workers because the generator asserts the bounded-shard invariant (the default worker plus
    at least one shard) — the same assertion the inline heredoc it replaced made.
    """
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "algenta-runtime-worker").write_bytes(b"#!/bin/sh\nexit 0\n")
    (directory / "algenta-runtime-worker-001").write_bytes(b"#!/bin/sh\nexit 0\n")
    (directory / "runtime-shards.json").write_text(
        json.dumps({"schema_version": 1, "default_worker": "algenta-runtime-worker"}),
        encoding="utf-8",
    )
    if engine is not None:
        path = directory / ENGINE_NAME
        path.write_bytes(engine)
        path.chmod(0o755)
    return directory


def _engine_block(directory: Path) -> dict:
    path = directory / ENGINE_NAME
    return bundle_manifest.build_engine_block(
        name=ENGINE_NAME,
        sha256=_sha256(path),
        size_bytes=path.stat().st_size,
        source=ENGINE_SOURCE,
        cuda_target="sm_90a",
        comptime_defines=CERTIFIED_DEFINES,
        host_shared_libraries=("libcublas.so.12", "libcublasLt.so.12"),
        shim_object="tc_shim.cu@sm_90a sha256:deadbeefdeadbeef",
    )


# ── the variant is what distinguishes the two wheels ─────────────────────────


def test_a_cpu_manifest_declares_its_variant_and_bundles_no_engine(tmp_path: Path) -> None:
    directory = _stage_runtime(tmp_path / "cpu")
    payload = bundle_manifest.build_bundle_manifest(
        artifact_dir=directory, platform="linux-x86_64", build_variant="cpu"
    )
    assert payload["build_variant"] == "cpu"
    assert payload["format_version"] == bundle_manifest.MANIFEST_FORMAT_VERSION
    assert payload["platform"] == "linux-x86_64"
    assert "engine" not in payload
    assert "cuda_target" not in payload
    assert {entry["name"] for entry in payload["artifacts"]} == {
        "algenta-runtime-worker",
        "algenta-runtime-worker-001",
        "runtime-shards.json",
    }


def test_a_cuda_manifest_declares_the_engine_and_its_host_libraries(tmp_path: Path) -> None:
    directory = _stage_runtime(tmp_path / "cuda", engine=b"\x7fELF fake engine")
    engine = _engine_block(directory)
    payload = bundle_manifest.build_bundle_manifest(
        artifact_dir=directory,
        platform="linux-x86_64",
        build_variant="cuda",
        engine=engine,
        cuda_target="sm_90a",
    )
    bundle_manifest.validate_bundle_manifest(payload)

    assert payload["build_variant"] == "cuda"
    assert payload["cuda_target"] == "sm_90a"
    declared = payload["engine"]
    assert declared["name"] == ENGINE_NAME
    assert declared["source"] == ENGINE_SOURCE
    assert declared["cuda_target"] == "sm_90a"
    assert tuple(declared["comptime_defines"]) == CERTIFIED_DEFINES
    assert declared["host_shared_libraries"] == ["libcublas.so.12", "libcublasLt.so.12"]
    # The engine's digest is stated twice in one payload; it must be one fact, not two.
    listed = next(entry for entry in payload["artifacts"] if entry["name"] == ENGINE_NAME)
    assert listed["sha256"] == declared["sha256"] == _sha256(directory / ENGINE_NAME)
    assert listed["size_bytes"] == declared["size_bytes"]


def test_identical_workers_are_distinguishable_by_variant_alone(tmp_path: Path) -> None:
    """THE requirement: a CPU-built and a CUDA-built worker differ by manifest, not by bytes.

    Both directories are staged from the SAME worker bytes, so their artifact digests are
    identical; the only difference in the two signed payloads must be the variant facts. A future
    change that let these two payloads collapse into one would silently re-create the ambiguity
    `algenta serve` resolves.
    """
    worker_bytes = b"#!/bin/sh\nexit 0\n"
    cpu_dir = tmp_path / "cpu"
    cuda_dir = tmp_path / "cuda"
    for directory in (cpu_dir, cuda_dir):
        directory.mkdir(parents=True)
        (directory / "algenta-runtime-worker").write_bytes(worker_bytes)
        (directory / "algenta-runtime-worker-001").write_bytes(worker_bytes)
        (directory / "runtime-shards.json").write_text('{"schema_version":1}', encoding="utf-8")
    (cuda_dir / ENGINE_NAME).write_bytes(b"\x7fELF fake engine")
    (cuda_dir / ENGINE_NAME).chmod(0o755)

    cpu = bundle_manifest.build_bundle_manifest(
        artifact_dir=cpu_dir, platform="linux-x86_64", build_variant="cpu"
    )
    cuda = bundle_manifest.build_bundle_manifest(
        artifact_dir=cuda_dir,
        platform="linux-x86_64",
        build_variant="cuda",
        engine=_engine_block(cuda_dir),
        cuda_target="sm_90a",
    )

    cpu_digests = {
        entry["name"]: entry["sha256"] for entry in cpu["artifacts"] if entry["name"] != ENGINE_NAME
    }
    cuda_digests = {
        entry["name"]: entry["sha256"]
        for entry in cuda["artifacts"]
        if entry["name"] != ENGINE_NAME
    }
    assert cpu_digests == cuda_digests, "the shared workers must be byte-identical"
    assert cpu["build_variant"] != cuda["build_variant"]
    assert bundle_manifest.render_bundle_manifest(cpu) != bundle_manifest.render_bundle_manifest(
        cuda
    )


# ── fail closed on an incoherent manifest ────────────────────────────────────


def test_an_unknown_build_variant_is_refused_rather_than_defaulted(tmp_path: Path) -> None:
    directory = _stage_runtime(tmp_path / "bad")
    with pytest.raises(bundle_manifest.BundleManifestError, match="unknown build variant"):
        bundle_manifest.build_bundle_manifest(
            artifact_dir=directory, platform="linux-x86_64", build_variant="rocm"
        )


def test_a_manifest_with_no_build_variant_at_all_is_refused(tmp_path: Path) -> None:
    """Backwards incompatibility, deliberately: an OLD manifest is not silently read as `cpu`.

    Reading an absent variant as "cpu" would make a pre-schema CUDA wheel look like a CPU one, and
    reading it as "cuda" would launch an engine nobody certified. Refusing is the only answer that
    cannot be wrong.
    """
    payload = {
        "format_version": 1,
        "platform": "linux-x86_64",
        "artifacts": [
            {"name": "algenta-runtime-worker", "sha256": "0" * 64, "size_bytes": 1},
            {"name": "algenta-runtime-worker-001", "sha256": "0" * 64, "size_bytes": 1},
            {"name": "runtime-shards.json", "sha256": "0" * 64, "size_bytes": 1},
        ],
    }
    with pytest.raises(bundle_manifest.BundleManifestError, match="build_variant"):
        bundle_manifest.validate_bundle_manifest(payload)


def test_an_engine_cannot_ride_in_a_cpu_manifest(tmp_path: Path) -> None:
    directory = _stage_runtime(tmp_path / "cpu", engine=b"\x7fELF fake engine")
    with pytest.raises(bundle_manifest.BundleManifestError, match="cannot be declared"):
        bundle_manifest.build_bundle_manifest(
            artifact_dir=directory,
            platform="linux-x86_64",
            build_variant="cpu",
            engine=_engine_block(directory),
        )


def test_a_cuda_target_cannot_ride_in_a_cpu_manifest(tmp_path: Path) -> None:
    directory = _stage_runtime(tmp_path / "cpu")
    with pytest.raises(bundle_manifest.BundleManifestError, match="cuda_target"):
        bundle_manifest.build_bundle_manifest(
            artifact_dir=directory,
            platform="linux-x86_64",
            build_variant="cpu",
            cuda_target="sm_90a",
        )


def test_an_engine_must_be_a_staged_artifact(tmp_path: Path) -> None:
    """The manifest cannot declare an engine the wheel does not contain.

    This is the exact defect the workstream is fixing, moved one level down: a manifest that claims
    kernels ship, over a directory where they do not.
    """
    directory = _stage_runtime(tmp_path / "cuda")
    with pytest.raises(bundle_manifest.BundleManifestError, match="not present in the staged"):
        bundle_manifest.build_bundle_manifest(
            artifact_dir=directory,
            platform="linux-x86_64",
            build_variant="cuda",
            engine={
                "name": ENGINE_NAME,
                "sha256": "0" * 64,
                "size_bytes": 1,
                "source": ENGINE_SOURCE,
                "cuda_target": "sm_90a",
                "comptime_defines": list(CERTIFIED_DEFINES),
                "host_shared_libraries": ["libcublas.so.12"],
            },
            cuda_target="sm_90a",
        )


def test_a_cuda_engine_manifest_without_a_cuda_target_is_refused(tmp_path: Path) -> None:
    directory = _stage_runtime(tmp_path / "cuda", engine=b"\x7fELF fake engine")
    engine = _engine_block(directory)
    payload = bundle_manifest.build_bundle_manifest(
        artifact_dir=directory,
        platform="linux-x86_64",
        build_variant="cuda",
        engine=engine,
        cuda_target="sm_90a",
    )
    del payload["cuda_target"]
    with pytest.raises(bundle_manifest.BundleManifestError, match="cuda_target"):
        bundle_manifest.validate_bundle_manifest(payload)


@pytest.mark.parametrize(
    "cuda_target",
    ["sm90a", "sm_90a ", "compute_90", "9.0", "", "sm_"],
)
def test_a_malformed_cuda_target_is_refused(cuda_target: str) -> None:
    with pytest.raises(bundle_manifest.BundleManifestError, match="cuda_target"):
        bundle_manifest.build_engine_block(
            name=ENGINE_NAME,
            sha256="0" * 64,
            size_bytes=1,
            source=ENGINE_SOURCE,
            cuda_target=cuda_target,
            comptime_defines=CERTIFIED_DEFINES,
            host_shared_libraries=("libcublas.so.12",),
        )


def test_a_host_library_must_be_a_soname_not_a_path() -> None:
    """The declaration is what a USER's host has to provide, so it must name a library, not ours."""
    with pytest.raises(bundle_manifest.BundleManifestError, match="soname"):
        bundle_manifest.build_engine_block(
            name=ENGINE_NAME,
            sha256="0" * 64,
            size_bytes=1,
            source=ENGINE_SOURCE,
            cuda_target="sm_90a",
            comptime_defines=CERTIFIED_DEFINES,
            host_shared_libraries=("/usr/local/cuda/lib64/libcublas.so.12",),
        )


def test_an_artifact_name_must_stay_a_bare_file_name(tmp_path: Path) -> None:
    directory = _stage_runtime(tmp_path / "cuda", engine=b"\x7fELF fake engine")
    engine = _engine_block(directory)
    payload = bundle_manifest.build_bundle_manifest(
        artifact_dir=directory,
        platform="linux-x86_64",
        build_variant="cuda",
        engine=engine,
        cuda_target="sm_90a",
    )
    payload["artifacts"].append({"name": "../escape", "sha256": "0" * 64, "size_bytes": 1})
    with pytest.raises(bundle_manifest.BundleManifestError, match="unsafe"):
        bundle_manifest.validate_bundle_manifest(payload)


def test_the_bounded_worker_shard_invariant_survives_the_refactor(tmp_path: Path) -> None:
    """The two invariants the replaced heredoc asserted are still asserted."""
    directory = tmp_path / "one-worker"
    directory.mkdir()
    (directory / "algenta-runtime-worker").write_bytes(b"#!/bin/sh\nexit 0\n")
    (directory / "runtime-shards.json").write_text("{}", encoding="utf-8")
    with pytest.raises(bundle_manifest.BundleManifestError, match="worker shards missing"):
        bundle_manifest.build_bundle_manifest(
            artifact_dir=directory, platform="linux-x86_64", build_variant="cpu"
        )

    no_shard_map = tmp_path / "no-map"
    no_shard_map.mkdir()
    (no_shard_map / "algenta-runtime-worker").write_bytes(b"#!/bin/sh\nexit 0\n")
    (no_shard_map / "algenta-runtime-worker-001").write_bytes(b"#!/bin/sh\nexit 0\n")
    with pytest.raises(bundle_manifest.BundleManifestError, match="runtime-shards.json"):
        bundle_manifest.build_bundle_manifest(
            artifact_dir=no_shard_map, platform="linux-x86_64", build_variant="cpu"
        )


# ── canonical bytes, and the round trip through the release validator ────────


def test_the_rendered_manifest_is_canonical_and_byte_stable(tmp_path: Path) -> None:
    """The release signature covers these EXACT bytes, so re-serializing must be a no-op."""
    directory = _stage_runtime(tmp_path / "cuda", engine=b"\x7fELF fake engine")
    payload = bundle_manifest.build_bundle_manifest(
        artifact_dir=directory,
        platform="linux-x86_64",
        build_variant="cuda",
        engine=_engine_block(directory),
        cuda_target="sm_90a",
    )
    rendered = bundle_manifest.render_bundle_manifest(payload)
    assert rendered == bundle_manifest.render_bundle_manifest(json.loads(rendered))
    assert b"\n" not in rendered
    assert b": " not in rendered and b", " not in rendered, "canonical separators, not pretty"
    assert json.loads(rendered) == payload


def _sign(directory: Path, manifest_bytes: bytes) -> None:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    (directory / "manifest.json").write_bytes(manifest_bytes)
    (directory / "manifest.sig").write_bytes(
        key.sign(manifest_bytes, padding.PKCS1v15(), hashes.SHA256())
    )
    (directory / "algenta_release_pub.pem").write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )


def test_the_release_validator_round_trips_a_signed_cuda_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = _stage_runtime(tmp_path / "cuda", engine=b"\x7fELF fake engine")
    payload = bundle_manifest.build_bundle_manifest(
        artifact_dir=directory,
        platform="linux-x86_64",
        build_variant="cuda",
        engine=_engine_block(directory),
        cuda_target="sm_90a",
    )
    _sign(directory, bundle_manifest.render_bundle_manifest(payload))
    monkeypatch.setenv("ALGENTA_RELEASE_PUBKEY_FILE", str(directory / "algenta_release_pub.pem"))
    monkeypatch.delenv("ALGENTA_RELEASE_PUBKEY", raising=False)

    summary = release_validation.validate_bundle_manifest(directory / "manifest.json")
    assert summary["build_variant"] == "cuda"
    assert summary["platform"] == "linux-x86_64"
    assert summary["artifact_count"] == len(payload["artifacts"])
    assert summary["engine"]["name"] == ENGINE_NAME
    assert summary["engine"]["cuda_target"] == "sm_90a"
    assert summary["engine"]["comptime_define_count"] == len(CERTIFIED_DEFINES)
    assert summary["engine"]["host_shared_libraries"] == [
        "libcublas.so.12",
        "libcublasLt.so.12",
    ]


def test_the_release_validator_refuses_a_tampered_engine_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One byte of the bundled engine, and the signed manifest stops covering the wheel."""
    directory = _stage_runtime(tmp_path / "cuda", engine=b"\x7fELF fake engine")
    payload = bundle_manifest.build_bundle_manifest(
        artifact_dir=directory,
        platform="linux-x86_64",
        build_variant="cuda",
        engine=_engine_block(directory),
        cuda_target="sm_90a",
    )
    _sign(directory, bundle_manifest.render_bundle_manifest(payload))
    monkeypatch.setenv("ALGENTA_RELEASE_PUBKEY_FILE", str(directory / "algenta_release_pub.pem"))
    monkeypatch.delenv("ALGENTA_RELEASE_PUBKEY", raising=False)

    (directory / ENGINE_NAME).write_bytes(b"\x7fELF tampered engine")
    with pytest.raises(release_validation.RuntimeReleaseValidationScriptError) as excinfo:
        release_validation.validate_bundle_manifest(directory / "manifest.json")
    assert excinfo.value.code == "bundle_artifact_tampered"


def test_the_release_validator_refuses_an_unsigned_bundle(tmp_path: Path) -> None:
    directory = _stage_runtime(tmp_path / "cuda", engine=b"\x7fELF fake engine")
    payload = bundle_manifest.build_bundle_manifest(
        artifact_dir=directory,
        platform="linux-x86_64",
        build_variant="cuda",
        engine=_engine_block(directory),
        cuda_target="sm_90a",
    )
    (directory / "manifest.json").write_bytes(bundle_manifest.render_bundle_manifest(payload))
    with pytest.raises(release_validation.RuntimeReleaseValidationScriptError) as excinfo:
        release_validation.validate_bundle_manifest(directory / "manifest.json")
    assert excinfo.value.code == "bundle_manifest_unsigned"


def test_the_release_validator_refuses_a_bundle_signed_by_another_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = _stage_runtime(tmp_path / "cuda", engine=b"\x7fELF fake engine")
    payload = bundle_manifest.build_bundle_manifest(
        artifact_dir=directory,
        platform="linux-x86_64",
        build_variant="cuda",
        engine=_engine_block(directory),
        cuda_target="sm_90a",
    )
    _sign(directory, bundle_manifest.render_bundle_manifest(payload))

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setenv(
        "ALGENTA_RELEASE_PUBKEY",
        other.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode("ascii"),
    )
    with pytest.raises(release_validation.RuntimeReleaseValidationScriptError) as excinfo:
        release_validation.validate_bundle_manifest(directory / "manifest.json")
    assert excinfo.value.code == "bundle_manifest_untrusted"


def test_the_generator_cli_writes_a_validatable_manifest(tmp_path: Path) -> None:
    directory = _stage_runtime(tmp_path / "cuda", engine=b"\x7fELF fake engine")
    argv = [
        "--artifact-dir",
        str(directory),
        "--platform",
        "linux-x86_64",
        "--build-variant",
        "cuda",
        "--output",
        str(directory / "manifest.json"),
        "--engine",
        ENGINE_NAME,
        "--engine-source",
        ENGINE_SOURCE,
        "--cuda-target",
        "sm_90a",
        "--host-shared-library",
        "libcublas.so.12",
    ]
    for define in CERTIFIED_DEFINES:
        argv += ["--comptime-define", define]

    assert bundle_manifest.main(argv) == 0
    payload = json.loads((directory / "manifest.json").read_bytes())
    bundle_manifest.validate_bundle_manifest(payload)
    assert payload["build_variant"] == "cuda"
    assert payload["engine"]["comptime_defines"] == list(CERTIFIED_DEFINES)


def test_the_generator_cli_refuses_an_engine_that_was_never_staged(tmp_path: Path) -> None:
    directory = _stage_runtime(tmp_path / "cuda")
    assert (
        bundle_manifest.main(
            [
                "--artifact-dir",
                str(directory),
                "--platform",
                "linux-x86_64",
                "--build-variant",
                "cuda",
                "--output",
                str(directory / "manifest.json"),
                "--engine",
                ENGINE_NAME,
                "--engine-source",
                ENGINE_SOURCE,
                "--cuda-target",
                "sm_90a",
                "--comptime-define",
                "ALGENTA_CUDA",
            ]
        )
        == 1
    )
    assert not (directory / "manifest.json").exists()
