#!/usr/bin/env python3
"""verify-no-dev-secret: fail if a BUILT artifact still carries the HS256 dev-licence secret.

``scripts/strip_dev_stub.py`` hardens a SOURCE tree before packaging. This gate runs on the OUTPUT
-- an exported container-image filesystem, a runtime-bundle tarball or an unpacked directory -- so a
production artifact is proven clean by inspection rather than by trusting that the build steps which
were supposed to strip it actually ran (secret-scanning alert #14: the needle was public for a month
and, until this gate, nothing checked the shipped images or the bundle for it).

    docker export "$(docker create IMAGE)" | python3 scripts/verify_no_dev_secret.py --tar -
    python3 scripts/verify_no_dev_secret.py --tar dist/runtime-bundle/algenta-runtime-<v>-<os>.tgz
    python3 scripts/verify_no_dev_secret.py --tar-glob 'dist/runtime-bundle/algenta-runtime-*.tgz'
    python3 scripts/verify_no_dev_secret.py --tree build/wheel-staging

Three independent checks; any finding is exit 1 (findings are listed by path; the needle itself is
never echoed):

  1. path denylist -- ``apps/runtime/_dev_license_stub.py`` (or its compiled bytecode) and
     ``scripts/strip_dev_stub.py`` (the build tool that legitimately holds the needle) must not ship
     at all, whatever their content;
  2. byte scan -- every regular file is searched for the needle literal, chunked with overlap, so a
     ``.py``, a ``.pyc``, a ``.so`` constant pool, JSON, anything is caught whatever its extension;
  3. frozen archive -- a PyInstaller-frozen executable (recognised by its archive magic) has its
     embedded PYZ opened: ``apps.runtime._dev_license_stub`` must be absent from the table of
     contents and no module's DECOMPRESSED bytecode may hold the needle. The PYZ is zlib-compressed,
     so check (2) alone cannot see into it; this is what makes the gate meaningful for the
     managed-runtime bundle.

``--tar-glob`` takes a QUOTED pattern and resolves it here, refusing anything but exactly one match,
so a release script never depends on the shell's zero-/multi-match glob behaviour. Hard links in a
tar are resolved to the regular member they name: that member's bytes are scanned once, a link to a
flagged member is reported too, and a link whose target the archive never presents as a regular
file is a finding (fail-closed) because its bytes could not be scanned.

The needle is read from ``scripts/strip_dev_stub.py`` (its single build-side home) at start-up, so
this file never contains it and can itself ship inside an image.
"""

from __future__ import annotations

import argparse
import glob
import importlib.util
import os
import sys
import tarfile
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import IO

_HERE = Path(__file__).resolve().parent
_STUB_MODULE = "apps.runtime._dev_license_stub"
_STUB_SOURCE_NAME = "_dev_license_stub.py"
_STUB_BYTECODE_PREFIX = "_dev_license_stub."
_STRIP_TOOL_NAME = "strip_dev_stub.py"
# The cookie magic every PyInstaller CArchive ends with (PyInstaller/archive/readers.py; the
# bootloader's pyi_archive.h). Its presence in a file marks a frozen executable.
_PYINSTALLER_MAGIC = b"MEI\014\013\012\013\016"
_CHUNK = 1 << 20
# A frozen executable is buffered in memory while it is scanned so its archive can be opened
# afterwards without re-reading a non-seekable stream. Onedir daemons are a few MB; this cap only
# guards against pathological inputs.
_FROZEN_BUFFER_CAP = 256 << 20


class GateInputError(Exception):
    """The artifact could not be read at all (usage / IO error, exit 2), as opposed to a finding."""


@dataclass
class GateReport:
    files_scanned: int = 0
    bytes_scanned: int = 0
    frozen_archives_inspected: int = 0
    hardlinks_resolved: int = 0
    findings: list[str] = field(default_factory=list)

    @property
    def hardened(self) -> bool:
        return not self.findings


