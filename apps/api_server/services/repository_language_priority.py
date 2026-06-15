from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

# Keep the public-repo probe aligned to a stable popularity order so multi-language
# repositories start from the most common supported languages first.
REPOSITORY_LANGUAGE_POPULARITY_ORDER: tuple[str, ...] = (
    "typescript",
    "python",
    "javascript",
    "vue",
    "svelte",
    "astro",
    "node",
    "java",
    "cs",
    "dotnet",
    "asp.net",
    "php",
    "hack",
    "shell",
    "graphql",
    "fish",
    "answer set programming",
    "alloy",
    "aiken",
    "asl",
    "ats",
    "1centerprise",
    "apacheconf",
    "nginx",
    "aidl",
    "4d",
    "c",
    "dockerfile",
    "cpp",
    "cuda",
    "opencl",
    "cmake",
    "protobuf",
    "thrift",
    "meson",
    "qmake",
    "qml",
    "cython",
    "scratch",
    "go",
    "rust",
    "assembly",
    "ruby",
    "prolog",
    "logtalk",
    "chapel",
    "eiffel",
    "swift",
    "scss",
    "sass",
    "less",
    "stylus",
    "jinja",
    "liquid",
    "handlebars",
    "pug",
    "ejs",
    "blade",
    "erb",
    "mustache",
    "nunjucks",
    "twig",
    "templ",
    "haml",
    "slim",
    "smarty",
    "freemarker",
    "mako",
    "tex",
    "rst",
    "asciidoc",
    "org",
    "delphi",
    "sql",
    "tsql",
    "vb6",
    "vba",
    "plsql",
    "plpgsql",
    "ada",
    "cobol",
    "sas",
    "ml",
    "sml",
    "abap",
    "abapcds",
    "kotlin",
    "scala",
    "dart",
    "groovy",
    "xtend",
    "aspectj",
    "codeql",
    "maven",
    "gnuplot",
    "dataweave",
    "brightscript",
    "common workflow language",
    "earthly",
    "ampl",
    "openedge",
    "nsis",
    "processing",
    "ballerina",
    "webassembly",
    "nextflow",
    "robotframework",
    "gherkin",
    "antlr",
    "typst",
    "luau",
    "lua",
    "lisp",
    "hy",
    "wren",
    "janet",
    "fennel",
    "vyper",
    "clarity",
    "circom",
    "cairo",
    "scheme",
    "racket",
    "gdscript",
    "postscript",
    "pawn",
    "smali",
    "motoko",
    "m4",
    "dm",
    "vbscript",
    "elixir",
    "ladder",
    "solidity",
    "glsl",
    "hlsl",
    "wgsl",
    "shaderlab",
    "verilog",
    "systemverilog",
    "vhdl",
    "qsharp",
    "erlang",
    "clojurescript",
    "clojure",
    "r",
    "cfml",
    "xpp",
    "al",
    "matlab",
    "objectivec",
    "julia",
    "stan",
    "haskell",
    "lean",
    "coq",
    "dafny",
    "agda",
    "idris",
    "tlaplus",
    "haxe",
    "move",
    "sway",
    "odin",
    "purescript",
    "rescript",
    "reasonml",
    "roc",
    "moonbit",
    "modelica",
    "gleam",
    "ocaml",
    "perl",
    "raku",
    "powershell",
    "just",
    "makefile",
    "batchfile",
    "autohotkey",
    "autoit",
    "squirrel",
    "starlark",
    "hcl",
    "vcl",
    "puppet",
    "bitbake",
    "bicep",
    "cue",
    "dhall",
    "rego",
    "yara",
    "nix",
    "jsonnet",
    "nushell",
    "pkl",
    "apex",
    "labview",
    "wolfram",
    "rpg",
    "actionscript",
    "angelscript",
    "applescript",
    "awk",
    "coffeescript",
    "moonscript",
    "zig",
    "gml",
    "nim",
    "crystal",
    "fsharp",
    "visualbasic",
    "foxpro",
    "pascal",
    "freebasic",
    "purebasic",
    "d",
    "elm",
    "emacslisp",
    "vimscript",
    "fortran",
    "mojo",
    "tcl",
    "v",
    "vala",
    "smalltalk",
    "pony",
    "mql5",
    "gams",
    "openscad",
    "factor",
    "ocamllex",
    "ocamlyacc",
    "xslt",
    "yacc",
    "lex",
    "xquery",
    "q",
    "j",
    "graphviz",
    "mermaid",
    "plantuml",
    "openqasm",
    "forth",
    "isabelle",
    "mercury",
    "red",
    "apl",
    "hoon",
    "sed",
    "metal",
    "bqn",
    "rebol",
    "json",
    "yaml",
    "toml",
    "xml",
    "html",
    "css",
    "markdown",
    "edn",
    "rockspec",
    "opam",
    "unknown",
    "txt",
)

NON_REAL_REPOSITORY_LANGUAGE_LABELS = frozenset(
    {
        "node",
        "dotnet",
        "json",
        "yaml",
        "toml",
        "xml",
        "html",
        "css",
        "markdown",
        "edn",
        "rockspec",
        "opam",
        "unknown",
        "txt",
    }
)
DEFAULT_REAL_LANGUAGE_RANK_TARGET = 250
UNSUPPORTED_RANKED_REAL_REPOSITORY_LANGUAGES = frozenset()

