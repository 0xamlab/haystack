from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_indexing import (
    _candidate_repository_roots,
    _language_for_path,
    _matches_repository_pattern,
    _matches_repository_scope,
    _normalize_repository_relative_path,
)
from apps.api_server.services.repository_intelligence_inventory import (
    _DEFAULT_EXCLUDED_PATH_PARTS,
)
from apps.api_server.services.repository_intelligence_repository_source import (
    _git_repository_relative_files,
)

TEXT_FILE_SUFFIXES = {
    ".abap",
    ".ada",
    ".adb",
    ".agda",
    ".agda-lib",
    ".ace",
    ".a51",
    ".ads",
    ".ahk",
    ".au3",
    ".nut",
    ".apex",
    ".asm",
    ".as",
    ".applescript",
    ".asd",
    ".auk",
    ".awk",
    ".bash",
    ".bashrc",
    ".bas",
    ".bat",
    ".bb",
    ".bbappend",
    ".bbclass",
    ".bzl",
    ".cabal",
    ".c",
    ".cbl",
    ".cc",
    ".cu",
    ".cuh",
    ".cfc",
    ".cfm",
    ".cfml",
    ".cmake",
    ".chpl",
    ".clj",
    ".cljc",
    ".cljs",
    ".cob",
    ".cobol",
    ".coffee",
    ".cpp",
    ".cpy",
    ".cr",
    ".cls",
    ".cmd",
    ".cxx",
    ".css",
    ".cs",
    ".csproj",
    ".dtx",
    ".dockerfile",
    ".pxd",
    ".pxi",
    ".pyx",
    ".stan",
    ".cue",
    ".ctl",
    ".d",
    ".dfm",
    ".dbproj",
    ".dhall",
    ".dm",
    ".dme",
    ".dot",
    ".mmd",
    ".puml",
    ".qasm",
    ".dpk",
    ".dpr",
    ".dproj",
    ".e",
    ".ecf",
    ".fsproj",
    ".dart",
    ".di",
    ".edn",
    ".el",
    ".elm",
    ".erl",
    ".f",
    ".factor",
    ".fnl",
    ".fnlm",
    ".fish",
    ".f03",
    ".f08",
    ".f90",
    ".f95",
    ".for",
    ".hrl",
    ".ex",
    ".exs",
    ".fmx",
    ".fs",
    ".fsi",
    ".fsx",
    ".frm",
    ".gawk",
    ".gleam",
    ".gms",
    ".go",
    ".gv",
    ".mermaid",
    ".nf",
    ".plantuml",
    ".iuml",
    ".gradle",
    ".groovy",
    ".gpr",
    ".glsl",
    ".hlsl",
    ".hlsli",
    ".wgsl",
    ".fx",
    ".fxh",
    ".g4",
    ".cginc",
    ".vert",
    ".frag",
    ".geom",
    ".tesc",
    ".tese",
    ".comp",
    ".compute",
    ".shader",
    ".hcl",
    ".hack",
    ".bicep",
    ".tla",
    ".h",
    ".hx",
    ".hxml",
    ".hh",
    ".hhi",
    ".hsc",
    ".hpp",
    ".hs",
    ".hy",
    ".wren",
    ".hxx",
    ".idr",
    ".inc",
    ".ipkg",
    ".html",
    ".ipp",
    ".java",
    ".js",
    ".jl",
    ".janet",
    ".j2",
    ".jinja",
    ".jinja2",
    ".liquid",
    ".hbs",
    ".handlebars",
    ".mustache",
    ".njk",
    ".nunj",
    ".nunjucks",
    ".twig",
    ".haml",
    ".slim",
    ".tpl",
    ".erb",
    ".rhtml",
    ".jade",
    ".pug",
    ".ejs",
    ".vue",
    ".svelte",
    ".astro",
    ".json",
    ".jsx",
    ".just",
    ".ksh",
    ".kt",
    ".kts",
    ".l5x",
    ".lagda",
    ".lidr",
    ".lhs",
    ".lgt",
    ".lean",
    ".logtalk",
    ".litcoffee",
    ".lisp",
    ".lsp",
    ".lvclass",
    ".lvlib",
    ".lvproj",
    ".lua",
    ".luau",
    ".mawk",
    ".m",
    ".mk",
    ".mm",
    ".md",
    ".mq5",
    ".mqh",
    ".mqproj",
    ".mlb",
    ".mj",
    ".mojo",
    ".move",
    ".mo",
    ".roc",
    ".res",
    ".resi",
    ".ml",
    ".mli",
    ".cm",
    ".nim",
    ".nimble",
    ".nims",
    ".nix",
    ".nu",
    ".nawk",
    ".opam",
    ".odin",
    ".scad",
    ".pas",
    ".purs",
    ".php",
    ".podspec",
    ".pl",
    ".pkb",
    ".pks",
    ".pm",
    ".pm6",
    ".p6",
    ".pp",
    ".prolog",
    ".prg",
    ".prc",
    ".pls",
    ".ps1",
    ".psd1",
    ".psgi",
    ".psm1",
    ".pro",
    ".py",
    ".pri",
    ".prf",
    ".proto",
    ".qml",
    ".r",
    ".rego",
    ".rb",
    ".yar",
    ".yara",
    ".raku",
    ".rakumod",
    ".rakutest",
    ".rst",
    ".rest",
    ".org",
    ".adoc",
    ".asciidoc",
    ".asc",
    ".rkt",
    ".rktl",
    ".scm",
    ".sld",
    ".rpg",
    ".rpginc",
    ".rockspec",
    ".resource",
    ".robot",
    ".feature",
    ".scss",
    ".less",
    ".mbt",
    ".mbti",
    ".styl",
    ".sty",
    ".rpgle",
    ".rpgleinc",
    ".gemspec",
    ".rs",
    ".sas",
    ".sig",
    ".sb3",
    ".scpt",
    ".sbt",
    ".sln",
    ".sml",
    ".sol",
    ".ston",
    ".sqlrpg",
    ".sqlrpgle",
    ".scala",
    ".s",
    ".sps",
    ".sh",
    ".ss",
    ".st",
    ".sql",
    ".star",
    ".sqlproj",
    ".swift",
    ".sv",
    ".svh",
    ".tcl",
    ".tf",
    ".tfvars",
    ".tm",
    ".trigger",
    ".trg",
    ".tpp",
    ".tex",
    ".typ",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".fun",
    ".vala",
    ".vapi",
    ".gml",
    ".gd",
    ".vb",
    ".v",
    ".vbe",
    ".vbproj",
    ".vbp",
    ".vbs",
    ".vhd",
    ".vhdl",
    ".vh",
    ".vi",
    ".vim",
    ".vit",
    ".wl",
    ".wls",
    ".xpo",
    ".xpp",
    ".lpi",
    ".lpk",
    ".lpr",
    ".ltx",
    ".wsf",
    ".yaml",
    ".yml",
    ".zsh",
    ".zsh-theme",
    ".zig",
}

