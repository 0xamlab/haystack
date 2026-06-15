# ruff: noqa: I001
from __future__ import annotations
import inspect
from collections.abc import Callable, Iterable, Iterator, Sequence
from functools import lru_cache
from pathlib import Path, PurePosixPath
from apps.api_server.services.repository_intelligence_contracts import _ModuleIndexLookup
from apps.api_server.services.repository_intelligence_indexing_paths import (
    _normalize_repository_relative_path,
)
from apps.api_server.services.repository_intelligence_indexing import (
    _JS_LIKE_SUFFIXES,
    _MODULE_INDEX_LOOKUP_CACHE,
    _MODULE_INDEX_LOOKUP_CACHE_LIMIT,
    _RAKU_SUFFIXES,
)
def _estimate_tokens(text: str) -> int:
    return max(1, (len(text.encode("utf-8")) + 3) // 4)
def _module_aliases_for_path(file_path: str) -> set[str]:
    path = PurePosixPath(file_path)
    suffix_lower = path.suffix.lower()
    if suffix_lower == ".m":
        return set()
    aliases = {path.stem, file_path}
    without_suffix_path = str(path.with_suffix(""))
    without_suffix = without_suffix_path.replace("/", ".")
    aliases.add(without_suffix)
    if path.name == "__init__.py":
        aliases.add(str(path.parent).replace("/", "."))
    if suffix_lower in {
        ".abap",
        ".ada",
        ".adb",
        ".ads",
        ".awk",
        ".auk",
        ".c",
        ".cbl",
        ".cc",
        ".cpp",
        ".pxd",
        ".pxi",
        ".pyx",
        ".cob",
        ".cobol",
        ".coffee",
        ".cfc",
        ".cfm",
        ".cfml",
        ".cpy",
        ".cxx",
        ".clj",
        ".cljc",
        ".cljs",
        ".cr",
        ".dart",
        ".erl",
        ".ex",
        ".exs",
        ".fs",
        ".fsi",
        ".fsx",
        ".h",
        ".hack",
        ".hh",
        ".hhi",
        ".hpp",
        ".hrl",
        ".hs",
        ".hsc",
        ".hxx",
        ".ipp",
        ".jl",
        ".js",
        ".jsx",
        ".ksh",
        ".lhs",
        ".litcoffee",
        ".lisp",
        ".lsp",
        ".lvclass",
        ".lvlib",
        ".lvproj",
        ".lua",
        ".luau",
        ".mawk",
        ".moon",
        ".mj",
        ".ml",
        ".mll",
        ".mly",
        ".templ",
        ".thrift",
        ".vcl",
        ".re",
        ".rei",
        ".mli",
        ".mojo",
        ".mq5",
        ".mqh",
        ".gms",
        ".nix",
        ".odin",
        ".factor",
        ".cairo",
        ".pas",
        ".php",
        ".pl",
        ".pkb",
        ".pks",
        ".pm",
        ".pp",
        ".prolog",
        ".prg",
        ".prc",
        ".pls",
        ".purs",
        *_RAKU_SUFFIXES,
        ".ps1",
        ".psgi",
        ".psm1",
        ".py",
        ".r",
        ".rb",
        ".rpg",
        ".rpginc",
        ".rpgle",
        ".rpgleinc",
        ".sas",
        ".scad",
        ".sml",
        ".sol",
        ".apex",
        ".applescript",
        ".sig",
        ".sh",
        ".scpt",
        ".st",
        ".sqlrpg",
        ".sqlrpgle",
        ".sql",
        ".sw",
        ".swift",
        ".tcl",
        ".tm",
        ".trigger",
        ".trg",
        ".tpp",
        ".ts",
        ".tsx",
        ".v",
        ".fun",
        ".vala",
        ".vapi",
        ".vb",
        ".vbe",
        ".vi",
        ".vim",
        ".vit",
        ".bas",
        ".cls",
        ".ctl",
        ".frm",
        ".vbp",
        ".vbs",
        ".wl",
        ".wls",
        ".wsf",
        ".asd", ".cwl", ".dem", ".dockerfile", ".dot", ".dwl", ".feature", ".g4", ".gp", ".gnuplot", ".gv", ".mmd", ".mermaid", ".plt", ".puml", ".plantuml", ".iuml", ".nf", ".fnl", ".fnlm", ".qasm", ".ql", ".qll", ".brs", ".gawk", ".gleam", ".hy", ".wren", ".janet", ".bal", ".bicep", ".chpl", ".tla", ".lgt", ".logtalk", ".cue", ".proto", ".move", ".roc", ".stan", ".cu", ".cuh", ".hlsl", ".hlsli", ".wgsl", ".j2", ".jinja", ".jinja2", ".liquid", ".hbs", ".handlebars", ".mustache", ".njk", ".nunj", ".nunjucks", ".twig", ".haml", ".slim", ".tpl", ".erb", ".rhtml", ".pug", ".jade", ".ejs", ".scss", ".less", ".styl", ".svelte", ".astro", ".shader", ".fx", ".fxh", ".cginc", ".compute", ".typ", ".tex", ".sty", ".ltx", ".dtx", ".rst", ".rest", ".adoc", ".asciidoc", ".asc", ".org",
        ".agda", ".agda-lib", ".nu", ".nawk", ".dpk", ".dpr", ".lpr", ".zsh",
        ".zsh-theme",
        ".zig",
        ".cs",
    }:
        aliases.add(without_suffix_path)
    if suffix_lower in _JS_LIKE_SUFFIXES and path.stem == "index":
        parent = str(path.parent)
        if parent and parent != ".":
            aliases.add(parent)
            aliases.add(parent.replace("/", "."))
    if suffix_lower == ".go":
        parent = str(path.parent)
        if parent and parent != ".":
            aliases.add(parent)
            aliases.add(parent.replace("/", "."))
    if suffix_lower in {".rs", ".cairo", ".sw"} and path.stem in {"mod", "lib", "main"}:
        parent = str(path.parent)
        if parent and parent != ".":
            aliases.add(parent)
            aliases.add(parent.replace("/", "."))
        if path.stem in {"lib", "main"}:
            aliases.add("crate")
    if suffix_lower in {".java", ".kt", ".kts", ".scala", ".pde"}:
        source_parts = list(path.parts)
        marker_index = None
        for index, part in enumerate(source_parts):
            lowered_part = part.lower()
            if lowered_part in {"java", "kotlin"} or lowered_part.startswith("scala"):
                marker_index = index
                break
        if marker_index is not None:
            package_parts = list(source_parts[marker_index + 1 : -1])
            if suffix_lower == ".scala" and path.stem == "package":
                if package_parts:
                    aliases.add(".".join(package_parts))
            elif path.stem != "package-info":
                package_parts.append(path.stem)
                if package_parts:
                    aliases.add(".".join(package_parts))
    if suffix_lower in {".ex", ".exs"}:
        source_parts = list(path.parts)
        if "lib" in source_parts:
            lib_index = source_parts.index("lib")
            module_parts = list(source_parts[lib_index + 1 : -1])
            stem_parts = [part for part in path.stem.split(".") if part]
            module_parts.extend(stem_parts)
            camelized_parts = [
                "".join(piece.capitalize() for piece in segment.split("_") if piece)
                for segment in module_parts
                if segment
            ]
            if camelized_parts:
                aliases.add(".".join(camelized_parts))
    return {alias for alias in aliases if alias}
def _module_index_values(module_index: dict[str, str]) -> tuple[str, ...]:
    return _module_index_lookup(module_index).values
def _module_index_lookup(module_index: dict[str, str]) -> _ModuleIndexLookup:
    cache_key = tuple(sorted(set(module_index.values())))
    cached_lookup = _MODULE_INDEX_LOOKUP_CACHE.get(cache_key)
    if cached_lookup is not None:
        return cached_lookup
    values = cache_key
    exact_paths: dict[str, str] = {}
    suffix_paths: dict[str, str] = {}
    directory_suffix_paths: dict[str, str] = {}
    for file_path in values:
        lowered_file_path = file_path.lower()
        exact_paths.setdefault(lowered_file_path, file_path)
        path_parts = PurePosixPath(lowered_file_path).parts
        for start in range(len(path_parts)):
            suffix_paths.setdefault("/".join(path_parts[start:]), file_path)
        directory_parts = path_parts[:-1]
        for start in range(len(directory_parts)):
            directory_suffix_paths.setdefault("/".join(directory_parts[start:]), file_path)
    lookup = _ModuleIndexLookup(
        values=values,
        exact_paths=exact_paths,
        suffix_paths=suffix_paths,
        directory_suffix_paths=directory_suffix_paths,
    )
    if len(_MODULE_INDEX_LOOKUP_CACHE) >= _MODULE_INDEX_LOOKUP_CACHE_LIMIT:
        _MODULE_INDEX_LOOKUP_CACHE.clear()
    _MODULE_INDEX_LOOKUP_CACHE[cache_key] = lookup
    return lookup
def _module_index_aliases_for_file(module_index: dict[str, str], file_path: str) -> set[str]:
    return {
        alias
        for alias, resolved_path in module_index.items()
        if resolved_path == file_path
    }


@lru_cache(maxsize=512)
def _root_scoped_module_alias_builder_accepts_text(
    builder: Callable[..., Iterable[str]],
) -> bool:
    try:
        return "text" in inspect.signature(builder).parameters
    except (TypeError, ValueError):
        return False


def _iter_root_scoped_module_aliases(
    *,
    root_path: Path,
    file_path: str,
    root_scoped_module_alias_builders: Sequence[Callable[..., Iterable[str]]],
    text: str | None = None,
) -> Iterator[str]:
    for builder in root_scoped_module_alias_builders:
        if text is not None and _root_scoped_module_alias_builder_accepts_text(builder):
            yield from builder(root_path=root_path, file_path=file_path, text=text)
            continue
        yield from builder(root_path=root_path, file_path=file_path)
def _read_repository_relative_text(*, root_path: Path, file_path: str) -> str | None:
    try:
        return (root_path / file_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
def _resolve_suffix_match(*, module_index: dict[str, str], suffixes: Sequence[str]) -> str | None:
    normalized_suffixes = []
    for suffix in suffixes:
        normalized_suffix = _normalize_repository_relative_path(suffix)
        if normalized_suffix:
            normalized_suffixes.append(normalized_suffix)
    if not normalized_suffixes:
        return None
    lookup = _module_index_lookup(module_index)
    for suffix in normalized_suffixes:
        lowered_suffix = suffix.lower()
        direct_match = lookup.exact_paths.get(lowered_suffix)
        if direct_match is not None:
            return direct_match
        suffix_match = lookup.suffix_paths.get(lowered_suffix)
        if suffix_match is not None:
            return suffix_match
    return None
def _resolve_directory_prefix_match(
    *, module_index: dict[str, str], prefixes: Sequence[str]
) -> str | None:
    normalized_prefixes = []
    for prefix in prefixes:
        normalized_prefix = _normalize_repository_relative_path(prefix)
        if normalized_prefix:
            normalized_prefixes.append(normalized_prefix)
    if not normalized_prefixes:
        return None
    lookup = _module_index_lookup(module_index)
    for prefix in normalized_prefixes:
        prefix_match = lookup.directory_suffix_paths.get(prefix.lower())
        if prefix_match is not None:
            return prefix_match
    return None
def _build_module_index(
    file_paths: Sequence[str],
    *,
    root_path: Path | None = None,
    root_scoped_module_alias_builders: Sequence[Callable[..., Iterable[str]]] = (),
    root_scoped_module_alias_builder_selector: Callable[..., Sequence[Callable[..., Iterable[str]]]] | None = None,
    module_index_extenders: Sequence[Callable[..., None]] = (),
) -> dict[str, str]:
    index: dict[str, str] = {}
    for file_path in file_paths:
        repository_relative_text: str | None = None
        for alias in _module_aliases_for_path(file_path):
            index.setdefault(alias, file_path)
        if root_path is not None and root_scoped_module_alias_builders:
            selected_root_scoped_module_alias_builders = root_scoped_module_alias_builders
            repository_relative_text = _read_repository_relative_text(
                root_path=root_path,
                file_path=file_path,
            )
            if root_scoped_module_alias_builder_selector is not None:
                selected_root_scoped_module_alias_builders = (
                    root_scoped_module_alias_builder_selector(
                        root_path=root_path,
                        file_path=file_path,
                        text=repository_relative_text,
                    )
                )
            for alias in _iter_root_scoped_module_aliases(
                root_path=root_path,
                file_path=file_path,
                root_scoped_module_alias_builders=selected_root_scoped_module_alias_builders,
                text=repository_relative_text,
            ):
                index.setdefault(alias, file_path)
    if root_path is not None:
        for extender in module_index_extenders:
            extender(root_path=root_path, file_paths=file_paths, index=index)
    return index
