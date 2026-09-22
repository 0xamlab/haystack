#!/usr/bin/env python3
"""Refuse ELF objects whose PT_LOAD program headers glibc will not map.

glibc's loader rejects any object carrying a PT_LOAD segment whose virtual address and file offset
differ by something other than a whole number of pages:

    ELF load command address/offset not page-aligned

patchelf 0.14.x (ubuntu:22.04's apt package) emits exactly such a header -- a zero-size PT_LOAD
left where a grown section used to be -- when a --set-rpath / --set-soname / --replace-needed
rewrite has to enlarge a segment (fixed upstream in 0.18). Every published algenta-llm x86_64
library carried one and could not be dlopened on any real Linux/amd64 host (2026-09-22), while the
same pipeline's macOS and aarch64 artifacts were fine. This module is the gate that makes the
defect impossible to ship: build_hf_kernel_family.py runs `alignment_defects` over every Linux
artifact after the retag, and the release tooling / CI run this file over the staged closures.

Per PT_LOAD header (System V gABI "Program Header"; glibc elf/dl-load.c):
  * (p_vaddr - p_offset) % 0x1000 == 0        the page congruence glibc enforces
  * p_offset % p_align == p_vaddr % p_align     the gABI congruence rule (p_align > 1)

    scripts/hf_kernels/elf_check.py <file or directory> [...]

Directories are walked; files that are not ELF images (Mach-O dylibs, manifests) are skipped and
reported as such. Exit status 0 when every ELF file is loadable, 1 when any header is misaligned or
an image is malformed, 2 when a path does not exist. Standard library only, so it runs unchanged
inside the build container's pixi Python and on a macOS host inspecting Linux artifacts.
"""

from __future__ import annotations

import argparse
import struct
import sys
from collections.abc import Iterable
from pathlib import Path

ELF_MAGIC = b"\x7fELF"
PT_LOAD = 1
PAGE_SIZE = 0x1000
_EHDR_LEN = {1: 52, 2: 64}
_PHDR_LEN = {1: 32, 2: 56}
_PHDR_FIELDS = {
    # struct format and field order of one program header, per ELF class
    1: (
        "IIIIIIII",
        ("p_type", "p_offset", "p_vaddr", "p_paddr", "p_filesz", "p_memsz", "p_flags", "p_align"),
    ),
    2: (
        "IIQQQQQQ",
        ("p_type", "p_flags", "p_offset", "p_vaddr", "p_paddr", "p_filesz", "p_memsz", "p_align"),
    ),
}
_REPORTED = ("p_type", "p_offset", "p_vaddr", "p_filesz", "p_memsz", "p_align")


def is_elf(path: Path) -> bool:
    try:
        with Path(path).open("rb") as f:
            return f.read(len(ELF_MAGIC)) == ELF_MAGIC
    except OSError:
        return False


def program_headers(data: bytes) -> list[dict[str, int]]:
    """Parse the program header table of an ELF32 or ELF64 image in either byte order.

    One dict per header: index, p_type, p_offset, p_vaddr, p_filesz, p_memsz, p_align.
    Raises ValueError for anything that is not a well-formed ELF image.
    """
    if data[:4] != ELF_MAGIC:
        raise ValueError("not an ELF image")
    ei_class, ei_data = data[4], data[5]
    if ei_class not in _EHDR_LEN or ei_data not in (1, 2):
        raise ValueError(f"unsupported EI_CLASS/EI_DATA {ei_class}/{ei_data}")
    end = "<" if ei_data == 1 else ">"
    if len(data) < _EHDR_LEN[ei_class]:
        raise ValueError("truncated ELF header")
    if ei_class == 2:
        (e_phoff,) = struct.unpack_from(end + "Q", data, 0x20)
        e_phentsize, e_phnum = struct.unpack_from(end + "HH", data, 0x36)
    else:
        (e_phoff,) = struct.unpack_from(end + "I", data, 0x1C)
        e_phentsize, e_phnum = struct.unpack_from(end + "HH", data, 0x2A)
    if e_phnum and e_phentsize < _PHDR_LEN[ei_class]:
        bits = 32 if ei_class == 1 else 64
        raise ValueError(f"e_phentsize {e_phentsize} is below the ELF{bits} minimum")
    if e_phoff + e_phnum * e_phentsize > len(data):
        raise ValueError("truncated program header table")
    fmt, names = _PHDR_FIELDS[ei_class]
    headers: list[dict[str, int]] = []
    for i in range(e_phnum):
        raw = struct.unpack_from(end + fmt, data, e_phoff + i * e_phentsize)
        fields = dict(zip(names, raw, strict=True))
        headers.append({"index": i, **{k: fields[k] for k in _REPORTED}})
    return headers


def alignment_defects(path: Path) -> list[str]:
    """One line per PT_LOAD header of `path` that the loader would refuse, naming the file and the
    header index; empty when every load segment is mappable."""
    path = Path(path)
    try:
        headers = program_headers(path.read_bytes())
    except (OSError, ValueError) as exc:
        return [f"{path}: unreadable or malformed ELF image ({exc})"]
    defects: list[str] = []
    for h in headers:
        if h["p_type"] != PT_LOAD:
            continue
        where = (
            f"{path}: PT_LOAD program header #{h['index']} (p_offset=0x{h['p_offset']:x} "
            f"p_vaddr=0x{h['p_vaddr']:x} p_filesz=0x{h['p_filesz']:x} p_align=0x{h['p_align']:x})"
        )
        page_delta = (h["p_vaddr"] - h["p_offset"]) % PAGE_SIZE
        if page_delta != 0:
            defects.append(
                f"{where}: (p_vaddr - p_offset) % 0x1000 = 0x{page_delta:x}; "
                "glibc: 'ELF load command address/offset not page-aligned'"
            )
        align = h["p_align"]
        if align > 1 and h["p_offset"] % align != h["p_vaddr"] % align:
            defects.append(
                f"{where}: p_offset % p_align = 0x{h['p_offset'] % align:x} "
                f"but p_vaddr % p_align = 0x{h['p_vaddr'] % align:x}"
            )
    return defects


def candidate_files(paths: Iterable[Path]) -> tuple[list[Path], list[Path]]:
    """Expand directories (walked, sorted) into files; return (files, missing paths)."""
    files: list[Path] = []
    missing: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(q for q in p.rglob("*") if q.is_file()))
        elif p.is_file():
            files.append(p)
        else:
            missing.append(p)
    return files, missing


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("paths", nargs="+", type=Path, help="ELF files, or directories to walk")
    ap.add_argument("--quiet", action="store_true", help="print only defects and the summary line")
    a = ap.parse_args(argv)
    files, missing = candidate_files(a.paths)
    for p in missing:
        print(f"MISSING  {p}", file=sys.stderr)
    checked = skipped = bad_files = 0
    for p in files:
        if not is_elf(p):
            skipped += 1
            if not a.quiet:
                print(f"skip     {p} (not an ELF image)")
            continue
        checked += 1
        defects = alignment_defects(p)
        if defects:
            bad_files += 1
            for line in defects:
                print(f"MISALIGNED {line}")
        elif not a.quiet:
            print(f"aligned  {p}")
    print(
        f"elf_check: {checked} ELF file(s) checked, {bad_files} with misaligned PT_LOAD headers, "
        f"{skipped} non-ELF skipped, {len(missing)} missing"
    )
    if missing:
        return 2
    return 1 if bad_files else 0


if __name__ == "__main__":
    raise SystemExit(main())