TEXT_FILE_BASENAMES = frozenset(
    {
        ".bash_profile",
        ".bashrc",
        ".envrc",
        ".latexmkrc",
        ".profile",
        ".zlogin",
        ".zlogout",
        ".zprofile",
        ".zshenv",
        ".zshrc",
        "latexmkrc",
        "dockerfile",
        "containerfile",
        "Dockerfile",
        "Containerfile",
        "Makefile",
        "makefile",
        "GNUmakefile",
        "justfile",
        "Justfile",
        ".justfile",
        "Procfile",
        "Jenkinsfile",
        "Gemfile",
        "BUILD",
        "BUILD.bazel",
        "Project.toml",
        "Manifest.toml",
        "MODULE.bazel",
        "Move.toml",
        "moon.mod",
        "moon.pkg",
        "rescript.json",
        "bsconfig.json",
        "shard.yml",
        "Rakefile",
        "Brewfile",
        "box.json",
        "DESCRIPTION",
        "NAMESPACE",
        "cpanfile",
        "dist.ini",
        "pom.xml",
        "WORKSPACE",
        "WORKSPACE.bazel",
        "Makefile.PL",
        "Build.PL",
        "CMakeLists.txt",
        "Cask",
        "build.sbt",
        "build.sc",
        "build.mill",
        "Cakefile",
        "cakefile",
        "build.bat",
        "build.cmd",
        "dune",
        "dune-project",
        ".hhconfig",
        "config.nims",
        "hhvm.autoload",
        "hh_autoload.json",
        "nim.cfg",
        "vimrc",
        ".vimrc",
        "_vimrc",
        "_CoqProject",
        "_RocqProject",
        "lean-toolchain",
        "gvimrc",
        "build.gradle",
        "build.gradle.kts",
        "settings.gradle",
        "settings.gradle.kts",
        "mix.exs",
        "erlang.mk",
        "rebar.config",
        "composer.json",
        "deps.edn",
        "bb.edn",
        "layer.conf",
        "bblayers.conf",
        "local.conf",
        "nextflow.config",
        "package.yaml",
        "Package.swift",
        "Puppetfile",
        "project.clj",
        "qmldir",
        "qmake.conf",
        "shadow-cljs.edn",
        "stack.yaml",
        "buf.gen.yaml",
        "buf.work.yaml",
        "buf.yaml",
        "typst.toml",
        "dbt_project.yml",
        "dbt_project.yaml",
        "build.zig",
        "bash_completion",
        "cabal.project",
        "meson.build",
        "Modulefile",
        "project.godot",
        "asconfig.json",
        "v.mod",
    }
)


