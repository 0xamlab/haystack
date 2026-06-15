from __future__ import annotations

from collections import Counter
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services.repository_language_priority import (
    canonical_repository_language,
    repository_language_priority,
    sort_repository_languages,
    sort_repository_languages_by_score,
)
from benchmarks.repository_intelligence_real_repo_probe_documentation_score_support import (
    documentation_ecosystems_suppressed_in_finalize,
)


def _probe_module():
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    return probe_module


_CANDIDATE_ECOSYSTEM_PATH_CACHE_LIMIT = 8192
_CANDIDATE_ECOSYSTEM_PATH_CACHE: dict[tuple[str, str], frozenset[str]] = {}
_CANDIDATE_ECOSYSTEM_COUNT_CACHE_LIMIT = 128
_CANDIDATE_ECOSYSTEM_COUNT_CACHE: dict[tuple[str, int], Counter[str]] = {}
_PROFILE_ENTRYPOINT_BASENAMES = frozenset(
    {
        "__main__.py",
        "app.py",
        "boot.asm",
        "boot.s",
        "app.tsx",
        "index.tsx",
        "index.jsx",
        "kernel.asm",
        "kernel.s",
        "main.cr",
        "main.asm",
        "main.c",
        "main.cc",
        "main.cpp",
        "main.cxx",
        "main.go",
        "main.py",
        "main.rs",
        "main.s",
        "main.scala",
        "main.ts",
        "main.tsx",
        "main.js",
        "main.jsx",
        "main.pl",
        "main.pas",
        "main.pp",
        "main.lpr",
        "main.dpr",
        "app.r",
        "main.hs",
        "main.lhs",
        "main.ml",
        "main.m",
        "main.bas",
        "main.as",
        "main.trigger",
        "main.vbs",
        "main.wsf",
        "main.prg",
        "main.rpg",
        "main.rpgle",
        "main.sqlrpg",
        "main.sqlrpgle",
        "main.gd",
        "main.frm",
        "main.lisp",
        "main.sml",
        "main.sol",
        "main.sv",
        "main.v",
        "main.vhd",
        "main.vhdl",
        "main.prolog",
        "package.lisp",
        "packages.lisp",
        "package.lsp",
        "packages.lsp",
        "main.fs",
        "program.lpr",
        "program.dpr",
        "schema.sql",
        "init.sql",
        "tables.sql",
        "views.sql",
        "functions.sql",
        "procedures.sql",
        "server.r",
        "ui.r",
        "app.psgi",
        "main.zig",
        "program.fs",
        "manage.py",
        "main.adb",
        "main.ada",
        "app.as",
        "form1.frm",
        "page.tsx",
        "page.jsx",
        "root.zig",
        "server.ts",
        "server.js",
        "index.rst",
        "index.rest",
        "contents.rst",
        "contents.rest",
        "readme.rst",
        "readme.rest",
        "index.adoc",
        "index.asciidoc",
        "contents.adoc",
        "contents.asciidoc",
        "readme.adoc",
        "readme.asciidoc",
        "index.org",
        "contents.org",
        "readme.org",
        "start.asm",
        "start.s",
        "top.sv",
        "top.v",
        "top.vhd",
        "top.vhdl",
    }
)
_PROFILE_ROUTE_PRIORITY_SEGMENTS = frozenset(
    {
        "pages",
        "app",
        "arch",
        "asm",
        "assembly",
        "boot",
        "cmd",
        "contract",
        "contracts",
        "include",
        "interface",
        "interfaces",
        "lib",
        "libraries",
        "library",
        "lisp",
        "script",
        "scripts",
        "src",
        "source",
        "sources",
        "systems",
        "unit",
        "units",
        "db",
        "sql",
        "migration",
        "migrations",
        "prolog",
        "program",
        "programs",
        "prg",
        "qprotosrc",
        "qrpglesrc",
        "qrpgsrc",
        "rpg",
        "rpglesrc",
        "rpgsrc",
        "schema",
        "schemas",
        "models",
        "snapshots",
    }
)
_PROFILE_NOISE_SEGMENTS = frozenset(
    {"doc", "docs", "docs_src", "example", "examples", "sample", "samples"}
)
_PROFILE_NOISE_BASENAMES = frozenset({"readme.md", "changelog.md", "contributing.md"})
_PROFILE_WRAPPER_TOKENS = ("/components/ui/", "/vendor/", "/mocks/")
_BITBAKE_CONFIG_BASENAMES = repository_service.bitbake_adapter.BITBAKE_CONFIG_BASENAMES
_MOONBIT_CONFIG_BASENAMES = repository_service.moonbit_adapter.MOONBIT_CONFIG_BASENAMES
_RESCRIPT_CONFIG_BASENAMES = repository_service.rescript_adapter.RESCRIPT_CONFIG_BASENAMES
_CANDIDATE_ECOSYSTEM_STATIC_BASENAME_LANGUAGES = {
    ".smalltalk.all.ston": "smalltalk",
    ".smalltalk.release.ston": "smalltalk",
    ".smalltalk.ston": "smalltalk",
    ".hhconfig": "hack",
    "_coqproject": "coq",
    "_rocqproject": "coq",
    "ballerina.toml": "ballerina",
    "bicepconfig.json": "bicep",
    "bower.json": "purescript",
    "bsconfig.json": "rescript",
    "gleam.toml": "gleam",
    "hh_autoload.json": "hack",
    "hhvm.autoload": "hack",
    "lakefile.lean": "lean",
    "lakefile.toml": "lean",
    "lean-toolchain": "lean",
    "mason.toml": "chapel",
    "meson.build": "meson",
    "meta6.json": "raku",
    "nextflow.config": "nextflow",
    "project.janet": "janet",
    "puppetfile": "puppet",
    "qsharp.json": "qsharp",
    "rescript.json": "rescript",
    "shadow-cljs.edn": "clojurescript",
    "spago.dhall": "purescript",
    "spago.yaml": "purescript",
}
_CANDIDATE_ECOSYSTEM_STATIC_SUFFIX_LANGUAGE_HINTS = (
    ((".4dproject", ".4dcatalog", ".4dsettings"), "4d"),
    ((".agda-lib",), "agda"),
    ((".hxml",), "haxe"),
    ((".ipkg",), "idris"),
    ((".mlb", ".cm"), "sml"),
)
_CANDIDATE_ECOSYSTEM_LANGUAGE_ALIASES = {
    "4d": frozenset({"4d"}),
    "actionscript": frozenset({"actionscript"}),
    "agda": frozenset({"agda"}),
    "al": frozenset({"al"}),
    "applescript": frozenset({"applescript"}),
    "autohotkey": frozenset({"autohotkey"}),
    "autoit": frozenset({"autoit"}),
    "awk": frozenset({"awk"}),
    "ballerina": frozenset({"ballerina"}),
    "bicep": frozenset({"bicep"}),
    "blade": frozenset({"blade"}),
    "cfml": frozenset({"cfml"}),
    "chapel": frozenset({"chapel"}),
    "clojurescript": frozenset({"clojurescript"}),
    "coffeescript": frozenset({"coffeescript"}),
    "cs": frozenset({"dotnet"}),
    "delphi": frozenset({"delphi"}),
    "dhall": frozenset({"dhall"}),
    "ejs": frozenset({"ejs"}),
    "emacslisp": frozenset({"emacslisp"}),
    "erb": frozenset({"erb"}),
    "ex": frozenset({"elixir"}),
    "exs": frozenset({"elixir"}),
    "factor": frozenset({"factor"}),
    "fish": frozenset({"fish"}),
    "fsharp": frozenset({"dotnet"}),
    "foxpro": frozenset({"foxpro"}),
    "gams": frozenset({"gams"}),
    "gleam": frozenset({"gleam"}),
    "glsl": frozenset({"glsl"}),
    "groovy": frozenset({"groovy"}),
    "hack": frozenset({"hack"}),
    "haml": frozenset({"haml"}),
    "handlebars": frozenset({"handlebars"}),
    "haxe": frozenset({"haxe"}),
    "hcl": frozenset({"hcl"}),
    "idris": frozenset({"idris"}),
    "janet": frozenset({"janet"}),
    "javascript": frozenset({"node"}),
    "jinja": frozenset({"jinja"}),
    "labview": frozenset({"labview"}),
    "ladder": frozenset({"ladder"}),
    "less": frozenset({"less"}),
    "liquid": frozenset({"liquid"}),
    "logtalk": frozenset({"logtalk"}),
    "lua": frozenset({"lua"}),
    "luau": frozenset({"luau"}),
    "moonbit": frozenset({"moonbit"}),
    "mql5": frozenset({"mql5"}),
    "mustache": frozenset({"mustache"}),
    "nextflow": frozenset({"nextflow"}),
    "nimble": frozenset({"nim"}),
    "nimscript": frozenset({"nim"}),
    "nix": frozenset({"nix"}),
    "nunjucks": frozenset({"nunjucks"}),
    "nushell": frozenset({"nushell"}),
    "ocaml": frozenset({"ocaml"}),
    "opencl": frozenset({"opencl"}),
    "openscad": frozenset({"openscad"}),
    "opam": frozenset({"ocaml"}),
    "pascal": frozenset({"pascal"}),
    "puppet": frozenset({"puppet"}),
    "purescript": frozenset({"purescript"}),
    "qsharp": frozenset({"qsharp"}),
    "r": frozenset({"r"}),
    "racket": frozenset({"racket"}),
    "raku": frozenset({"raku"}),
    "rego": frozenset({"rego"}),
    "rescript": frozenset({"rescript"}),
    "rockspec": frozenset({"lua"}),
    "rpg": frozenset({"rpg"}),
    "sass": frozenset({"sass"}),
    "scheme": frozenset({"scheme"}),
    "smalltalk": frozenset({"smalltalk"}),
    "sml": frozenset({"sml"}),
    "slim": frozenset({"slim"}),
    "squirrel": frozenset({"squirrel"}),
    "starlark": frozenset({"starlark"}),
    "stylus": frozenset({"stylus"}),
    "tcl": frozenset({"tcl"}),
    "tlaplus": frozenset({"tlaplus"}),
    "tsql": frozenset({"tsql"}),
    "twig": frozenset({"twig"}),
    "typescript": frozenset({"node"}),
    "v": frozenset({"v"}),
    "vala": frozenset({"vala"}),
    "vb": frozenset({"dotnet", "visualbasic"}),
    "vba": frozenset({"vba"}),
    "verilog": frozenset({"verilog"}),
    "vimscript": frozenset({"vimscript"}),
    "vue": frozenset({"vue"}),
    "wgsl": frozenset({"wgsl"}),
    "xpp": frozenset({"xpp"}),
    "yara": frozenset({"yara"}),
}


