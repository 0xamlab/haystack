"""The shipped-artifact gate for the HS256 dev-licence secret (secret-scanning #14) and the build
surfaces that must run it.

scripts/strip_dev_stub.py hardens a SOURCE tree; scripts/verify_no_dev_secret.py proves the OUTPUT
(an exported image filesystem, a bundle tarball, an unpacked tree) is clean. Both must hold, and the
production Dockerfiles, the bundle spec and every image/bundle workflow must actually invoke them.
"""

from __future__ import annotations

import ast
import hashlib
import io
import sys
import tarfile
from pathlib import Path

import jwt
import pytest

from scripts import verify_no_dev_secret as gate
from scripts.strip_dev_stub import _DEV_SECRET_NEEDLE

_REPO = Path(__file__).resolve().parent.parent
_NEEDLE = _DEV_SECRET_NEEDLE.encode("utf-8")
_PRODUCTION_DOCKERFILES = (
    "infra/docker/Dockerfile.api.prod",
    "infra/docker/Dockerfile.worker.prod",
    "infra/docker/Dockerfile.engine.prod",
)


def _write(root: Path, rel: str, data: bytes) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _clean_tree(root: Path) -> None:
    _write(
        root,
        "apps/runtime/license.py",
        b"try:\n    from apps.runtime._dev_license_stub import DEV_SECRET\n"
        b"except ImportError:\n    _DEV_SECRET = None\n",
    )
    _write(root, "apps/runtime/__init__.py", b"")
    _write(root, "scripts/verify_no_dev_secret.py", b"# the gate itself never holds the needle\n")
    _write(root, "usr/lib/libfoo.so", b"\x7fELF" + b"\x00" * 64)


# ── the needle ────────────────────────────────────────────────────────────────────────────────────


def test_needle_is_read_from_the_strip_tool() -> None:
    assert gate.load_needle() == _NEEDLE
    # and the gate module itself never embeds it (it may ship inside an image)
    assert _NEEDLE not in (_REPO / "scripts" / "verify_no_dev_secret.py").read_bytes()


# ── check 1: path denylist ────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "app/apps/runtime/_dev_license_stub.py",
        "_dev_license_stub.py",
        "app/apps/runtime/__pycache__/_dev_license_stub.cpython-314.pyc",
        "build/scripts/strip_dev_stub.py",
    ],
)
def test_denylisted_paths_are_findings_regardless_of_content(path: str) -> None:
    assert gate.denylisted_path_reason(path) is not None


@pytest.mark.parametrize(
    "path",
    [
        "app/apps/runtime/license.py",
        "app/scripts/verify_no_dev_secret.py",
        "app/apps/runtime/__pycache__/license.cpython-314.pyc",
    ],
)
def test_ordinary_paths_are_allowed(path: str) -> None:
    assert gate.denylisted_path_reason(path) is None


# ── check 2: byte scan ────────────────────────────────────────────────────────────────────────────


