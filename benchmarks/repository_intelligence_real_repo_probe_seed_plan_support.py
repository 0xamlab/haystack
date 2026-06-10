from __future__ import annotations

from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services.repository_language_priority import (
    canonical_repository_language,
    repository_language_priority,
    sort_repository_languages,
    sort_repository_languages_by_score,
)


def _probe_module():
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    return probe_module


def candidate_ecosystems_for_path(
    path: str,
    *,
    repo_path: Path | None = None,
) -> set[str]:
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
    _probe_language_for_path = probe_module._probe_language_for_path

    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return set()
    basename = PurePosixPath(normalized_path).name.lower()
    if basename in {
        ".smalltalk.ston",
        ".smalltalk.all.ston",
        ".smalltalk.release.ston",
    }:
        language = "smalltalk"
    elif basename == "gleam.toml":
        language = "gleam"
    elif basename == "qsharp.json":
        language = "qsharp"
    elif basename == "shadow-cljs.edn":
        language = "clojurescript"
    elif basename in {".hhconfig", "hhvm.autoload", "hh_autoload.json"}:
        language = "hack"
    elif basename == "project.janet":
        language = "janet"
    elif basename == "nextflow.config":
        language = "nextflow"
    elif basename == "mason.toml":
        language = "chapel"
    elif basename in repository_service.bitbake_adapter.BITBAKE_CONFIG_BASENAMES:
        language = "bitbake"
    elif basename == "bicepconfig.json":
        language = "bicep"
    elif repo_path is not None and _is_cue_module_config_path(repo_path, normalized_path):
        language = "cue"
    elif repo_path is not None and _is_odin_ols_config_path(repo_path, normalized_path):
        language = "odin"
    elif basename in {"puppetfile", "modulefile"}:
        language = "puppet"
    elif repo_path is not None and _is_puppet_metadata_config_path(repo_path, normalized_path):
        language = "puppet"
    elif repo_path is not None and _is_eiffel_project_config_path(repo_path, normalized_path):
        language = "eiffel"
    elif basename in {"lean-toolchain", "lakefile.lean", "lakefile.toml"}:
        language = "lean"
    elif basename in {"_coqproject", "_rocqproject"}:
        language = "coq"
    elif basename.endswith(".agda-lib"):
        language = "agda"
    elif basename.endswith(".ipkg"):
        language = "idris"
    elif basename == "meta6.json":
        language = "raku"
    elif basename in {"spago.yaml", "spago.dhall"}:
        language = "purescript"
    elif basename in {"rescript.json", "bsconfig.json"}:
        language = "rescript"
    elif basename in repository_service.moonbit_adapter.MOONBIT_CONFIG_BASENAMES:
        language = "moonbit"
    elif basename.endswith(".hxml"):
        language = "haxe"
    elif repo_path is not None and _is_cfml_box_config_path(repo_path, normalized_path):
        language = "cfml"
    elif repo_path is not None and _is_purescript_bower_config_path(repo_path, normalized_path):
        language = "purescript"
    elif repo_path is not None and _is_rescript_config_path(repo_path, normalized_path):
        language = "rescript"
    elif repo_path is not None and _is_moonbit_config_path(repo_path, normalized_path):
        language = "moonbit"
    elif repo_path is not None and _is_delphi_project_config_path(repo_path, normalized_path):
        language = "delphi"
    else:
        language = _probe_language_for_path(normalized_path, repo_path=repo_path)
    ecosystems = {language}
    ecosystem_aliases = {
        "cs": {"dotnet"},
        "ex": {"elixir"},
        "exs": {"elixir"},
        "fsharp": {"dotnet"},
        "foxpro": {"foxpro"},
        "javascript": {"node"},
        "ladder": {"ladder"},
        "labview": {"labview"},
        "lua": {"lua"},
        "luau": {"luau"},
        "ocaml": {"ocaml"},
        "actionscript": {"actionscript"},
        "applescript": {"applescript"},
        "autohotkey": {"autohotkey"},
        "autoit": {"autoit"},
        "squirrel": {"squirrel"},
        "awk": {"awk"},
        "coffeescript": {"coffeescript"},
        "delphi": {"delphi"},
        "emacslisp": {"emacslisp"},
        "fish": {"fish"},
        "gams": {"gams"},
        "gleam": {"gleam"},
        "glsl": {"glsl"},
        "groovy": {"groovy"},
        "wgsl": {"wgsl"},
        "less": {"less"},
        "opencl": {"opencl"},
        "qsharp": {"qsharp"},
        "sass": {"sass"},
        "clojurescript": {"clojurescript"},
        "al": {"al"},
        "sml": {"sml"},
        "stylus": {"stylus"},
        "jinja": {"jinja"},
        "liquid": {"liquid"},
        "handlebars": {"handlebars"},
        "mustache": {"mustache"},
        "nunjucks": {"nunjucks"},
        "twig": {"twig"},
        "haml": {"haml"},
        "slim": {"slim"},
        "erb": {"erb"},
        "ejs": {"ejs"},
        "blade": {"blade"},
        "vue": {"vue"},
        "hack": {"hack"},
        "hcl": {"hcl"},
        "puppet": {"puppet"},
        "bicep": {"bicep"},
        "dhall": {"dhall"},
        "tlaplus": {"tlaplus"},
        "logtalk": {"logtalk"},
        "janet": {"janet"},
        "nextflow": {"nextflow"},
        "moonbit": {"moonbit"},
        "chapel": {"chapel"},
        "rego": {"rego"},
        "yara": {"yara"},
        "agda": {"agda"},
        "idris": {"idris"},
        "raku": {"raku"},
        "haxe": {"haxe"},
        "openscad": {"openscad"},
        "factor": {"factor"},
        "purescript": {"purescript"},
        "rescript": {"rescript"},
        "nix": {"nix"},
        "mql5": {"mql5"},
        "nushell": {"nushell"},
        "vimscript": {"vimscript"},
        "v": {"v"},
        "verilog": {"verilog"},
        "pascal": {"pascal"},
        "smalltalk": {"smalltalk"},
        "vala": {"vala"},
        "opam": {"ocaml"},
        "r": {"r"},
        "rpg": {"rpg"},
        "racket": {"racket"},
        "scheme": {"scheme"},
        "rockspec": {"lua"},
        "starlark": {"starlark"},
        "tcl": {"tcl"},
        "tsql": {"tsql"},
        "nimble": {"nim"},
        "nimscript": {"nim"},
        "typescript": {"node"},
        "vb": {"dotnet", "visualbasic"},
        "vba": {"vba"},
        "xpp": {"xpp"},
    }
    ecosystems.update(ecosystem_aliases.get(language, set()))
    return {ecosystem for ecosystem in ecosystems if ecosystem}


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
    depth = max(0, len(PurePosixPath(normalized_path).parts) - 1)
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
    for candidate_path in candidate_file_paths:
        for ecosystem in candidate_ecosystems_for_path(candidate_path, repo_path=repo_path):
            canonical = canonical_repository_language(ecosystem)
            if canonical in target_ecosystems:
                counts[canonical] += 1
    return counts