@lru_cache(maxsize=32768)
def _normalized_path_components(
    normalized_path: str,
) -> tuple[PurePosixPath, str, str, str, tuple[str, ...]]:
    candidate_path = PurePosixPath(normalized_path)
    return (
        candidate_path,
        candidate_path.name.lower(),
        candidate_path.suffix.lower(),
        candidate_path.stem.lower(),
        tuple(part.lower() for part in candidate_path.parts),
    )


def clear_candidate_ecosystem_path_cache() -> None:
    _CANDIDATE_ECOSYSTEM_PATH_CACHE.clear()


def candidate_ecosystem_path_cache_size() -> int:
    return len(_CANDIDATE_ECOSYSTEM_PATH_CACHE)


def clear_candidate_ecosystem_count_cache() -> None:
    _CANDIDATE_ECOSYSTEM_COUNT_CACHE.clear()


def candidate_ecosystem_count_cache_size() -> int:
    return len(_CANDIDATE_ECOSYSTEM_COUNT_CACHE)


def _candidate_ecosystem_static_language_hint(
    normalized_path: str,
    *,
    basename: str,
    repo_path: Path | None,
) -> str | None:
    probe_module = _probe_module()
    _is_cfml_box_config_path = probe_module._is_cfml_box_config_path
    _is_cue_module_config_path = probe_module._is_cue_module_config_path
    _is_delphi_project_config_path = probe_module._is_delphi_project_config_path
    _is_eiffel_project_config_path = probe_module._is_eiffel_project_config_path
    _is_moonbit_config_path = probe_module._is_moonbit_config_path
    _is_odin_ols_config_path = probe_module._is_odin_ols_config_path
    _is_puppet_metadata_config_path = probe_module._is_puppet_metadata_config_path
    _is_purescript_bower_config_path = probe_module._is_purescript_bower_config_path
    _is_rescript_config_path = probe_module._is_rescript_config_path

    direct_language = _CANDIDATE_ECOSYSTEM_STATIC_BASENAME_LANGUAGES.get(basename)
    if direct_language is not None:
        return direct_language
    for suffixes, language in _CANDIDATE_ECOSYSTEM_STATIC_SUFFIX_LANGUAGE_HINTS:
        if basename.endswith(suffixes):
            return language
    if basename in _BITBAKE_CONFIG_BASENAMES:
        return "bitbake"
    if basename in {"modulefile", "puppetfile"}:
        return "puppet"
    if basename in _MOONBIT_CONFIG_BASENAMES:
        return "moonbit"
    # Gate each specialized config probe behind a cheap basename/suffix relevance check so
    # it never runs (or touches the filesystem) for an irrelevant path such as a plain
    # ``.py`` source — only the matching manifest name reaches the config validator.
    parent_basename = PurePosixPath(normalized_path).parent.name.lower()
    suffix = PurePosixPath(normalized_path).suffix.lower()
    if (
        repo_path is not None
        and basename == "module.cue"
        and parent_basename == "cue.mod"
        and _is_cue_module_config_path(repo_path, normalized_path)
    ):
        return "cue"
    if (
        repo_path is not None
        and basename == "ols.json"
        and _is_odin_ols_config_path(repo_path, normalized_path)
    ):
        return "odin"
    if (
        repo_path is not None
        and basename == "metadata.json"
        and _is_puppet_metadata_config_path(repo_path, normalized_path)
    ):
        return "puppet"
    if (
        repo_path is not None
        and suffix in {".ecf", ".ace"}
        and _is_eiffel_project_config_path(repo_path, normalized_path)
    ):
        return "eiffel"
    if (
        repo_path is not None
        and basename == "box.json"
        and _is_cfml_box_config_path(repo_path, normalized_path)
    ):
        return "cfml"
    if (
        repo_path is not None
        and basename == "bower.json"
        and _is_purescript_bower_config_path(repo_path, normalized_path)
    ):
        return "purescript"
    if (
        repo_path is not None
        and basename in _RESCRIPT_CONFIG_BASENAMES
        and _is_rescript_config_path(repo_path, normalized_path)
    ):
        return "rescript"
    if (
        repo_path is not None
        and basename in _MOONBIT_CONFIG_BASENAMES
        and _is_moonbit_config_path(repo_path, normalized_path)
    ):
        return "moonbit"
    if (
        repo_path is not None
        and basename.endswith(".dproj")
        and _is_delphi_project_config_path(repo_path, normalized_path)
    ):
        return "delphi"
    return None