def test_clean_tree_is_hardened(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    report = gate.gate_tree(tmp_path, _NEEDLE)
    assert report.hardened
    assert report.files_scanned == 4
    assert report.frozen_archives_inspected == 0


def test_secret_bytes_are_found_whatever_the_extension(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    for rel in (
        "apps/runtime/leaky.py",
        "apps/runtime/__pycache__/leaky.cpython-314.pyc",
        "etc/config.json",
        "usr/lib/libleaky.so",
    ):
        _write(tmp_path, rel, b"\x00prefix\x00" + _NEEDLE + b"\x00suffix")
    report = gate.gate_tree(tmp_path, _NEEDLE)
    flagged = sorted(f.split(":")[0] for f in report.findings)
    assert flagged == sorted(
        [
            "apps/runtime/leaky.py",
            "apps/runtime/__pycache__/leaky.cpython-314.pyc",
            "etc/config.json",
            "usr/lib/libleaky.so",
        ]
    )


def test_denylisted_paths_are_flagged_even_when_their_bytes_are_clean(tmp_path: Path) -> None:
    _clean_tree(tmp_path)
    _write(tmp_path, "apps/runtime/_dev_license_stub.py", b'DEV_SECRET = "redacted"\n')
    _write(tmp_path, "scripts/strip_dev_stub.py", b"# tool without its needle\n")
    _write(tmp_path, "apps/runtime/__pycache__/_dev_license_stub.cpython-314.pyc", b"\x00")
    report = gate.gate_tree(tmp_path, _NEEDLE)
    assert len(report.findings) == 3
    assert all("ships in the artifact" in f for f in report.findings)


def test_needle_straddling_a_chunk_boundary_is_still_seen() -> None:
    body = bytearray(b"A" * (gate._CHUNK + 4096))
    start = gate._CHUNK - 7  # 7 bytes before the boundary, the rest in the next chunk
    body[start : start + len(_NEEDLE)] = _NEEDLE
    result = gate.scan_stream(io.BytesIO(bytes(body)), _NEEDLE, keep_content=False)
    assert result.needle_found
    assert result.size == len(body)


def test_pyinstaller_magic_straddling_a_chunk_boundary_is_still_seen() -> None:
    body = bytearray(b"B" * (gate._CHUNK + 64))
    start = gate._CHUNK - 3
    body[start : start + len(gate._PYINSTALLER_MAGIC)] = gate._PYINSTALLER_MAGIC
    result = gate.scan_stream(io.BytesIO(bytes(body)), _NEEDLE, keep_content=False)
    assert result.magic_found and not result.needle_found


def _tarball(tmp_path: Path, files: dict[str, bytes], *, compress: bool = True) -> Path:
    out = tmp_path / ("artifact.tar.gz" if compress else "artifact.tar")
    with tarfile.open(out, "w:gz" if compress else "w") as tar:
        for rel, data in files.items():
            info = tarfile.TarInfo(rel)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        link = tarfile.TarInfo("app/alias")
        link.type = tarfile.SYMTYPE
        link.linkname = "apps/runtime/license.py"
        tar.addfile(link)
    return out


def test_tar_path_and_tar_stream_report_the_same_findings(tmp_path: Path) -> None:
    files = {
        "app/apps/runtime/license.py": b"clean\n",
        "app/etc/leak.txt": b"x" + _NEEDLE + b"y",
    }
    tarball = _tarball(tmp_path, files)
    by_path = gate.gate_tar(str(tarball), _NEEDLE)
    with tarball.open("rb") as fh:
        by_stream = gate.gate_tar_stream(fh, _NEEDLE)
    assert (
        by_path.findings
        == by_stream.findings
        == ["app/etc/leak.txt: contains the dev-licence secret"]
    )
    assert by_path.files_scanned == 2  # the symlink is not a regular member


def test_tar_from_stdin_is_supported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tarball = _tarball(tmp_path, {"a/clean": b"ok"}, compress=False)

    class _Stdin:
        buffer = tarball.open("rb")

    monkeypatch.setattr(sys, "stdin", _Stdin())
    try:
        report = gate.gate_tar("-", _NEEDLE)
    finally:
        _Stdin.buffer.close()
    assert report.hardened and report.files_scanned == 1


def _hardlink_tarball(tmp_path: Path, entries: list[tuple[str, str, bytes]]) -> Path:
    """entries: (kind, name, payload-or-linkname) in archive order; kind is 'file' or 'hardlink'."""
    out = tmp_path / "links.tar"
    with tarfile.open(out, "w") as tar:
        for kind, name, payload in entries:
            info = tarfile.TarInfo(name)
            if kind == "hardlink":
                info.type = tarfile.LNKTYPE
                info.linkname = payload.decode()
                tar.addfile(info)
            else:
                info.size = len(payload)
                tar.addfile(info, io.BytesIO(payload))
    return out


def test_hardlink_to_a_flagged_member_is_reported_and_its_bytes_scanned_once(
    tmp_path: Path,
) -> None:
    payload = b"x" + _NEEDLE + b"y"
    tarball = _hardlink_tarball(
        tmp_path,
        [
            ("file", "app/etc/leak.txt", payload),
            ("hardlink", "app/etc/leak-link.txt", b"app/etc/leak.txt"),
        ],
    )
    report = gate.gate_tar(str(tarball), _NEEDLE)
    assert report.findings == [
        "app/etc/leak.txt: contains the dev-licence secret",
        "app/etc/leak-link.txt: hard link to app/etc/leak.txt, which is flagged above",
    ]
    assert report.hardlinks_resolved == 1
    assert report.files_scanned == 1 and report.bytes_scanned == len(payload)  # scanned once


def test_hardlink_preceding_its_target_still_resolves(tmp_path: Path) -> None:
    tarball = _hardlink_tarball(
        tmp_path,
        [
            ("hardlink", "./bin/py", b"./usr/local/bin/python3.14"),
            ("file", "usr/local/bin/python3.14", b"ELF"),
        ],
    )
    report = gate.gate_tar(str(tarball), _NEEDLE)
    assert report.hardened and report.hardlinks_resolved == 1


def test_hardlink_to_a_member_never_presented_as_a_regular_file_fails_closed(
    tmp_path: Path,
) -> None:
    tarball = _hardlink_tarball(
        tmp_path,
        [("file", "app/ok.txt", b"clean"), ("hardlink", "app/ghost", b"app/never-in-archive")],
    )
    report = gate.gate_tar(str(tarball), _NEEDLE)
    assert report.findings == [
        "app/ghost: hard link to app/never-in-archive, which this archive never presents as a "
        "regular file, so its bytes could not be scanned (fail-closed)"
    ]


def test_hardlink_with_a_denylisted_name_is_flagged_by_path(tmp_path: Path) -> None:
    tarball = _hardlink_tarball(
        tmp_path,
        [
            ("file", "app/clean.py", b"clean"),
            ("hardlink", "app/apps/runtime/_dev_license_stub.py", b"app/clean.py"),
        ],
    )
    report = gate.gate_tar(str(tarball), _NEEDLE)
    assert report.findings == [
        "app/apps/runtime/_dev_license_stub.py: the dev-licence stub module ships in the artifact"
    ]


def test_tar_glob_requires_exactly_one_match(tmp_path: Path) -> None:
    pattern = str(tmp_path / "algenta-runtime-*-linux-x64.tar.gz")
    with pytest.raises(gate.GateInputError, match="expected exactly one tar archive .* found 0"):
        gate.resolve_tar_glob(pattern)  # zero matches: the literal pattern is not silently used
    one = _tarball(tmp_path, {"a/clean": b"ok"})
    one = one.rename(tmp_path / "algenta-runtime-1.0.0-linux-x64.tar.gz")
    assert gate.resolve_tar_glob(pattern) == one
    (tmp_path / "algenta-runtime-0.9.0-linux-x64.tar.gz").write_bytes(one.read_bytes())
    with pytest.raises(gate.GateInputError, match="found 2: .*0\\.9\\.0.*1\\.0\\.0"):
        gate.resolve_tar_glob(pattern)  # stale artifacts must not widen the argument list


def test_cli_tar_glob_gates_the_single_match_and_exits_2_otherwise(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pattern = str(tmp_path / "bundle-*.tar.gz")
    assert gate.main(["--tar-glob", pattern]) == 2
    leaky = _tarball(tmp_path, {"app/etc/leak.txt": b"x" + _NEEDLE + b"y"}).rename(
        tmp_path / "bundle-1.tar.gz"
    )
    assert gate.main(["--tar-glob", pattern]) == 1
    captured = capsys.readouterr()
    assert "found 0" in captured.err and f"{leaky} is NOT hardened" in captured.err
    assert _DEV_SECRET_NEEDLE not in captured.err


def test_unreadable_inputs_are_input_errors_not_findings(tmp_path: Path) -> None:
    with pytest.raises(gate.GateInputError):
        gate.gate_tar(str(tmp_path / "missing.tar"), _NEEDLE)
    with pytest.raises(gate.GateInputError):
        gate.gate_tree(tmp_path / "missing", _NEEDLE)
    junk = tmp_path / "junk.tar"
    junk.write_bytes(b"not a tar archive at all" * 64)
    with pytest.raises(gate.GateInputError):
        gate.gate_tar(str(junk), _NEEDLE)


# ── check 3: PyInstaller frozen archive ───────────────────────────────────────────────────────────


def _frozen_file(tmp_path: Path) -> Path:
    return _write(
        tmp_path,
        "daemon/algenta-runtime-daemon",
        b"\x7fELF" + b"\x00" * 128 + gate._PYINSTALLER_MAGIC + b"\x00" * 32,
    )


def test_frozen_executable_without_pyinstaller_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _frozen_file(tmp_path)

    def _missing() -> tuple[type, str]:
        raise ImportError("No module named PyInstaller")

    monkeypatch.setattr(gate, "_import_carchive_reader", _missing)
    report = gate.gate_tree(tmp_path, _NEEDLE)
    assert report.frozen_archives_inspected == 1
    assert len(report.findings) == 1 and "PyInstaller is not importable" in report.findings[0]


class _FakePyz:
    def __init__(self, modules: dict[str, bytes]) -> None:
        self.toc = {name: ("m", 0, len(data)) for name, data in modules.items()}
        self._modules = modules

    def extract(self, name: str, raw: bool = False) -> bytes:
        assert raw, "the gate must scan DECOMPRESSED raw bytes, not unmarshal code objects"
        return self._modules[name]


def _fake_reader(modules: dict[str, bytes]) -> type:
    class _FakeCArchive:
        def __init__(self, filename: str) -> None:
            assert Path(filename).is_file()
            self.toc = {"PYZ-00.pyz": (0, 1, 1, 0, "z"), "pyi-runtime": (0, 1, 1, 0, "o")}

        def open_embedded_archive(self, name: str) -> _FakePyz:
            assert name == "PYZ-00.pyz"
            return _FakePyz(modules)

    return _FakeCArchive


def test_frozen_pyz_carrying_the_stub_module_is_flagged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _frozen_file(tmp_path)
    modules = {"apps.runtime.license": b"code", "apps.runtime._dev_license_stub": b"code"}
    monkeypatch.setattr(gate, "_import_carchive_reader", lambda: (_fake_reader(modules), "z"))
    report = gate.gate_tree(tmp_path, _NEEDLE)
    assert report.findings == [
        "daemon/algenta-runtime-daemon: frozen PYZ PYZ-00.pyz contains the module apps.runtime._dev_license_stub"
    ]


def test_frozen_pyz_bytecode_holding_the_needle_is_flagged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _frozen_file(tmp_path)
    modules = {"apps.runtime.license": b"code", "apps.runtime.other": b"\x00" + _NEEDLE + b"\x00"}
    monkeypatch.setattr(gate, "_import_carchive_reader", lambda: (_fake_reader(modules), "z"))
    report = gate.gate_tree(tmp_path, _NEEDLE)
    assert report.findings == [
        "daemon/algenta-runtime-daemon: frozen PYZ PYZ-00.pyz module apps.runtime.other holds the dev-licence secret"
    ]


def test_frozen_pyz_without_the_stub_is_hardened(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _frozen_file(tmp_path)
    modules = {"apps.runtime.license": b"code", "apps.runtime.daemon": b"code"}
    monkeypatch.setattr(gate, "_import_carchive_reader", lambda: (_fake_reader(modules), "z"))
    report = gate.gate_tree(tmp_path, _NEEDLE)
    assert report.hardened and report.frozen_archives_inspected == 1


# ── CLI contract ──────────────────────────────────────────────────────────────────────────────────


def test_cli_exit_codes_and_the_needle_is_never_printed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    clean = tmp_path / "clean"
    _clean_tree(clean)
    assert gate.main(["--tree", str(clean)]) == 0
    leaky = tmp_path / "leaky"
    _clean_tree(leaky)
    _write(leaky, "apps/runtime/_dev_license_stub.py", b'DEV_SECRET = "' + _NEEDLE + b'"\n')
    assert gate.main(["--tree", str(leaky), "--label", "leaky-image:test"]) == 1
    assert gate.main(["--tree", str(tmp_path / "absent")]) == 2
    captured = capsys.readouterr()
    assert "clean" in captured.out and "leaky-image:test is NOT hardened" in captured.err
    assert _DEV_SECRET_NEEDLE not in captured.out and _DEV_SECRET_NEEDLE not in captured.err


# ── the runtime degrades cleanly when the stub is absent (what a stripped image/bundle runs) ──────


def test_license_module_imports_and_hard_rejects_dev_hs256_without_the_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Load a SECOND copy of apps/runtime/license.py with the stub made unimportable (None in
    # sys.modules -> ImportError), exactly what the stripped image / EXCLUDES-built bundle sees.
    monkeypatch.setitem(sys.modules, "apps.runtime._dev_license_stub", None)
    monkeypatch.delenv("ALGENTA_LICENSE_RS256_ONLY", raising=False)
    monkeypatch.delenv("ALGENTA_REQUIRE_LOCAL_LICENSE", raising=False)
    monkeypatch.delenv("ALGENTA_RUNTIME_PRODUCT", raising=False)
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "apps_runtime_license_stripped_probe", _REPO / "apps" / "runtime" / "license.py"
    )
    assert spec is not None and spec.loader is not None
    probe = importlib.util.module_from_spec(spec)
    # register the probe under its own name: dataclass processing in license.py resolves
    # cls.__module__ through sys.modules
    monkeypatch.setitem(sys.modules, spec.name, probe)
    spec.loader.exec_module(probe)

    assert probe._DEV_SECRET is None
    forged = jwt.encode(
        {"ver": 2, "plan": "enterprise", "device_id": "d", "sub": "device-license"},
        _DEV_SECRET_NEEDLE,
        algorithm="HS256",
    )
    assert probe._parse_token(forged) is None
    # even for the one product that still verifies legacy control-plane HS256, the DEV secret is gone
    monkeypatch.setenv("ALGENTA_RUNTIME_PRODUCT", "codna")
    assert probe._parse_token(forged) is None
    with pytest.raises(RuntimeError, match="production build"):
        probe._issue_dev_jwt("device-x")


# ── build surfaces: the strip + gate must actually be wired in ────────────────────────────────────


def test_runtime_bundle_spec_excludes_the_stub_and_no_longer_hides_it_in() -> None:
    tree = ast.parse((_REPO / "scripts" / "runtime_bundle.spec").read_text(encoding="utf-8"))
    lists: dict[str, list[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.List):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"HIDDEN_IMPORTS", "EXCLUDES"}:
                    lists[target.id] = [ast.literal_eval(e) for e in node.value.elts]
    assert set(lists) == {"HIDDEN_IMPORTS", "EXCLUDES"}
    assert "apps.runtime._dev_license_stub" not in lists["HIDDEN_IMPORTS"]
    assert "apps.runtime._dev_license_stub" in lists["EXCLUDES"]
    assert "apps.runtime.license" in lists["HIDDEN_IMPORTS"]  # the consumer still ships


@pytest.mark.parametrize("relative_path", _PRODUCTION_DOCKERFILES)
def test_production_dockerfiles_strip_the_stub_before_the_runtime_stage(relative_path: str) -> None:
    text = (_REPO / relative_path).read_text(encoding="utf-8")
    strip = text.index("scripts/strip_dev_stub.py --package-root /build/context")
    drop_tool = text.index("rm /build/context/scripts/strip_dev_stub.py")
    context_copy = text.index("COPY . /build/context/")
    runtime_stage = text.index("FROM python:3.14-slim AS runtime")
    apps_copy = text.index("/build/context/apps/ /app/apps/")
    assert context_copy < strip < drop_tool < runtime_stage < apps_copy, relative_path


def test_control_plane_dockerfile_strips_the_stub_before_dropping_privileges() -> None:
    text = (_REPO / "infra/docker/Dockerfile.control-plane").read_text(encoding="utf-8")
    scripts_copy = text.index("COPY scripts/ /app/scripts/")
    strip = text.index("scripts/strip_dev_stub.py --package-root /app")
    drop_tool = text.index("rm /app/scripts/strip_dev_stub.py")
    user = text.index("USER app")
    assert scripts_copy < strip < drop_tool < user


def test_ci_gates_every_image_before_it_is_pushed_and_before_fly() -> None:
    text = (_REPO / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    # push-to-main image builds: local build -> gate -> push, per image
    for image in ("API", "Worker", "Engine"):
        local_build = text.index(f"- name: Build {image} image (local, for the dev-secret gate)")
        gate_step = text.index(
            f"- name: Gate -- the {image} image must not contain the dev-licence secret"
        )
        push = text.index(f"- name: Build and push {image} image")
        assert local_build < gate_step < push, image
    # PR-time smoke: the locally built API image is gated too
    smoke_build = text.index('-f infra/docker/Dockerfile.api.prod -t "$SMOKE_IMAGE_TAG" .')
    smoke_gate = text.index('bash scripts/verify_no_dev_secret.sh "$SMOKE_IMAGE_TAG"')
    assert smoke_build < smoke_gate
    # push-to-main deploys: pull -> gate -> fly, for codna-api and the control plane
    for app in ("codna-api", "algenta-control-plane"):
        fly = text.index(f"registry.fly.io/{app}:$TAG")
        gate_call = text.rindex('bash scripts/verify_no_dev_secret.sh "$SRC/api:$TAG"', 0, fly)
        pull = text.rindex('docker pull --platform linux/amd64 "$SRC/api:$TAG"', 0, gate_call)
        assert pull < gate_call < fly, app


def test_dispatch_deploy_gates_every_pulled_image_before_fly() -> None:
    text = (_REPO / ".github/workflows/deploy.yml").read_text(encoding="utf-8")
    for image, app in (
        ("engine", "codna-engine"),
        ("api", "codna-api"),
        ("api", "algenta-control-plane"),
    ):
        fly = text.index(f'"registry.fly.io/{app}:$TAG"')
        gate_call = text.rindex(f'bash scripts/verify_no_dev_secret.sh "$SRC/{image}:$TAG"', 0, fly)
        pull = text.rindex(f'docker pull --platform linux/amd64  "$SRC/{image}:$TAG"', 0, gate_call)
        assert pull < gate_call < fly, app


def test_bundle_release_build_gates_the_tarball_after_signing() -> None:
    text = (_REPO / ".github/scripts/build_runtime_bundle_linux_amd64.sh").read_text(
        encoding="utf-8"
    )
    build = text.index("python3 scripts/build_runtime_bundle.py")
    verify = text.index("python3 scripts/verify_runtime_bundle.py")
    gate_call = text.index("python3 scripts/verify_no_dev_secret.py")
    assert build < verify < gate_call
    # the glob is QUOTED and resolved by the gate (exactly-one-match), never by the shell
    assert "--tar-glob '/work/dist/runtime-bundle/algenta-runtime-*-linux-x64.tar.gz'" in text
    assert "--tar /work/dist/runtime-bundle/algenta-runtime-*" not in text


def test_makefile_gate_target_covers_tree_image_and_bundle() -> None:
    text = (_REPO / "Makefile").read_text(encoding="utf-8")
    target = text[text.index("verify-no-dev-secret:") :]
    assert 'bash scripts/verify_no_dev_secret.sh "$(IMAGE)"' in target
    assert 'python3 scripts/verify_no_dev_secret.py --tar "$(BUNDLE)"' in target
    assert "python3 scripts/verify_no_dev_secret.py --tree build/wheel-staging" in target


def test_only_the_stub_and_the_strip_tool_hold_the_needle_in_the_source_tree() -> None:
    # The two legitimate homes. Anything else is a leak the image strip would then have to catch.
    digest = hashlib.sha256(_NEEDLE).hexdigest()
    holders: list[str] = []
    for path in sorted((_REPO / "apps").rglob("*.py")) + sorted((_REPO / "scripts").rglob("*.py")):
        if _NEEDLE in path.read_bytes():
            holders.append(path.relative_to(_REPO).as_posix())
    assert holders == ["apps/runtime/_dev_license_stub.py", "scripts/strip_dev_stub.py"], digest[
        :12
    ]