def load_needle() -> bytes:
    """The literal that must be absent, imported from its single build-side home."""
    source = _HERE / _STRIP_TOOL_NAME
    spec = importlib.util.spec_from_file_location("_algenta_strip_dev_stub", source)
    if spec is None or spec.loader is None:
        raise GateInputError(f"cannot load the needle source {source}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    needle = str(module._DEV_SECRET_NEEDLE).encode("utf-8")
    if len(needle) < 16:
        raise GateInputError("dev-secret needle is implausibly short; refusing to gate on it")
    return needle


# ── Check 1: path denylist ─────────────────────────────────────────────────────────────────────


def denylisted_path_reason(path: str) -> str | None:
    """Why a path must not appear in a production artifact, or None when it is allowed."""
    name = PurePosixPath(path.replace(os.sep, "/")).name
    if name == _STUB_SOURCE_NAME:
        return "the dev-licence stub module ships in the artifact"
    if name.startswith(_STUB_BYTECODE_PREFIX) and name.endswith((".pyc", ".pyo")):
        return "compiled bytecode of the dev-licence stub ships in the artifact"
    if name == _STRIP_TOOL_NAME:
        return "the strip tool (which holds the needle) ships in the artifact"
    return None


# ── Check 2: chunked byte scan ─────────────────────────────────────────────────────────────────


@dataclass
class _ScanResult:
    size: int = 0
    needle_found: bool = False
    magic_found: bool = False
    buffered: bytearray | None = None  # full content, kept only while under the buffer cap


def scan_stream(stream: IO[bytes], needle: bytes, *, keep_content: bool = True) -> _ScanResult:
    """Search a byte stream for the needle and the PyInstaller magic, chunk by chunk with an overlap
    of (longest pattern - 1) bytes so a match straddling two chunks is still seen."""
    result = _ScanResult(buffered=bytearray() if keep_content else None)
    patterns = (needle, _PYINSTALLER_MAGIC)
    keep = max(len(p) for p in patterns) - 1
    tail = b""
    while True:
        chunk = stream.read(_CHUNK)
        if not chunk:
            break
        result.size += len(chunk)
        window = tail + chunk
        if not result.needle_found and needle in window:
            result.needle_found = True
        if not result.magic_found and _PYINSTALLER_MAGIC in window:
            result.magic_found = True
        if result.buffered is not None:
            if result.size <= _FROZEN_BUFFER_CAP:
                result.buffered.extend(chunk)
            else:
                result.buffered = None
        tail = window[-keep:]
    return result


# ── Check 3: PyInstaller frozen archive ────────────────────────────────────────────────────────


def _import_carchive_reader() -> tuple[type, str]:
    """PyInstaller's CArchive reader class and its PYZ typecode; ImportError when not installed."""
    from PyInstaller.archive.readers import PKG_ITEM_PYZ, CArchiveReader

    return CArchiveReader, PKG_ITEM_PYZ


def inspect_frozen_archive(path: Path, needle: bytes, label: str) -> list[str]:
    """Open a PyInstaller-frozen executable's embedded PYZ archive(s) and report the dev stub module
    or any decompressed module bytecode that holds the needle. Fails closed when PyInstaller is not
    importable or the archive cannot be parsed: a file carrying the magic must be inspectable."""
    try:
        reader_cls, pyz_typecode = _import_carchive_reader()
    except ImportError:
        return [
            f"{label}: PyInstaller-frozen executable detected but PyInstaller is not importable; "
            "install pyinstaller so its embedded PYZ can be inspected (fail-closed)"
        ]
    try:
        archive = reader_cls(str(path))
    except Exception as exc:
        return [
            f"{label}: carries the PyInstaller archive magic but its archive is unreadable ({exc})"
        ]

    findings: list[str] = []
    pyz_names = [name for name, entry in archive.toc.items() if entry[-1] == pyz_typecode]
    if not pyz_names:
        findings.append(
            f"{label}: frozen executable has no embedded PYZ; cannot prove {_STUB_MODULE} is absent"
        )
    for pyz_name in pyz_names:
        pyz = archive.open_embedded_archive(pyz_name)
        if _STUB_MODULE in pyz.toc:
            findings.append(f"{label}: frozen PYZ {pyz_name} contains the module {_STUB_MODULE}")
        for module_name in sorted(pyz.toc):
            data = pyz.extract(module_name, raw=True)
            if isinstance(data, bytes | bytearray) and needle in data:
                findings.append(
                    f"{label}: frozen PYZ {pyz_name} module {module_name} holds the "
                    "dev-licence secret"
                )
    return findings


# ── Drivers ────────────────────────────────────────────────────────────────────────────────────


def _gate_one(path: str, stream: IO[bytes], needle: bytes, report: GateReport) -> None:
    report.files_scanned += 1
    reason = denylisted_path_reason(path)
    if reason is not None:
        report.findings.append(f"{path}: {reason}")
    scanned = scan_stream(stream, needle)
    report.bytes_scanned += scanned.size
    if scanned.needle_found:
        report.findings.append(f"{path}: contains the dev-licence secret")
    if not scanned.magic_found:
        return
    report.frozen_archives_inspected += 1
    if scanned.buffered is None:
        report.findings.append(
            f"{path}: PyInstaller-frozen executable larger than the {_FROZEN_BUFFER_CAP} byte "
            "buffer cap; re-run the gate against an unpacked --tree so it can be opened"
        )
        return
    with tempfile.NamedTemporaryFile(
        prefix="algenta-frozen-", suffix=".bin", delete=False
    ) as spool:
        spool.write(scanned.buffered)
        spool_path = Path(spool.name)
    try:
        report.findings.extend(inspect_frozen_archive(spool_path, needle, path))
    finally:
        spool_path.unlink(missing_ok=True)


def _member_path(name: str) -> str:
    """Member names and hard-link targets share one namespace; normalise both the same way."""
    return PurePosixPath(name).as_posix()


def _iter_tar_members(
    tar: tarfile.TarFile, hardlinks: list[tuple[str, str]]
) -> Iterator[tuple[str, IO[bytes]]]:
    """Yield each regular member's (path, payload). Hard links carry no payload of their own in the
    stream, so they are collected into ``hardlinks`` as (path, target) and resolved by the caller
    once every regular member has been seen (a link may precede its target in a crafted archive).
    Directories, symlinks and devices have no bytes to scan."""
    for member in tar:
        if member.islnk():
            hardlinks.append((_member_path(member.name), _member_path(member.linkname)))
            continue
        if not member.isfile():
            continue
        handle = tar.extractfile(member)
        if handle is None:
            continue
        with handle:
            yield _member_path(member.name), handle


def _resolve_hardlinks(
    hardlinks: list[tuple[str, str]], scanned: set[str], flagged: set[str], report: GateReport
) -> None:
    for path, target in hardlinks:
        report.hardlinks_resolved += 1
        reason = denylisted_path_reason(path)
        if reason is not None:
            report.findings.append(f"{path}: {reason}")
        if target not in scanned:
            report.findings.append(
                f"{path}: hard link to {target}, which this archive never presents as a regular "
                "file, so its bytes could not be scanned (fail-closed)"
            )
        elif target in flagged:
            report.findings.append(f"{path}: hard link to {target}, which is flagged above")


def gate_tar_stream(fileobj: IO[bytes], needle: bytes) -> GateReport:
    """Gate a tar stream (plain or compressed): a ``docker export`` pipe or a bundle tarball."""
    report = GateReport()
    hardlinks: list[tuple[str, str]] = []
    scanned: set[str] = set()
    flagged: set[str] = set()
    try:
        with tarfile.open(fileobj=fileobj, mode="r|*") as tar:
            for name, handle in _iter_tar_members(tar, hardlinks):
                before = len(report.findings)
                _gate_one(name, handle, needle, report)
                scanned.add(name)
                if len(report.findings) > before:
                    flagged.add(name)
    except tarfile.TarError as exc:
        raise GateInputError(f"not a readable tar archive: {exc}") from exc
    _resolve_hardlinks(hardlinks, scanned, flagged, report)
    return report


def resolve_tar_glob(pattern: str) -> Path:
    """Resolve a QUOTED glob to exactly one existing tar archive, or raise GateInputError. Done here
    rather than in the calling shell so zero matches (a literal pattern) or several matches (stale
    artifacts from an earlier run) fail with a message that says so, not a misleading one."""
    matches = sorted(p for p in glob.glob(os.path.expanduser(pattern)) if Path(p).is_file())
    if len(matches) != 1:
        found = f"found {len(matches)}" + (": " + ", ".join(matches) if matches else "")
        raise GateInputError(f"expected exactly one tar archive matching {pattern!r}, {found}")
    return Path(matches[0])


def gate_tar(source: str, needle: bytes) -> GateReport:
    if source == "-":
        return gate_tar_stream(sys.stdin.buffer, needle)
    path = Path(source).expanduser()
    if not path.is_file():
        raise GateInputError(f"tar archive not found: {path}")
    with path.open("rb") as fileobj:
        return gate_tar_stream(fileobj, needle)


def gate_tree(root: Path, needle: bytes) -> GateReport:
    """Gate an unpacked directory (a wheel-staging tree, an extracted image or bundle)."""
    if not root.is_dir():
        raise GateInputError(f"directory not found: {root}")
    report = GateReport()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            if path.is_symlink() or not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            with path.open("rb") as handle:
                _gate_one(rel, handle, needle, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail if a built artifact still carries the HS256 dev-licence secret."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--tar",
        help="tar archive (plain or compressed), or '-' for stdin: a `docker export` stream or a "
        "runtime-bundle tarball",
    )
    source.add_argument(
        "--tar-glob",
        help="a QUOTED glob matching exactly one tar archive (resolved here, not by the shell)",
    )
    source.add_argument("--tree", help="an unpacked directory")
    parser.add_argument(
        "--label", help="how to name the artifact in messages (default: the source)"
    )
    args = parser.parse_args(argv)

    label = args.label or args.tar or args.tar_glob or args.tree
    try:
        needle = load_needle()
        if args.tar_glob is not None:
            resolved = resolve_tar_glob(args.tar_glob)
            label = args.label or str(resolved)
            report = gate_tar(str(resolved), needle)
        elif args.tar is not None:
            report = gate_tar(args.tar, needle)
        else:
            report = gate_tree(Path(args.tree), needle)
    except GateInputError as exc:
        sys.stderr.write(f"verify-no-dev-secret: {exc}\n")
        return 2

    if not report.hardened:
        sys.stderr.write(
            f"verify-no-dev-secret: {label} is NOT hardened -- the HS256 dev-licence secret (or "
            "its "
            f"stub / strip tool) is present ({len(report.findings)} finding(s)):\n  - "
            + "\n  - ".join(report.findings)
            + "\n"
        )
        return 1
    sys.stdout.write(
        f"verify-no-dev-secret: {label} is clean -- {report.files_scanned} files / "
        f"{report.bytes_scanned} bytes scanned, {report.hardlinks_resolved} hard link(s) resolved, "
        f"{report.frozen_archives_inspected} frozen archive(s) inspected, no dev-licence secret, "
        "stub or strip tool present\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