def candidate_ecosystems_for_path(
    path: str,
    *,
    repo_path: Path | None = None,
    language: str | None = None,
) -> set[str]:
    probe_module = _probe_module()
    _probe_language_for_path = probe_module._probe_language_for_path

    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return set()
    cache_key = (
        str(repo_path) if repo_path is not None else "",
        normalized_path,
    )
    cached_ecosystems = _CANDIDATE_ECOSYSTEM_PATH_CACHE.get(cache_key)
    if cached_ecosystems is not None:
        return set(cached_ecosystems)
    _candidate_path, basename, suffix, _stem, _parts = _normalized_path_components(
        normalized_path
    )
    static_language_hint = _candidate_ecosystem_static_language_hint(
        normalized_path,
        basename=basename,
        repo_path=repo_path,
    )
    if static_language_hint is not None:
        language = static_language_hint
    elif language is None:
        # Resolve a cheap, stat-free direct suffix/basename hint (e.g. ``.l5x`` -> ladder)
        # before the heavier content-aware probe — a direct hint is authoritative and lets
        # the caller avoid touching the filesystem for unambiguous source suffixes.
        from benchmarks import (
            repository_intelligence_real_repo_probe_profile_path_classification_support as _classification_support,
        )

        direct_language_hint = _classification_support._structural_direct_probe_language_hint(
            basename=basename,
            suffix=suffix,
        )
        language = (
            direct_language_hint
            if direct_language_hint is not None
            else _probe_language_for_path(normalized_path, repo_path=repo_path)
        )
    ecosystems = {language}
    ecosystems.update(_CANDIDATE_ECOSYSTEM_LANGUAGE_ALIASES.get(language, ()))
    resolved_ecosystems = frozenset(ecosystem for ecosystem in ecosystems if ecosystem)
    if len(_CANDIDATE_ECOSYSTEM_PATH_CACHE) >= _CANDIDATE_ECOSYSTEM_PATH_CACHE_LIMIT:
        oldest_key = next(iter(_CANDIDATE_ECOSYSTEM_PATH_CACHE))
        _CANDIDATE_ECOSYSTEM_PATH_CACHE.pop(oldest_key, None)
    _CANDIDATE_ECOSYSTEM_PATH_CACHE[cache_key] = resolved_ecosystems
    return set(resolved_ecosystems)


