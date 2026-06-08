from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

_KNOWN_ASSEMBLY_SUFFIXES = (".a51", ".asm", ".inc", ".s")
_ENTRYPOINT_NAMES = frozenset({"_start", "boot", "entry", "main", "start"})
_TEXT_SECTION_TOKENS = frozenset({"code", ".code", "text", ".text"})
_DATA_SECTION_TOKENS = frozenset({"bss", ".bss", "const", ".const", "data", ".data", "rodata"})
_POINTER_QUALIFIERS = frozenset(
    {
        "abs",
        "byte",
        "dword",
        "far",
        "fword",
        "large",
        "long",
        "near",
        "offset",
        "oword",
        "ptr",
        "qword",
        "rel",
        "short",
        "small",
        "tbyte",
        "tword",
        "word",
        "wrt",
        "xword",
        "yword",
        "zword",
    }
)
_SEGMENT_REGISTERS = frozenset({"cs", "ds", "es", "fs", "gs", "ss"})
_REGISTER_NAMES = frozenset(
    {
        "a",
        "ah",
        "al",
        "ar0",
        "ar1",
        "ar2",
        "ar3",
        "ar4",
        "ar5",
        "ar6",
        "ar7",
        "ax",
        "b",
        "bh",
        "bl",
        "bp",
        "bx",
        "cl",
        "cx",
        "di",
        "dl",
        "dx",
        "eax",
        "ebp",
        "ebx",
        "ecx",
        "edi",
        "edx",
        "eip",
        "esi",
        "esp",
        "fp",
        "hl",
        "pc",
        "r0",
        "r1",
        "r10",
        "r11",
        "r12",
        "r13",
        "r14",
        "r15",
        "r2",
        "r3",
        "r4",
        "r5",
        "r6",
        "r7",
        "r8",
        "r9",
        "ra",
        "si",
        "sp",
        "spl",
        "x0",
        "x1",
        "x10",
        "x11",
        "x12",
        "x13",
        "x14",
        "x15",
        "x16",
        "x17",
        "x18",
        "x19",
        "x2",
        "x20",
        "x21",
        "x22",
        "x23",
        "x24",
        "x25",
        "x26",
        "x27",
        "x28",
        "x29",
        "x3",
        "x30",
        "x31",
        "x4",
        "x5",
        "x6",
        "x7",
        "x8",
        "x9",
        "y",
    }
)
_COMMON_DIRECTIVES = frozenset(
    {
        ".ascii",
        ".asciz",
        ".byte",
        ".code",
        ".data",
        ".global",
        ".globl",
        ".include",
        ".long",
        ".macro",
        ".quad",
        ".section",
        ".short",
        ".text",
        ".word",
        "align",
        "assume",
        "bits",
        "code",
        "cpu",
        "data",
        "db",
        "dd",
        "dq",
        "dt",
        "dw",
        "equ",
        "export",
        "extern",
        "extrn",
        "format",
        "global",
        "include",
        "incbin",
        "macro",
        "model",
        "org",
        "proc",
        "public",
        "section",
        "segment",
        "struc",
        "struct",
    }
)
_DATA_DIRECTIVES = frozenset(
    {
        ".ascii",
        ".asciz",
        ".byte",
        ".fill",
        ".long",
        ".quad",
        ".short",
        ".space",
        ".word",
        "db",
        "dd",
        "dq",
        "dt",
        "dw",
        "equ",
        "resb",
        "resd",
        "resq",
        "resw",
    }
)
_COMMON_MNEMONICS = frozenset(
    {
        "adc",
        "add",
        "and",
        "asr",
        "auipc",
        "cmp",
        "dec",
        "inc",
        "int",
        "lea",
        "ld",
        "lda",
        "ldx",
        "ldy",
        "li",
        "lui",
        "lsl",
        "lsr",
        "mov",
        "mul",
        "nop",
        "or",
        "pop",
        "push",
        "ret",
        "rol",
        "ror",
        "sbc",
        "st",
        "sta",
        "stx",
        "sty",
        "sub",
        "svc",
        "syscall",
        "test",
        "trap",
        "xor",
    }
)
_CONTROL_TRANSFER_OPCODES = frozenset(
    {
        "b",
        "bal",
        "bcc",
        "bcs",
        "beq",
        "bge",
        "bgt",
        "bhi",
        "ble",
        "bl",
        "blr",
        "bls",
        "blt",
        "bmi",
        "bne",
        "bpl",
        "bra",
        "br",
        "bsr",
        "bvc",
        "bvs",
        "call",
        "callq",
        "invoke",
        "ja",
        "jae",
        "jb",
        "jbe",
        "jc",
        "je",
        "jg",
        "jge",
        "jl",
        "jle",
        "jmp",
        "jmpq",
        "jnc",
        "jne",
        "jno",
        "jnp",
        "jns",
        "jnz",
        "jo",
        "jp",
        "js",
        "jz",
        "jal",
        "jalr",
        "jmpl",
        "jsr",
        "loop",
        "loopnz",
        "loopz",
    }
)
RESERVED_SYMBOL_NAMES = frozenset(
    set(_COMMON_DIRECTIVES)
    | set(_COMMON_MNEMONICS)
    | set(_CONTROL_TRANSFER_OPCODES)
    | set(_POINTER_QUALIFIERS)
    | set(_REGISTER_NAMES)
    | set(_SEGMENT_REGISTERS)
    | {"endm", "endp", "macro", "proc"}
)
_INCLUDE_RE = re.compile(
    r"^\s*(?:%include|include|\.include)\s*(?:"
    r"<(?P<angle>[^>]+)>|"
    r'"(?P<double>[^"]+)"|'
    r"'(?P<single>[^']+)')",
    re.IGNORECASE | re.MULTILINE,
)
_LABEL_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z_.$?@][A-Za-z0-9_.$?@]*)\s*::?\s*(?P<body>.*)$",
    re.IGNORECASE,
)
_PROC_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z_.$?@][A-Za-z0-9_.$?@]*)\s+proc\b",
    re.IGNORECASE,
)
_MACRO_RE = re.compile(
    r"^\s*(?:%macro|macro)\s+(?P<name>[A-Za-z_.$?@][A-Za-z0-9_.$?@]*)\b",
    re.IGNORECASE,
)
_SECTION_DIRECTIVE_RE = re.compile(
    r"^\s*(?:section|segment)\s+(?P<name>[^\s;]+)",
    re.IGNORECASE,
)
_PREPROCESSOR_DIRECTIVE_RE = re.compile(
    r"^\s*#\s*(?:define|elif|else|endif|if|ifdef|ifndef|include|pragma)\b",
    re.IGNORECASE,
)
_WHOLE_LINE_HASH_COMMENT_RE = re.compile(r"^\s*#")
_NAME_TOKEN_RE = re.compile(r"[A-Za-z_.$?@][A-Za-z0-9_.$?@:-]*")


