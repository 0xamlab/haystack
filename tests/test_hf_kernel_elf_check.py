"""scripts/hf_kernels/elf_check.py: the PT_LOAD alignment gate, exercised on synthetic ELF images.

The images are built here with `struct` (an ELF header plus a program header table, no sections or
code): one that glibc would map and ones carrying the exact header shape patchelf 0.14.3 left in the
published algenta-llm x86_64 libraries (p_offset 0x20198c, p_vaddr 0x203000, zero size). No binary
fixtures are committed.
"""

from __future__ import annotations

import importlib.util
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


elf_check = _load("hfk_elf_check", ROOT / "scripts" / "hf_kernels" / "elf_check.py")

PT_LOAD, PT_DYNAMIC = 1, 2


def elf64(loads: list[tuple[int, int, int]], *, little: bool = True, phentsize: int = 56) -> bytes:
    """A minimal ELF64 shared object: header + program headers. `loads` = [(p_offset, p_vaddr, p_align)];
    a PT_DYNAMIC header is appended so non-PT_LOAD entries are seen and ignored."""
    end = "<" if little else ">"
    ident = b"\x7fELF" + bytes([2, 1 if little else 2, 1, 0]) + b"\0" * 8
    phnum = len(loads) + 1
    header = ident + struct.pack(
        end + "HHIQQQIHHHHHH", 3, 62, 1, 0, 64, 0, 0, 64, phentsize, phnum, 64, 0, 0
    )
    body = b"".join(
        struct.pack(end + "IIQQQQQQ", PT_LOAD, 5, off, va, va, 0x100, 0x100, al).ljust(
            phentsize, b"\0"
        )
        for off, va, al in loads
    )
    body += struct.pack(
        end + "IIQQQQQQ", PT_DYNAMIC, 6, 0x1FFD18, 0x200D18, 0x200D18, 0x1D0, 0x1D0, 8
    ).ljust(phentsize, b"\0")
    return header + body


def elf32(loads: list[tuple[int, int, int]], *, little: bool = True) -> bytes:
    end = "<" if little else ">"
    ident = b"\x7fELF" + bytes([1, 1 if little else 2, 1, 0]) + b"\0" * 8
    header = ident + struct.pack(
        end + "HHIIIIIHHHHHH", 3, 3, 1, 0, 52, 0, 0, 52, 32, len(loads), 40, 0, 0
    )
    body = b"".join(
        struct.pack(end + "IIIIIIII", PT_LOAD, off, va, va, 0x100, 0x100, 5, al)
        for off, va, al in loads
    )
    return header + body


ALIGNED = [
    (0x0, 0x0, 0x1000),
    (0x2000, 0x2000, 0x1000),
    (0x1FFD18, 0x200D18, 0x1000),
    (0x201000, 0x202000, 0x1000),
]
# The published defect, verbatim: header #10 of libalgenta_algenta_llm.so (x86_64, patchelf 0.14.3).
PATCHELF_0_14_DEFECT = [
    (0x0, 0x0, 0x1000),
    (0x201000, 0x202000, 0x1000),
    (0x20198C, 0x203000, 0x1000),
    (0x202000, 0x204000, 0x1000),
]
# aarch64 style 64 KiB alignment: page-congruent, but not congruent modulo p_align.
CONGRUENCE_DEFECT = [(0x0, 0x0, 0x10000), (0x1000, 0x2000, 0x10000)]