def best_repository_path_priority(
    path: str,
    *,
    repo_path: Path | None = None,
) -> tuple[int, str]:
    matched_ecosystems = sort_repository_languages(
        candidate_ecosystems_for_path(path, repo_path=repo_path)
    )
    if not matched_ecosystems:
        return repository_language_priority(None)
    best_match = matched_ecosystems[0]
    return repository_language_priority(best_match)


def ordered_detected_ecosystems(
    detected_ecosystems: set[str],
) -> list[str]:
    return sort_repository_languages(detected_ecosystems)


def ordered_operational_ecosystems(
    detected_ecosystems: set[str],
    *,
    ecosystem_scores: Counter[str] | None = None,
) -> list[str]:
    if ecosystem_scores:
        return sort_repository_languages_by_score(
            detected_ecosystems,
            scores=ecosystem_scores,
        )
    return ordered_detected_ecosystems(detected_ecosystems)


def profile_signal_depth_score(path: str) -> int:
    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return 0
    _candidate_path, _basename, _suffix, _stem, parts = _normalized_path_components(
        normalized_path
    )
    depth = max(0, len(parts) - 1)
    return max(2, 16 - min(depth, 12))


def register_candidate_ecosystems(
    index: dict[str, set[str]],
    *,
    values: set[str],
    ecosystems: set[str],
) -> None:
    canonical_ecosystems = {
        canonical_repository_language(ecosystem)
        for ecosystem in ecosystems
        if canonical_repository_language(ecosystem)
    }
    if not canonical_ecosystems:
        return
    for value in values:
        normalized_value = repository_service._normalize_repository_relative_path(value)
        if not normalized_value:
            continue
        index.setdefault(normalized_value, set()).update(canonical_ecosystems)