def _replace_with_spaces(value: str) -> str:
    return "".join("\n" if character == "\n" else " " for character in value)


def _normalize_repository_relative_path(value: str) -> str:
    raw_parts = PurePosixPath(str(value).replace("\\", "/")).parts
    normalized_parts: list[str] = []
    for part in raw_parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if normalized_parts:
                normalized_parts.pop()
            continue
        normalized_parts.append(part)
    return "/".join(normalized_parts)


def normalize_identifier(raw_name: str) -> str:
    normalized = str(raw_name or "").strip().strip(":")
    if normalized.startswith("%"):
        normalized = normalized[1:]
    if "@" in normalized and not normalized.startswith("@@"):
        normalized = normalized.split("@", 1)[0]
    return normalized.strip().lower()


def _is_local_symbol_name(symbol_name: str) -> bool:
    return (
        not symbol_name
        or symbol_name.startswith(".")
        or symbol_name.startswith("@@")
        or symbol_name in {"$", "$$"}
        or re.fullmatch(r"\d+\$?", symbol_name) is not None
    )


def _is_numeric_token(value: str) -> bool:
    normalized = value.lower().strip()
    return bool(
        normalized
        and (
            normalized.isdigit()
            or normalized.startswith("0x")
            or normalized.endswith("h")
            or normalized.startswith("$")
        )
    )