def _path_is_indexable_repository_file(path: Path) -> bool:
    if path.suffix.lower() in TEXT_FILE_SUFFIXES:
        return True
    if path.name in TEXT_FILE_BASENAMES:
        return True
    if path.suffix.lower() == ".xml":
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        return _language_for_path(path, text=text) == "xpp"
    if path.suffix:
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return _language_for_path(path, text=text) == "awk"


def _detected_repository_file_language(path: Path, *, repo_root: Path | None = None) -> str:
    if path.suffix.lower() not in {
        ".bas",
        ".cls",
        ".ctl",
        ".dfm",
        ".dpk",
        ".dpr",
        ".dproj",
        ".fmx",
        ".frm",
        ".h",
        ".inc",
        ".m",
        ".mm",
        ".pas",
        ".pch",
        ".pl",
        ".sql",
        ".dbproj",
        ".sqlproj",
        ".prg",
        ".v",
        ".vhd",
        ".vhdl",
        ".vh",
        ".vbp",
        ".xml",
        ".just",
        "",
    }:
        return _language_for_path(path, repo_root=repo_root)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = None
    return _language_for_path(path, text=text, repo_root=repo_root)


def _append_repository_file(
    *,
    root_path: Path,
    path: Path,
    files: list[Path],
    seen_paths: set[str],
    normalized_include_patterns: list[str] | tuple[str, ...],
    normalized_exclude_patterns: list[str] | tuple[str, ...],
    max_files: int,
    max_total_bytes: int | None,
    total_bytes: int,
) -> dict[str, int | bool]:
    if not path.is_file() or path.is_symlink():
        return {"total_bytes": total_bytes, "stop": False}
    if not _path_is_indexable_repository_file(path):
        return {"total_bytes": total_bytes, "stop": False}
    relative_path = _normalize_repository_relative_path(str(path.relative_to(root_path)))
    if not relative_path or relative_path in seen_paths:
        return {"total_bytes": total_bytes, "stop": False}
    parts = set(PurePosixPath(relative_path).parts)
    if parts & _DEFAULT_EXCLUDED_PATH_PARTS:
        return {"total_bytes": total_bytes, "stop": False}
    if normalized_include_patterns and not any(
        _matches_repository_pattern(relative_path, pattern)
        for pattern in normalized_include_patterns
    ):
        return {"total_bytes": total_bytes, "stop": False}
    if any(
        _matches_repository_pattern(relative_path, pattern)
        for pattern in normalized_exclude_patterns
    ):
        return {"total_bytes": total_bytes, "stop": False}
    try:
        file_size = path.stat().st_size
    except OSError:
        return {"total_bytes": total_bytes, "stop": False}
    if max_total_bytes is not None and files and total_bytes + file_size > max_total_bytes:
        return {"total_bytes": total_bytes, "stop": True}
    seen_paths.add(relative_path)
    files.append(path)
    total_bytes += file_size
    stop = len(files) >= max_files or (
        max_total_bytes is not None and total_bytes >= max_total_bytes
    )
    return {"total_bytes": total_bytes, "stop": stop}


def _iter_repository_files_impl(
    root_path: Path,
    *,
    focus_paths: list[str] | tuple[str, ...],
    include_patterns: list[str] | tuple[str, ...],
    exclude_patterns: list[str] | tuple[str, ...],
    max_files: int,
    max_total_bytes: int | None,
) -> list[Path]:
    git_relative_files = _git_repository_relative_files(root_path)
    if git_relative_files is not None:
        files: list[Path] = []
        seen_paths: set[str] = set()
        total_bytes = 0
        for relative_path in git_relative_files:
            if focus_paths and not any(
                _matches_repository_scope(relative_path, focus_path) for focus_path in focus_paths
            ):
                continue
            result = _append_repository_file(
                root_path=root_path,
                path=root_path / relative_path,
                files=files,
                seen_paths=seen_paths,
                normalized_include_patterns=include_patterns,
                normalized_exclude_patterns=exclude_patterns,
                max_files=max_files,
                max_total_bytes=max_total_bytes,
                total_bytes=total_bytes,
            )
            total_bytes = int(result["total_bytes"])
            if bool(result["stop"]):
                break
        return files

    candidate_roots = _candidate_repository_roots(
        root_path=root_path,
        focus_paths=focus_paths,
    )
    files: list[Path] = []
    seen_paths: set[str] = set()
    total_bytes = 0
    for candidate_root in candidate_roots:
        if candidate_root.is_file():
            result = _append_repository_file(
                root_path=root_path,
                path=candidate_root,
                files=files,
                seen_paths=seen_paths,
                normalized_include_patterns=include_patterns,
                normalized_exclude_patterns=exclude_patterns,
                max_files=max_files,
                max_total_bytes=max_total_bytes,
                total_bytes=total_bytes,
            )
            total_bytes = int(result["total_bytes"])
            if bool(result["stop"]):
                break
            continue
        for current_root, dirnames, filenames in os.walk(candidate_root):
            dirnames[:] = [
                name for name in sorted(dirnames) if name not in _DEFAULT_EXCLUDED_PATH_PARTS
            ]
            for filename in sorted(filenames):
                result = _append_repository_file(
                    root_path=root_path,
                    path=Path(current_root) / filename,
                    files=files,
                    seen_paths=seen_paths,
                    normalized_include_patterns=include_patterns,
                    normalized_exclude_patterns=exclude_patterns,
                    max_files=max_files,
                    max_total_bytes=max_total_bytes,
                    total_bytes=total_bytes,
                )
                total_bytes = int(result["total_bytes"])
                if bool(result["stop"]):
                    return files
    return files