def candidate_ecosystem_counts(
    candidate_file_paths: list[str],
    *,
    repo_path: Path,
    ecosystems: set[str],
) -> Counter[str]:
    target_ecosystems = {
        canonical_repository_language(ecosystem)
        for ecosystem in ecosystems
        if canonical_repository_language(ecosystem)
    }
    counts: Counter[str] = Counter()
    if not target_ecosystems:
        return counts
    cache_key = (str(repo_path), id(candidate_file_paths))
    cached_counts = _CANDIDATE_ECOSYSTEM_COUNT_CACHE.get(cache_key)
    if cached_counts is None:
        cached_counts = Counter()
        for candidate_path in candidate_file_paths:
            for ecosystem in candidate_ecosystems_for_path(candidate_path, repo_path=repo_path):
                canonical = canonical_repository_language(ecosystem)
                if canonical:
                    cached_counts[canonical] += 1
        if len(_CANDIDATE_ECOSYSTEM_COUNT_CACHE) >= _CANDIDATE_ECOSYSTEM_COUNT_CACHE_LIMIT:
            oldest_key = next(iter(_CANDIDATE_ECOSYSTEM_COUNT_CACHE))
            _CANDIDATE_ECOSYSTEM_COUNT_CACHE.pop(oldest_key, None)
        _CANDIDATE_ECOSYSTEM_COUNT_CACHE[cache_key] = cached_counts
    for ecosystem in target_ecosystems:
        if cached_counts[ecosystem] > 0:
            counts[ecosystem] = cached_counts[ecosystem]
    return counts


def rank_repo_profile_seed_path(
    path: str,
    *,
    repo_path: Path | None = None,
    support_roots: set[str],
) -> tuple[int, int, int, int, int, int, int, int, int, str, str]:
    probe_module = _probe_module()
    _best_matching_support_root = probe_module._best_matching_support_root
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path

    normalized_path = repository_service._normalize_repository_relative_path(path)
    path_lower = normalized_path.lower()
    _candidate_path, basename, _suffix, _stem, lowered_parts = _normalized_path_components(
        normalized_path
    )
    part_set = set(lowered_parts)
    matched_ecosystems = sort_repository_languages(
        candidate_ecosystems_for_path(
            normalized_path,
            repo_path=repo_path,
        )
    )
    language = matched_ecosystems[0] if matched_ecosystems else "unknown"
    if matched_ecosystems:
        ecosystem_name = matched_ecosystems[0]
        ecosystem_priority, ecosystem_name = repository_language_priority(ecosystem_name)
    else:
        ecosystem_priority, ecosystem_name = repository_language_priority(None)
    entrypoint_priority = 0 if basename in _PROFILE_ENTRYPOINT_BASENAMES else 1
    shell_root_priority = 0 if language == "shell" and len(lowered_parts) == 1 else 1
    support_priority = (
        0
        if _best_matching_support_root(
            normalized_path,
            support_roots=support_roots,
        )
        is not None
        else 1
    )
    route_priority = (
        0
        if any(segment in _PROFILE_ROUTE_PRIORITY_SEGMENTS for segment in lowered_parts)
        else 1
    )
    code_priority = (
        1
        if language in repository_service._NON_CODE_GRAPH_LANGUAGES
        or language in repository_service._ENTRYPOINT_DEMOTED_LANGUAGES
        else 0
    )
    platform_noise_penalty = (
        1
        if (
            normalized_path.startswith(".github/")
            or normalized_path.startswith("docs/")
            or part_set & _PROFILE_NOISE_SEGMENTS
            or basename in _PROFILE_NOISE_BASENAMES
        )
        else 0
    )
    non_operational_penalty = 1 if _is_non_operational_profile_path(normalized_path) else 0
    wrapper_penalty = 1 if any(token in path_lower for token in _PROFILE_WRAPPER_TOKENS) else 0
    declaration_penalty = 1 if basename.endswith(".d.ts") or "/types/" in path_lower else 0
    return (
        1 if repository_service._is_test_path(normalized_path) else 0,
        code_priority,
        platform_noise_penalty + non_operational_penalty,
        ecosystem_priority,
        entrypoint_priority,
        shell_root_priority,
        support_priority,
        route_priority,
        wrapper_penalty + declaration_penalty,
        ecosystem_name,
        normalized_path,
    )