def rank_repo_profile_seed_path(
    path: str,
    *,
    repo_path: Path | None = None,
    support_roots: set[str],
) -> tuple[int, int, int, int, int, int, int, int, int, str, str]:
    probe_module = _probe_module()
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
    _probe_language_for_path = probe_module._probe_language_for_path

    normalized_path = repository_service._normalize_repository_relative_path(path)
    path_lower = normalized_path.lower()
    basename = PurePosixPath(normalized_path).name.lower()
    parts = PurePosixPath(normalized_path).parts
    part_set = {part.lower() for part in parts}
    language = _probe_language_for_path(normalized_path, repo_path=repo_path)
    ecosystem_priority, ecosystem_name = best_repository_path_priority(
        normalized_path,
        repo_path=repo_path,
    )
    entrypoint_basenames = {
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
    entrypoint_priority = 0 if basename in entrypoint_basenames else 1
    shell_root_priority = 0 if language == "shell" and len(parts) == 1 else 1
    support_priority = 1
    for root in support_roots:
        normalized_root = repository_service._normalize_repository_relative_path(root)
        if not normalized_root:
            continue
        if normalized_path == normalized_root or normalized_path.startswith(f"{normalized_root}/"):
            support_priority = 0
            break
    route_priority = (
        0
        if any(
            segment.lower()
            in {
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
            for segment in parts
        )
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
            or part_set & {"doc", "docs", "docs_src", "example", "examples", "sample", "samples"}
            or basename in {"readme.md", "changelog.md", "contributing.md"}
        )
        else 0
    )
    non_operational_penalty = 1 if _is_non_operational_profile_path(normalized_path) else 0
    wrapper_penalty = 1 if any(
        token in path_lower for token in ("/components/ui/", "/vendor/", "/mocks/")
    ) else 0
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
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
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
    if "bitbake" in detected_ecosystems and bitbake_candidate_file_paths:
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
    for entrypoint_path in existing_entrypoints:
        for ecosystem in entrypoint_candidate_ecosystems.get(entrypoint_path, set()):
            detected_ecosystem_scores[ecosystem] += 18
    for support_root in existing_support_roots:
        for ecosystem in support_root_candidate_ecosystems.get(support_root, set()):
            detected_ecosystem_scores[ecosystem] += 12
    candidate_file_paths = list(
        dict.fromkeys(existing_entrypoints + candidate_file_paths)
    )
    for candidate_path in candidate_file_paths:
        if repository_service._is_test_path(candidate_path):
            continue
        if _is_non_operational_profile_path(candidate_path):
            continue
        if not _is_repo_profile_code_candidate(candidate_path, repo_path=repo_path):
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
        if _is_repo_profile_code_candidate(path, repo_path=repo_path)
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
                and not _is_non_operational_profile_path(path)
            )
            or (
                "robotframework" in detected_ecosystems
                and _probe_language_for_path(path, repo_path=repo_path) == "robotframework"
            )
        )
        and _is_repo_profile_code_candidate(path, repo_path=repo_path)
    ]
    if filtered_existing_entrypoints or code_candidates:
        existing_entrypoints = filtered_existing_entrypoints
    support_root_filtered_candidates = [
        path
        for path in candidate_pool
        if existing_support_roots
        and _path_within_support_roots(path, support_roots=set(existing_support_roots))
        and not repository_service._is_test_path(path)
        and not _is_non_operational_profile_path(path)
    ]
    fallback_candidates = support_root_filtered_candidates or [
        path
        for path in candidate_pool
        if not repository_service._is_test_path(path)
        and not _is_non_operational_profile_path(path)
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