# The language popularity alias map was moved into a sibling module to keep this
# module under the per-file line budget; re-export it so the public import surface
# (`from ...repository_language_priority import _LANGUAGE_POPULARITY_ALIASES`) is
# unchanged and `canonical_repository_language` below keeps resolving it.
from apps.api_server.services.repository_language_priority_aliases import (  # noqa: E402
    _LANGUAGE_POPULARITY_ALIASES,
)


_LANGUAGE_POPULARITY_INDEX = {
    language: index for index, language in enumerate(REPOSITORY_LANGUAGE_POPULARITY_ORDER)
}
_UNKNOWN_LANGUAGE_PRIORITY = len(REPOSITORY_LANGUAGE_POPULARITY_ORDER) + 1


@dataclass(frozen=True)
class RepositoryLanguageSupportProgress:
    supported_real_languages: tuple[str, ...]
    supported_real_language_count: int
    ranked_target_language_count: int
    requested_ranked_target_language_count: int
    available_ranked_real_language_count: int
    target_clamped_to_available_ranked_real_languages: bool
    progress_fraction: float
    progress_label: str


def canonical_repository_language(language: str | None) -> str:
    normalized = str(language or "").strip().lower()
    if not normalized:
        return ""
    return _LANGUAGE_POPULARITY_ALIASES.get(normalized, normalized)


def repository_language_priority(language: str | None) -> tuple[int, str]:
    canonical = canonical_repository_language(language)
    if not canonical:
        return _UNKNOWN_LANGUAGE_PRIORITY, ""
    return _LANGUAGE_POPULARITY_INDEX.get(canonical, _UNKNOWN_LANGUAGE_PRIORITY), canonical


def supported_repository_languages(*, include_non_real: bool = False) -> tuple[str, ...]:
    if include_non_real:
        return tuple(
            language
            for language in REPOSITORY_LANGUAGE_POPULARITY_ORDER
            if language not in UNSUPPORTED_RANKED_REAL_REPOSITORY_LANGUAGES
        )
    return tuple(
        language
        for language in ranked_real_repository_languages()
        if language not in UNSUPPORTED_RANKED_REAL_REPOSITORY_LANGUAGES
    )


def ranked_real_repository_languages() -> tuple[str, ...]:
    return tuple(
        language
        for language in REPOSITORY_LANGUAGE_POPULARITY_ORDER
        if language not in NON_REAL_REPOSITORY_LANGUAGE_LABELS
    )


def repository_language_support_progress(
    *,
    ranked_target_language_count: int = DEFAULT_REAL_LANGUAGE_RANK_TARGET,
) -> RepositoryLanguageSupportProgress:
    if ranked_target_language_count <= 0:
        raise ValueError("ranked_target_language_count must be positive")
    requested_ranked_target_language_count = ranked_target_language_count
    available_ranked_real_language_count = len(ranked_real_repository_languages())
    supported_real_languages = supported_repository_languages()
    supported_real_language_count = len(supported_real_languages)
    effective_ranked_target_language_count = ranked_target_language_count
    if available_ranked_real_language_count > 0:
        effective_ranked_target_language_count = min(
            effective_ranked_target_language_count,
            available_ranked_real_language_count,
        )
    effective_ranked_target_language_count = max(
        effective_ranked_target_language_count,
        supported_real_language_count,
    )
    return RepositoryLanguageSupportProgress(
        supported_real_languages=supported_real_languages,
        supported_real_language_count=supported_real_language_count,
        ranked_target_language_count=effective_ranked_target_language_count,
        requested_ranked_target_language_count=requested_ranked_target_language_count,
        available_ranked_real_language_count=available_ranked_real_language_count,
        target_clamped_to_available_ranked_real_languages=(
            effective_ranked_target_language_count != requested_ranked_target_language_count
        ),
        progress_fraction=(
            supported_real_language_count / float(effective_ranked_target_language_count)
        ),
        progress_label=(
            f"{supported_real_language_count} / {effective_ranked_target_language_count}"
        ),
    )


def sort_repository_languages(languages: Iterable[str]) -> list[str]:
    return sort_repository_languages_by_score(languages, scores={})


def sort_repository_languages_by_score(
    languages: Iterable[str],
    *,
    scores: Mapping[str, int | float],
) -> list[str]:
    canonical_names: dict[str, str] = {}
    for language in languages:
        canonical = canonical_repository_language(language)
        if not canonical:
            continue
        canonical_names.setdefault(canonical, canonical)
    normalized_scores: dict[str, float] = {}
    for language, score in scores.items():
        canonical = canonical_repository_language(language)
        if not canonical:
            continue
        normalized_scores[canonical] = normalized_scores.get(canonical, 0.0) + float(score)
    return sorted(
        canonical_names.values(),
        key=lambda language: (
            -normalized_scores.get(language, 0.0),
            repository_language_priority(language)[0],
            repository_language_priority(language)[1],
            language.lower(),
        ),
    )