def finalize_seed_plan(state: Any) -> dict[str, Any]:
    probe_module = _probe_module()
    _candidate_existing_leaf_roots = probe_module._candidate_existing_leaf_roots
    _candidate_existing_paths = probe_module._candidate_existing_paths
    _cuda_profile_hints_from_candidates = probe_module._cuda_profile_hints_from_candidates
    _expand_profile_entrypoints = probe_module._expand_profile_entrypoints
    _is_non_operational_profile_path_for_ecosystems = (
        probe_module._is_non_operational_profile_path_for_ecosystems
    )
    _is_operational_profile_entrypoint_candidate = (
        probe_module._is_operational_profile_entrypoint_candidate
    )
    _is_repo_profile_code_candidate = probe_module._is_repo_profile_code_candidate
    _path_within_support_roots = probe_module._path_within_support_roots
    _probe_language_for_path = probe_module._probe_language_for_path

    repo_path = state.repo_path
    focus_paths = state.focus_paths
    entrypoint_candidates = state.entrypoint_candidates
    support_root_candidates = state.support_root_candidates
    config_path_candidates = state.config_path_candidates
    detected_ecosystems = state.detected_ecosystems
    detected_ecosystem_scores = state.detected_ecosystem_scores
    entrypoint_candidate_ecosystems = state.entrypoint_candidate_ecosystems
    support_root_candidate_ecosystems = state.support_root_candidate_ecosystems
    bitbake_candidate_file_paths = state.bitbake_candidate_file_paths
    candidate_file_paths = state.candidate_file_paths

    existing_entrypoints = _candidate_existing_paths(
        repo_path,
        paths=entrypoint_candidates,
    )
    existing_support_roots = _candidate_existing_leaf_roots(
        repo_path,
        roots=support_root_candidates,
        entrypoint_paths=set(existing_entrypoints),
    )
    existing_config_paths = _candidate_existing_paths(
        repo_path,
        paths=config_path_candidates,
    )

    def _is_entrypoint_or_code_candidate(path: str) -> bool:
        return _is_repo_profile_code_candidate(
            path,
            repo_path=repo_path,
        ) or _is_operational_profile_entrypoint_candidate(
            path,
            repo_path=repo_path,
        )

    def _is_non_operational_seed_path(path: str) -> bool:
        matched_ecosystems = candidate_ecosystems_for_path(
            path,
            repo_path=repo_path,
        ) or detected_ecosystems
        return _is_non_operational_profile_path_for_ecosystems(
            path,
            ecosystems=matched_ecosystems,
            repo_path=repo_path,
        )

    operational_ecosystem_order = ordered_operational_ecosystems(
        detected_ecosystems,
        ecosystem_scores=detected_ecosystem_scores,
    )
    bitbake_is_primary_operational_ecosystem = (
        bool(operational_ecosystem_order) and operational_ecosystem_order[0] == "bitbake"
    )
    logtalk_is_primary_operational_ecosystem = (
        bool(operational_ecosystem_order) and operational_ecosystem_order[0] == "logtalk"
    )
    if (
        bitbake_is_primary_operational_ecosystem
        and "bitbake" in detected_ecosystems
        and bitbake_candidate_file_paths
    ):
        bitbake_candidate_file_path_set = set(bitbake_candidate_file_paths)
        existing_entrypoints = [
            path
            for path in existing_entrypoints
            if path in bitbake_candidate_file_path_set
            and PurePosixPath(path).suffix.lower() == ".bb"
        ]
        existing_support_roots = [
            root
            for root in existing_support_roots
            if any(path == root or path.startswith(f"{root}/") for path in candidate_file_paths)
        ]
        existing_config_paths = [
            path
            for path in existing_config_paths
            if PurePosixPath(path).name.lower()
            in repository_service.bitbake_adapter.BITBAKE_CONFIG_BASENAMES
        ]
        candidate_file_paths = [
            path for path in candidate_file_paths if path in bitbake_candidate_file_path_set
        ]
    if logtalk_is_primary_operational_ecosystem and "logtalk" in detected_ecosystems:
        logtalk_candidate_file_paths = [
            path
            for path in candidate_file_paths
            if candidate_ecosystems_for_path(path, repo_path=repo_path) & {"logtalk", "prolog"}
        ]
        if logtalk_candidate_file_paths:
            logtalk_candidate_file_path_set = set(logtalk_candidate_file_paths)
            existing_entrypoints = [
                path
                for path in existing_entrypoints
                if path in logtalk_candidate_file_path_set
            ]
            existing_support_roots = [
                root
                for root in existing_support_roots
                if any(
                    path == root or path.startswith(f"{root}/")
                    for path in logtalk_candidate_file_paths
                )
            ]
            candidate_file_paths = logtalk_candidate_file_paths
    # A Robot Framework suite is the operational root of its repo: documentation surfaces
    # (README.rst / BUILD.rst) are not competing code. When ``.robot`` files dominate the real
    # (non-documentation) host code, lift robotframework to at least the leading documentation
    # score so the documentation suppression below then demotes those doc ecosystems.
    if "robotframework" in detected_ecosystems:
        robot_count = candidate_ecosystem_counts(
            candidate_file_paths,
            repo_path=repo_path,
            ecosystems={"robotframework"},
        )["robotframework"]
        if robot_count > 0:
            documentation_ecosystems = {
                canonical_repository_language(ecosystem)
                for ecosystem in probe_module._DOCUMENTATION_PRIMARY_ECOSYSTEMS
                if canonical_repository_language(ecosystem)
            }
            non_robot_host_count = sum(
                count
                for ecosystem, count in candidate_ecosystem_counts(
                    candidate_file_paths,
                    repo_path=repo_path,
                    ecosystems={"python", "html", "javascript", "typescript"},
                ).items()
            )
            if robot_count >= max(2, non_robot_host_count):
                detected_documentation_score = max(
                    (
                        score
                        for ecosystem, score in detected_ecosystem_scores.items()
                        if ecosystem in documentation_ecosystems
                    ),
                    default=0,
                )
                detected_ecosystem_scores["robotframework"] = max(
                    detected_ecosystem_scores["robotframework"],
                    detected_documentation_score + 16,
                )
    # An ASP.NET Web Forms app is the operational root: its ``.aspx``/``.ascx``/``.master``
    # markup is the surface, while the ``.aspx.vb``/``.cs`` code-behind (and their generic
    # ``dotnet``/``visualbasic`` aliases) are hosts. When the markup surface dominates, lift
    # asp.net above those code-behind host ecosystems so it wins operational rank.
    if any(_eco == "asp.net" for _eco in detected_ecosystems):
        aspnet_count = candidate_ecosystem_counts(
            candidate_file_paths,
            repo_path=repo_path,
            ecosystems={"asp.net"},
        )["asp.net"]
        if aspnet_count >= 3:
            code_behind_host_max = max(
                (
                    detected_ecosystem_scores[ecosystem]
                    for ecosystem in ("dotnet", "visualbasic", "cs", "csharp")
                    if ecosystem in detected_ecosystem_scores
                ),
                default=0,
            )
            detected_ecosystem_scores["asp.net"] = max(
                detected_ecosystem_scores["asp.net"],
                code_behind_host_max + 16,
            )
    suppressed_documentation_ecosystems = documentation_ecosystems_suppressed_in_finalize(
        detected_ecosystems,
        ecosystem_scores=detected_ecosystem_scores,
    )
    for entrypoint_path in existing_entrypoints:
        for ecosystem in entrypoint_candidate_ecosystems.get(entrypoint_path, set()):
            if ecosystem in suppressed_documentation_ecosystems:
                continue
            detected_ecosystem_scores[ecosystem] += 18
    for support_root in existing_support_roots:
        for ecosystem in support_root_candidate_ecosystems.get(support_root, set()):
            if ecosystem in suppressed_documentation_ecosystems:
                continue
            detected_ecosystem_scores[ecosystem] += 12
    candidate_file_paths = list(
        dict.fromkeys(existing_entrypoints + candidate_file_paths)
    )
    for candidate_path in candidate_file_paths:
        if repository_service._is_test_path(candidate_path) and PurePosixPath(
            candidate_path
        ).suffix.lower() not in {".wat", ".wast"}:
            continue
        if _is_non_operational_seed_path(candidate_path):
            continue
        if not _is_entrypoint_or_code_candidate(candidate_path):
            continue
        matched_ecosystems = candidate_ecosystems_for_path(
            candidate_path,
            repo_path=repo_path,
        )
        if not matched_ecosystems:
            continue
        detected_ecosystems.update(
            ecosystem
            for ecosystem in matched_ecosystems
            if ecosystem not in {"unknown", "txt"}
        )
        weight = 3 if candidate_path in existing_entrypoints else 1
        for ecosystem in matched_ecosystems:
            if ecosystem in suppressed_documentation_ecosystems:
                continue
            detected_ecosystem_scores[ecosystem] += weight
    cuda_count = candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"cuda"},
    )["cuda"]
    if cuda_count >= 24:
        cuda_entrypoints, _, cuda_configs = _cuda_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        cuda_entrypoint_root_count = len(
            {
                normalized_root
                for path in cuda_entrypoints
                if (
                    normalized_root := repository_service._normalize_repository_relative_path(
                        str(PurePosixPath(path).parent)
                    )
                )
            }
        )
        if len(cuda_configs) >= 8 and cuda_entrypoint_root_count >= 8:
            non_cuda_max_score = max(
                (
                    score
                    for ecosystem, score in detected_ecosystem_scores.items()
                    if ecosystem != "cuda"
                ),
                default=0,
            )
            detected_ecosystem_scores["cuda"] = max(
                detected_ecosystem_scores["cuda"],
                non_cuda_max_score + 32,
            )

    ranked_candidates = sorted(
        candidate_file_paths,
        key=lambda path: rank_repo_profile_seed_path(
            path,
            repo_path=repo_path,
            support_roots=set(existing_support_roots),
        ),
    )
    code_candidates = [
        path
        for path in ranked_candidates
        if _is_entrypoint_or_code_candidate(path)
    ]
    ecosystem_matched_candidates = [
        path
        for path in code_candidates
        if not detected_ecosystems
        or candidate_ecosystems_for_path(path, repo_path=repo_path) & detected_ecosystems
    ]
    candidate_pool = ecosystem_matched_candidates or code_candidates
    filtered_existing_entrypoints = [
        path
        for path in existing_entrypoints
        if (
            (
                not repository_service._is_test_path(path)
                and not _is_non_operational_seed_path(path)
            )
            or (
                "robotframework" in detected_ecosystems
                and _probe_language_for_path(path, repo_path=repo_path) == "robotframework"
            )
        )
        and _is_entrypoint_or_code_candidate(path)
    ]
    if filtered_existing_entrypoints or code_candidates:
        existing_entrypoints = filtered_existing_entrypoints
    support_root_filtered_candidates = [
        path
        for path in candidate_pool
        if existing_support_roots
        and _path_within_support_roots(path, support_roots=set(existing_support_roots))
        and not repository_service._is_test_path(path)
        and not _is_non_operational_seed_path(path)
    ]
    fallback_candidates = support_root_filtered_candidates or [
        path
        for path in candidate_pool
        if not repository_service._is_test_path(path)
        and not _is_non_operational_seed_path(path)
    ]
    if not fallback_candidates:
        fallback_candidates = [
            path for path in candidate_pool if not repository_service._is_test_path(path)
        ] or candidate_pool or code_candidates or ranked_candidates
    fallback_limit = 0
    if not existing_entrypoints:
        fallback_limit = min(12, max(4, len(ranked_candidates) // 8 or 1))
    elif len(existing_entrypoints) < 3:
        fallback_limit = 3 - len(existing_entrypoints)
    entrypoint_files = list(
        dict.fromkeys(existing_entrypoints + fallback_candidates[:fallback_limit])
    )
    entrypoint_files = _expand_profile_entrypoints(
        ranked_candidates=ranked_candidates,
        repo_path=repo_path,
        support_roots=existing_support_roots,
        existing_entrypoints=entrypoint_files,
        detected_ecosystems=detected_ecosystems,
        ecosystem_scores=detected_ecosystem_scores,
    )
    if (
        bitbake_is_primary_operational_ecosystem
        and "bitbake" in detected_ecosystems
        and bitbake_candidate_file_paths
    ):
        bitbake_recipe_entrypoints = [
            path for path in entrypoint_files if PurePosixPath(path).suffix.lower() == ".bb"
        ]
        if bitbake_recipe_entrypoints:
            entrypoint_files = bitbake_recipe_entrypoints
    if not existing_support_roots:
        existing_support_roots = [
            repository_service._normalize_repository_relative_path(path)
            for path in focus_paths
            if str(path).strip()
        ]
    for entrypoint_file in entrypoint_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(entrypoint_file).parent)
        )
        if parent_dir:
            existing_support_roots.append(parent_dir)
    return {
        "candidate_file_paths": candidate_file_paths,
        "entrypoint_files": [path for path in entrypoint_files if path],
        "support_roots": list(dict.fromkeys(path for path in existing_support_roots if path)),
        "config_paths": existing_config_paths,
        "detected_ecosystems": ordered_detected_ecosystems(
            detected_ecosystems,
        ),
        "operational_ecosystems": ordered_operational_ecosystems(
            detected_ecosystems,
            ecosystem_scores=detected_ecosystem_scores,
        ),
    }
