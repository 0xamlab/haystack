from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
import re


_LANGUAGE_EXTENSION_OVERRIDES = {
    "batchfile": "bat",
    "blade": "blade.php",
    "cobol": "cbl",
    "cpp": "cpp",
    "cs": "cs",
    "delphi": "pas",
    "dockerfile": "Dockerfile",
    "emacslisp": "el",
    "fish": "fish",
    "fortran": "f90",
    "handlebars": "hbs",
    "javascript": "js",
    "jinja": "j2",
    "jsx": "jsx",
    "less": "less",
    "makefile": "Makefile",
    "mojo": "mojo",
    "objectivec": "m",
    "openqasm": "qasm",
    "perl": "pl",
    "powershell": "ps1",
    "protobuf": "proto",
    "python": "py",
    "qsharp": "qs",
    "racket": "rkt",
    "robotframework": "robot",
    "ruby": "rb",
    "rust": "rs",
    "sass": "sass",
    "scss": "scss",
    "shell": "sh",
    "solidity": "sol",
    "sql": "sql",
    "stylus": "styl",
    "systemverilog": "sv",
    "tex": "tex",
    "toml": "toml",
    "tsql": "sql",
    "twig": "twig",
    "typescript": "ts",
    "vbscript": "vbs",
    "verilog": "v",
    "visualbasic": "vb",
    "vue": "vue",
    "wgsl": "wgsl",
    "xml": "xml",
    "yaml": "yml",
    "zig": "zig",
}


@dataclass(frozen=True)
class ClineLiveMatrixFixture:
    language: str
    target_file: str
    initial_content: str


def _language_slug(language: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", language.strip().lower()).strip("_")
    return normalized or "language"


def _extension_for_language(language: str) -> str:
    slug = _language_slug(language)
    return _LANGUAGE_EXTENSION_OVERRIDES.get(slug, slug)


def build_live_matrix_fixture(*, language: str, rank: int) -> ClineLiveMatrixFixture:
    if not isinstance(rank, int) or isinstance(rank, bool) or rank <= 0:
        raise ValueError("rank must be a positive integer")
    if not isinstance(language, str) or not language.strip():
        raise ValueError("language must be a non-empty string")
    slug = _language_slug(language)
    extension = _extension_for_language(language)
    filename = "main" if extension != "Dockerfile" and extension != "Makefile" else extension
    suffix = "" if extension in {"Dockerfile", "Makefile"} else f".{extension}"
    target_path = PurePosixPath("matrix") / f"{rank:03d}_{slug}" / f"{filename}{suffix}"
    return ClineLiveMatrixFixture(
        language=language.strip(),
        target_file=str(target_path),
        initial_content="alpha\n",
    )