def write(tmp_path: Path, name: str, data: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(data)
    return p


def test_program_headers_parse_elf64_and_elf32_in_both_byte_orders():
    for image in (
        elf64(ALIGNED),
        elf64(ALIGNED, little=False),
        elf32(ALIGNED[:2]),
        elf32(ALIGNED[:2], little=False),
    ):
        headers = elf_check.program_headers(image)
        loads = [h for h in headers if h["p_type"] == PT_LOAD]
        assert [(h["p_offset"], h["p_vaddr"], h["p_align"]) for h in loads] == ALIGNED[: len(loads)]
        assert [h["index"] for h in headers] == list(range(len(headers)))


def test_program_headers_honour_a_wider_e_phentsize():
    headers = elf_check.program_headers(elf64(ALIGNED, phentsize=64))
    assert [h["p_vaddr"] for h in headers if h["p_type"] == PT_LOAD] == [va for _, va, _ in ALIGNED]


def test_aligned_image_has_no_defects(tmp_path):
    assert elf_check.alignment_defects(write(tmp_path, "good.so", elf64(ALIGNED))) == []
    assert elf_check.alignment_defects(write(tmp_path, "good32.so", elf32(ALIGNED[:3]))) == []


def test_patchelf_0_14_shape_is_refused_and_names_the_header(tmp_path):
    defects = elf_check.alignment_defects(write(tmp_path, "bad.so", elf64(PATCHELF_0_14_DEFECT)))
    assert defects, "the misaligned zero-size PT_LOAD must be reported"
    assert all("bad.so" in d and "#2" in d for d in defects), defects
    assert any("(p_vaddr - p_offset) % 0x1000 = 0x674" in d for d in defects), defects
    assert any("not page-aligned" in d for d in defects), defects
    # Aligned neighbours are never reported.
    assert not any("#0" in d or "#1" in d or "#3" in d for d in defects), defects


def test_page_congruent_but_align_incongruent_header_is_refused(tmp_path):
    defects = elf_check.alignment_defects(write(tmp_path, "arm.so", elf64(CONGRUENCE_DEFECT)))
    assert len(defects) == 1 and "#1" in defects[0], defects
    assert "p_offset % p_align = 0x1000 but p_vaddr % p_align = 0x2000" in defects[0]


def test_p_align_of_zero_or_one_skips_the_congruence_rule(tmp_path):
    assert elf_check.alignment_defects(write(tmp_path, "a0.so", elf64([(0x10, 0x1010, 0)]))) == []
    assert elf_check.alignment_defects(write(tmp_path, "a1.so", elf64([(0x10, 0x1010, 1)]))) == []
    # ... but the page rule still applies.
    assert (
        len(elf_check.alignment_defects(write(tmp_path, "a1bad.so", elf64([(0x10, 0x1011, 1)]))))
        == 1
    )


def test_malformed_images_are_defects_not_crashes(tmp_path):
    truncated = write(tmp_path, "trunc.so", elf64(ALIGNED)[:-20])
    assert any(
        "truncated program header table" in d for d in elf_check.alignment_defects(truncated)
    )
    short = write(tmp_path, "short.so", b"\x7fELF" + b"\0" * 10)
    assert (
        elf_check.alignment_defects(short) and "malformed" in elf_check.alignment_defects(short)[0]
    )
    assert elf_check.alignment_defects(tmp_path / "missing.so")  # unreadable, reported not raised


def test_cli_exit_codes_and_directory_walk(tmp_path, capsys):
    good = write(tmp_path, "good.so", elf64(ALIGNED))
    nested = tmp_path / "cuda-sm_90" / "_native"
    nested.mkdir(parents=True)
    bad = write(nested, "libalgenta_algenta_llm.sm_90.so", elf64(PATCHELF_0_14_DEFECT))
    write(tmp_path, "manifest.json", b"{}")  # non-ELF: skipped, never a failure
    (tmp_path / "libalgenta.dylib").write_bytes(b"\xcf\xfa\xed\xfe" + b"\0" * 60)  # Mach-O: skipped

    assert elf_check.main([str(good)]) == 0
    out = capsys.readouterr().out
    assert "aligned" in out and "1 ELF file(s) checked, 0 with misaligned" in out

    assert elf_check.main(["--quiet", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert str(bad) in out and "#2" in out
    assert str(good) not in out.replace(str(bad), "")  # --quiet: only defects and the summary
    assert "2 ELF file(s) checked, 1 with misaligned PT_LOAD headers, 2 non-ELF skipped" in out

    assert elf_check.main([str(good), str(tmp_path / "nope.so")]) == 2
    assert "MISSING" in capsys.readouterr().err


def test_build_script_gate_raises_system_exit_naming_file_and_header(tmp_path):
    """build_hf_kernel_family._assert_elf_page_aligned is a plain raise (never `assert`) carrying the
    file and the program header index, so a container build log alone explains the refusal."""
    sys.path.insert(0, str(ROOT / "scripts"))
    build = _load("hfk_build_family", ROOT / "scripts" / "build_hf_kernel_family.py")
    bad = write(tmp_path, "libalgenta_algenta_llm.so", elf64(PATCHELF_0_14_DEFECT))
    with pytest.raises(SystemExit) as exc:
        build._assert_elf_page_aligned(bad)
    message = str(exc.value)
    assert "libalgenta_algenta_llm.so" in message and "#2" in message and "patchelf" in message
    build._assert_elf_page_aligned(write(tmp_path, "good.so", elf64(ALIGNED)))  # no raise