def _strip_inline_comment(raw_line: str) -> str:
    in_single = False
    in_double = False
    escaped = False
    for index, character in enumerate(raw_line):
        if character == "\\" and (in_single or in_double):
            escaped = not escaped
            continue
        if character == "'" and not in_double and not escaped:
            in_single = not in_single
        elif character == '"' and not in_single and not escaped:
            in_double = not in_double
        elif not in_single and not in_double:
            if character == ";":
                return raw_line[:index]
            if raw_line[index : index + 2] == "//":
                return raw_line[:index]
        escaped = False
    return raw_line


def strip_comments(text: str) -> str:
    without_block_comments = re.sub(
        r"/\*.*?\*/",
        lambda match: _replace_with_spaces(match.group(0)),
        text,
        flags=re.DOTALL,
    )
    stripped_lines: list[str] = []
    for raw_line in without_block_comments.splitlines():
        if _WHOLE_LINE_HASH_COMMENT_RE.match(raw_line) and not _PREPROCESSOR_DIRECTIVE_RE.match(
            raw_line
        ):
            stripped_lines.append("")
            continue
        stripped_lines.append(_strip_inline_comment(raw_line))
    return "\n".join(stripped_lines)


def _is_probable_instruction(opcode: str) -> bool:
    normalized = str(opcode or "").strip().lstrip(".").lower()
    return bool(
        normalized
        and (
            normalized in _COMMON_MNEMONICS
            or normalized in _CONTROL_TRANSFER_OPCODES
            or (normalized.startswith("j") and len(normalized) > 1)
            or (normalized.startswith("b") and len(normalized) > 1 and normalized != "byte")
        )
    )


def has_assembly_markers(text: str) -> bool:
    stripped_text = strip_comments(text)
    if any(
        pattern.search(stripped_text)
        for pattern in (_INCLUDE_RE, _PROC_RE, _MACRO_RE, _SECTION_DIRECTIVE_RE)
    ):
        return True
    instruction_count = 0
    for raw_line in stripped_text.splitlines():
        stripped_line = raw_line.strip()
        if not stripped_line:
            continue
        if stripped_line.lower() in _TEXT_SECTION_TOKENS | _DATA_SECTION_TOKENS:
            return True
        proc_match = _PROC_RE.match(stripped_line)
        if proc_match is not None:
            return True
        label_match = _LABEL_RE.match(stripped_line)
        instruction_body = stripped_line
        if label_match is not None:
            instruction_body = str(label_match.group("body") or "").strip()
            if not instruction_body:
                continue
        opcode = instruction_body.split(None, 1)[0].strip().lstrip(".").lower()
        if opcode in _COMMON_DIRECTIVES:
            return True
        if _is_probable_instruction(opcode):
            instruction_count += 1
            if instruction_count >= 2:
                return True
    return False


def is_probable_assembly_source(*, path: PurePosixPath | Path | str, text: str) -> bool:
    suffix = PurePosixPath(str(path).replace("\\", "/")).suffix.lower()
    if suffix not in _KNOWN_ASSEMBLY_SUFFIXES:
        return False
    if suffix in {".asm", ".s", ".a51"}:
        return True
    return has_assembly_markers(text)


def _symbol_name_is_eligible(symbol_name: str) -> bool:
    return bool(
        symbol_name
        and not _is_local_symbol_name(symbol_name)
        and symbol_name not in RESERVED_SYMBOL_NAMES
        and symbol_name not in _REGISTER_NAMES
        and not _is_numeric_token(symbol_name)
    )


def _first_token(raw_value: str) -> str:
    normalized_value = str(raw_value or "").strip()
    if not normalized_value:
        return ""
    return normalized_value.split(None, 1)[0].strip().lower()


def _label_symbol_kind(
    *,
    symbol_name: str,
    body: str,
    current_section: str,
) -> str:
    if symbol_name in _ENTRYPOINT_NAMES:
        return "function"
    opcode = _first_token(body)
    if opcode in _DATA_DIRECTIVES:
        return "type"
    if _is_probable_instruction(opcode) or opcode == "proc":
        return "function"
    if current_section in _DATA_SECTION_TOKENS:
        return "type"
    return "function" if current_section in _TEXT_SECTION_TOKENS else "type"