def _compact_repository_focus_paths(
    root_path: Path,
    *,
    focus_paths: list[str] | tuple[str, ...],
    include_patterns: list[str] | tuple[str, ...],
    exclude_patterns: list[str] | tuple[str, ...],
    max_files: int,
    max_total_bytes: int | None,
    prefer_concrete_focus_paths: bool = False,
) -> tuple[str, ...]:
    normalized_focus_paths = tuple(
        dict.fromkeys(value for value in focus_paths if str(value).strip())
    )
    if len(normalized_focus_paths) <= 1:
        return normalized_focus_paths

    existing_candidates: dict[str, Path] = {}
    for focus_path in normalized_focus_paths:
        candidate = (root_path / focus_path).resolve()
        if candidate.exists() and (candidate == root_path or root_path in candidate.parents):
            existing_candidates[focus_path] = candidate

    if not existing_candidates:
        return normalized_focus_paths

    redundant_directories: set[str] = set()
    for focus_path in normalized_focus_paths:
        candidate = existing_candidates.get(focus_path)
        if candidate is None or not candidate.is_dir():
            continue
        descendant_focus_paths = [
            other_focus_path
            for other_focus_path in normalized_focus_paths
            if other_focus_path != focus_path
            and _matches_repository_scope(other_focus_path, focus_path)
        ]
        if not descendant_focus_paths:
            continue
        if prefer_concrete_focus_paths and any(
            (
                descendant_candidate := existing_candidates.get(descendant_focus_path)
            ) is not None
            and descendant_candidate.is_file()
            for descendant_focus_path in descendant_focus_paths
        ):
            redundant_directories.add(focus_path)
            continue
        matched_files = _iter_repository_files_impl(
            root_path,
            focus_paths=(focus_path,),
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
            max_files=max_files,
            max_total_bytes=max_total_bytes,
        )
        if not matched_files:
            continue
        other_scopes = tuple(
            other_focus_path
            for other_focus_path in normalized_focus_paths
            if other_focus_path != focus_path
        )
        if all(
            any(
                _matches_repository_scope(
                    str(path.relative_to(root_path)).replace("\\", "/"),
                    other_scope,
                )
                for other_scope in other_scopes
            )
            for path in matched_files
        ):
            redundant_directories.add(focus_path)

    return tuple(
        focus_path
        for focus_path in normalized_focus_paths
        if focus_path not in redundant_directories
    )


def _iter_repository_files(
    root_path: Path,
    *,
    focus_paths: list[str] | tuple[str, ...],
    include_patterns: list[str] | tuple[str, ...],
    exclude_patterns: list[str] | tuple[str, ...],
    max_files: int,
    max_total_bytes: int | None,
) -> list[Path]:
    normalized_focus_paths = tuple(
        _normalize_repository_relative_path(value) for value in focus_paths if str(value).strip()
    )
    normalized_include_patterns = tuple(
        _normalize_repository_relative_path(value)
        for value in include_patterns
        if str(value).strip()
    )
    normalized_exclude_patterns = tuple(
        _normalize_repository_relative_path(value)
        for value in exclude_patterns
        if str(value).strip()
    )
    compacted_focus_paths = _compact_repository_focus_paths(
        root_path,
        focus_paths=normalized_focus_paths,
        include_patterns=normalized_include_patterns,
        exclude_patterns=normalized_exclude_patterns,
        max_files=max_files,
        max_total_bytes=max_total_bytes,
    )
    return _iter_repository_files_impl(
        root_path,
        focus_paths=compacted_focus_paths,
        include_patterns=normalized_include_patterns,
        exclude_patterns=normalized_exclude_patterns,
        max_files=max_files,
        max_total_bytes=max_total_bytes,
    )
