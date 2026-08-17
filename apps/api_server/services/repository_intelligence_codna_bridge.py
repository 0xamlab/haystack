"""Bridge algenta's repo-intelligence language adapters into codna's codeunits seam.

codna extracts structural units via stdlib ``ast`` (Python) plus tree-sitter grammars for the
common languages. Algenta's repository-intelligence adapter layer covers ~240 more languages with
regex-based structural extraction. This bridge plugs every adapter that follows the standard
``parse_file(file_path, text, module_index, *, stable_identifier, resolve_import)`` contract into
codna's extractor registry, so ``codna memory`` / ``codna impact`` can index repos in languages
codna has no grammar for — Mojo first among them.

Deliberate constraints:
  * Never shadow an extractor codna already registered (its ast Python and any installed
    tree-sitter grammar win — they are structurally stronger than regex).
  * Fail open per adapter: one broken module is recorded and skipped, never fatal.
  * Regex adapters are retrieval-grade, not compiler-grade: structural symbols + a bounded source
    slice, matching codeunits' unit-text convention.
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
from typing import Any, Callable, Iterator

ADAPTERS_PACKAGE = "apps.api_server.services.repository_intelligence_adapters"

# Standard-contract adapters and the file extensions they speak. Family modules cover several.
# Collisions within this table resolve first-listed-wins (e.g. matlab keeps ``.m``, wolfram gets
# ``.wl``); collisions with codna's own registrations are skipped entirely at register time.
ADAPTER_EXTENSIONS: dict[str, tuple[str, ...]] = {
    "ada": (".adb", ".ads"),
    "apex": (".cls", ".trigger"),
    "assembly": (".asm", ".s"),
    "c_family": (".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hh"),
    "clojure": (".clj", ".cljs", ".cljc", ".edn"),
    "cobol": (".cob", ".cbl"),
    "crystal": (".cr"),
    "csharp": (".cs"),
    "d_language": (".d",),
    "dart_language": (".dart",),
    "elixir": (".ex", ".exs"),
    "erlang": (".erl", ".hrl"),
    "fortran": (".f", ".f90", ".f95", ".f03", ".for"),
    "foxpro": (".prg",),
    "fsharp": (".fs", ".fsx"),
    "gdscript": (".gd",),
    "go_language": (".go",),
    "haskell": (".hs", ".lhs"),
    "js_like": (".js", ".jsx", ".mjs", ".ts", ".tsx"),
    "julia": (".jl",),
    "jvm": (".java", ".kt", ".scala", ".groovy"),
    "lua": (".lua",),
    "matlab": (".m",),
    "ml": (".sml",),
    "mojo_language": (".mojo",),
    "nim": (".nim",),
    "ocaml": (".ml", ".mli"),
    "perl": (".pl", ".pm"),
    "plsql": (".pls", ".pks", ".pkb"),
    "powershell": (".ps1", ".psm1"),
    "python_language": (".py",),
    "r_language": (".r", ".R"),
    "rpg": (".rpgle",),
    "ruby": (".rb",),
    "rust_language": (".rs",),
    "sas": (".sas",),
    "shell": (".sh", ".bash"),
    "sql": (".sql",),
    "swift": (".swift",),
    "visual_basic": (".vb", ".bas"),
    "wolfram": (".wl",),
    "zig": (".zig",),
}

# Adapter symbol kinds -> codna's symbol_type vocabulary (module/class/function/method/test).
_CLASS_KINDS = {"class", "struct", "trait", "interface", "record", "type"}

_MAX_UNIT_CHARS = 2000   # mirrors codna.codeunits._MAX_UNIT_CHARS — bound the indexed text slice
_MAX_SLICE_LINES = 40    # regex adapters report only a start line; cap the source window


def _stable_identifier(kind: str, payload: Any) -> str:
    return hashlib.sha256(f"{kind}:{payload}".encode("utf-8")).hexdigest()[:24]


def _resolve_import(import_target: str, module_index: dict[str, str]) -> str | None:
    return module_index.get(import_target)


def _symbol_type(name: str, kind: str) -> str:
    if name.startswith("test_"):
        return "test"
    if kind in _CLASS_KINDS:
        return "class"
    return "function"


def _unit_text(name: str, signature: str | None, source_lines: list[str], start_line: int) -> str:
    lo = max(0, start_line - 1)
    segment = "\n".join(source_lines[lo:lo + _MAX_SLICE_LINES])
    header = signature if signature and signature != name else name
    return f"{name}\n{header}\n{segment}".strip()[:_MAX_UNIT_CHARS]


class AlgentaAdapterExtractor:
    """codna LanguageExtractor backed by one algenta repo-intelligence adapter."""

    def __init__(self, language: str, extensions: tuple[str, ...], adapter: Any) -> None:
        self.language = language
        self.extensions = extensions
        self._adapter = adapter

    def extract(self, repo_id: str, relpath: str, source: str) -> Iterator[Any]:
        symbols, _dependencies, _references = self._adapter.parse_file(
            relpath, source, {},
            stable_identifier=_stable_identifier,
            resolve_import=_resolve_import,
        )
        lines = source.splitlines()
        seen: set[str] = set()
        for symbol in symbols:
            name = str(getattr(symbol, "symbol_name", "") or "")
            if not name:
                continue
            qual = name
            if qual in seen:                      # same-named symbols: keep ids unique per file
                qual = f"{name}@{getattr(symbol, 'start_line', 0)}"
            seen.add(qual)
            kind = str(getattr(symbol, "symbol_kind", "") or "")
            text = _unit_text(name, getattr(symbol, "signature", None), lines,
                              int(getattr(symbol, "start_line", 1) or 1))
            # Constructed duck-typed: the caller passes codna's CodeUnit class in at registration
            # time (stored on the instance by register_algenta_adapters).
            yield self._code_unit(
                id=f"{repo_id}:{relpath}:{qual}",
                text=text or qual,
                path=relpath,
                language=self.language,
                symbol_type=_symbol_type(name, kind),
                qualname=qual,
            )

    def _code_unit(self, **kwargs: Any) -> Any:
        return self._CodeUnit(**kwargs)


def _adapter_has_contract(module: Any) -> bool:
    fn = getattr(module, "parse_file", None)
    if not callable(fn):
        return False
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    return {"file_path", "text", "module_index", "stable_identifier", "resolve_import"} <= set(params)


def discover_adapters(*, languages: tuple[str, ...] | None = None,
                      record_error: Callable[[str, str], None] | None = None) -> dict[str, Any]:
    """Import every standard-contract adapter listed in ADAPTER_EXTENSIONS (or the ``languages``
    subset). Returns ``{language: module}``; anything broken or missing is recorded and skipped."""
    found: dict[str, Any] = {}
    selected = languages if languages is not None else tuple(ADAPTER_EXTENSIONS)
    for language in selected:
        if language not in ADAPTER_EXTENSIONS:
            if record_error is not None:
                record_error(language, f"unknown adapter language: {language}")
            continue
        try:
            module = importlib.import_module(f"{ADAPTERS_PACKAGE}.{language}")
        except Exception as exc:  # noqa: BLE001 — one broken adapter must not sink the rest
            if record_error is not None:
                record_error(language, f"import failed: {type(exc).__name__}: {exc}")
            continue
        if not _adapter_has_contract(module):
            if record_error is not None:
                record_error(language, "adapter lacks the standard parse_file contract")
            continue
        found[language] = module
    return found


def register_algenta_adapters(codeunits: Any, *,
                              languages: tuple[str, ...] | None = None,
                              record_error: Callable[[str, str], None] | None = None) -> set[str]:
    """Register algenta adapter extractors into a codna ``codeunits`` module.

    Returns the set of languages that went live. Extensions codna already registered (its ast
    Python extractor, installed tree-sitter grammars) are never shadowed — the regex adapters only
    fill gaps. Never raises: every failure path goes through ``record_error``."""
    registered: set[str] = set()
    existing_extensions = set(getattr(codeunits, "_EXTRACTORS", {}))
    code_unit_cls = getattr(codeunits, "CodeUnit", None)
    if code_unit_cls is None:
        if record_error is not None:
            record_error("codna", "codeunits module has no CodeUnit class")
        return registered
    for language, module in discover_adapters(languages=languages, record_error=record_error).items():
        extensions = tuple(
            ext for ext in ADAPTER_EXTENSIONS[language] if ext not in existing_extensions
        )
        if not extensions:
            continue   # every extension this adapter speaks is already better-served by codna
        extractor = AlgentaAdapterExtractor(language, extensions, module)
        extractor._CodeUnit = code_unit_cls  # noqa: SLF001 — injected constructor seam
        try:
            codeunits.register_extractor(extractor)
        except Exception as exc:  # noqa: BLE001
            if record_error is not None:
                record_error(language, f"registration failed: {type(exc).__name__}: {exc}")
            continue
        existing_extensions.update(extensions)
        registered.add(language)
    return registered
