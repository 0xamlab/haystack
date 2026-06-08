from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from collections import Counter, deque
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

from apps.api_server.schemas.repositories import (
    RepositoryApplyMode,
    RepositoryApplyRequest,
    RepositoryDecisionPlanCreateRequest,
    RepositoryDiagnostic,
    RepositoryGraphQueryRequest,
    RepositorySimulationRequest,
    RepositorySnapshotCreateRequest,
    RepositoryTriageRequest,
)
from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import repository_intelligence_runtime as runtime_service
from apps.api_server.services.repository_language_priority import (
    canonical_repository_language,
    repository_language_priority,
    sort_repository_languages,
    sort_repository_languages_by_score,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "build" / "repository_intelligence_real_repo_probe.json"
DEFAULT_PERSISTED_RUNTIME_DIR = (
    PROJECT_ROOT / "build" / "repository_intelligence_real_repo_probe_runtime"
)


def _default_probe_include_patterns() -> list[str]:
    patterns: list[str] = []
    for suffix in sorted(repository_service._TEXT_FILE_SUFFIXES):
        suffix_variants = {suffix}
        suffix_body = suffix[1:] if suffix.startswith(".") else ""
        if suffix_body.isalnum() and any(character.isalpha() for character in suffix_body):
            suffix_variants.add(f".{suffix_body.upper()}")
        for suffix_variant in sorted(suffix_variants):
            patterns.append(f"**/*{suffix_variant}")
            patterns.append(f"*{suffix_variant}")
    patterns.extend(
        [
            "**/AxClass/*.xml",
            "**/AxClassExtension/*.xml",
            "**/Descriptor/*.xml",
        ]
    )
    for basename in sorted(repository_service._TEXT_FILE_BASENAMES):
        patterns.append(f"**/{basename}")
        patterns.append(basename)
    # Allow extensionless shebang-backed code files into the candidate set.
    patterns.extend(["**/*", "*"])
    return list(dict.fromkeys(patterns))


DEFAULT_INCLUDE_PATTERNS = _default_probe_include_patterns()
DEFAULT_EXCLUDE_PATTERNS = [
    ".git/**",
    "node_modules/**",
    ".next/**",
    "dist/**",
    "dist_fresh/**",
    "build/**",
    "coverage/**",
    "__pycache__/**",
    ".venv/**",
    "venv/**",
    ".turbo/**",
    ".mypy_cache/**",
    ".pytest_cache/**",
    "assets/**",
    "cache/**",
    "broadcast/**",
    "**/dist/**",
    "**/dist_fresh/**",
    "**/build/**",
    "**/coverage/**",
]
_TSC_DIAGNOSTIC_RE = re.compile(
    r"^(?P<path>.+?)\((?P<line>\d+),(?P<column>\d+)\):\s+error\s+(?P<code>TS\d+):\s+(?P<message>.+)$"
)
_PYTHON_TRACEBACK_FILE_RE = re.compile(
    r'^\s*File "(?P<path>.+?)", line (?P<line>\d+)(?:, in (?P<function>.+))?\s*$'
)
_NODE_STACK_FRAME_RE = re.compile(
    r"^\s*at\s+(?:(?P<function>.*?)\s+\()?(?P<path>.+?):(?P<line>\d+):(?P<column>\d+)\)?\s*$"
)
_RUST_SPAN_RE = re.compile(
    r"^\s*-->\s+(?P<path>.+?):(?P<line>\d+):(?P<column>\d+)\s*$"
)
_COLON_DIAGNOSTIC_RE = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+):(?P<column>\d+):\s+(?P<message>.+)$"
)
_SLN_PROJECT_RE = re.compile(
    r'^Project\("[^"]+"\)\s*=\s*"[^"]+",\s*"(?P<path>[^"]+\.(?:csproj|fsproj))"',
    re.MULTILINE,
)
_COMMAND_CD_RE = re.compile(r"^\s*cd\s+(?P<path>[^&;]+?)\s*&&")
_PROJECT_ARG_RE = re.compile(r"(?:^|\s)(?:-p|--project)\s+(?P<path>[^\s]+)")
_POWERSHELL_MANIFEST_FIELD_RE = re.compile(
    r"^\s*(?P<field>RootModule|ModuleToProcess)\s*=\s*['\"](?P<value>[^'\"]+)['\"]",
    re.IGNORECASE | re.MULTILINE,
)
_POWERSHELL_MANIFEST_LIST_RE = re.compile(
    r"^\s*(?P<field>NestedModules)\s*=\s*@\((?P<body>.*?)\)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
_LUAU_PROJECT_PATH_RE = re.compile(r'"\$path"\s*:\s*"(?P<path>[^"]+)"')
_LUAU_WALLY_NAME_RE = re.compile(
    r"(?ms)^\s*\[package\]\s.*?^\s*name\s*=\s*['\"](?P<name>[^'\"]+)['\"]"
)
_QUOTED_SEGMENT_RE = re.compile(r"""['"](?P<value>[^'"]+)['"]""")
_FOUNDRY_STRING_FIELD_RE = re.compile(
    r"^\s*(?P<field>src|script|test)\s*=\s*[\"'](?P<value>[^\"']+)[\"']",
    re.IGNORECASE | re.MULTILINE,
)
_FOUNDRY_LIST_FIELD_RE = re.compile(
    r"^\s*(?P<field>libs)\s*=\s*\[(?P<body>.*?)\]",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
_PREPASS_CACHE_SCHEMA_VERSION = "repository-probe-prepass-v74"
_REPO_PROFILE_MANIFEST_BASENAMES = frozenset(
    {
        ".smalltalk.all.ston",
        ".smalltalk.release.ston",
        ".smalltalk.ston",
        ".ibmi.json",
        "_coqproject",
        "_rocqproject",
        "lean-toolchain",
        "lakefile.lean",
        "lakefile.toml",
        "asconfig.json",
        "bb.edn",
        "bblayers.conf",
        "bicepconfig.json",
        "build",
        "build.bazel",
        "bender.yaml",
        "bender.yml",
        "bower.json",
        "build.pl",
        "brownie-config.yaml",
        "brownie-config.yml",
        "cpanfile",
        "description",
        "dockerfile",
        "namespace",
        "package.json",
        "package.dhall",
        "tsconfig.json",
        "jsconfig.json",
        "pyproject.toml",
        "pubspec.yaml",
        "dbt_project.yml",
        "dbt_project.yaml",
        "deps.edn",
        "package.yaml",
        "project.toml",
        "manifest.toml",
        "move.toml",
        "moon.mod",
        "moon.pkg",
        "qmldir",
        "qmake.conf",
        "containerfile",
        "alire.toml",
        "shard.yml",
        "cargo.toml",
        "go.mod",
        "iproj.json",
        "pom.xml",
        "project.clj",
        "build.sbt",
        "build.sc",
        "build.mill",
        "cask",
        "cakefile",
        "dune",
        "dune-project",
        "cabal.project",
        "cmakelists.txt",
        "build.gradle",
        "build.gradle.kts",
        "settings.gradle",
        "settings.gradle.kts",
        "sfdx-project.json",
        "layer.conf",
        "local.conf",
        ".latexmkrc",
        "latexmkrc",
        "mix.exs",
        "erlang.mk",
        "fpm.toml",
        "foundry.toml",
        "dub.json",
        "dub.sdl",
        "hardhat.config.cjs",
        "hardhat.config.js",
        "hardhat.config.mjs",
        "hardhat.config.ts",
        "rebar.config",
        "remappings.txt",
        "composer.json",
        "dist.ini",
        "elm.json",
        "info.rkt",
        "project.xml",
        "package.scm",
        "flake.nix",
        "gleam.toml",
        ".hhconfig",
        "default.nix",
        "hhvm.autoload",
        "hh_autoload.json",
        "module.bazel",
        "shell.nix",
        "tectonic.toml",
        "texmf.cnf",
        "v.mod",
        "gemfile",
        "makefile.pl",
        "mason.toml",
        "config.nims",
        "nim.cfg",
        "package.swift",
        "puppetfile",
        "meta6.json",
        "modulefile",
        "bsconfig.json",
        "rescript.json",
        "default.project.json",
        "shadow-cljs.edn",
        "spago.dhall",
        "spago.yaml",
        "stack.yaml",
        "sqlproj",
        "wally.toml",
        "build.zig",
        "meson.build",
        "truffle-config.js",
        "truffle.js",
        "project.godot",
        "project.janet",
        "ipkg",
        "dbproj",
        "vhdl_ls.toml",
        "pacletinfo.m",
        "pacletinfo.wl",
        "workspace",
        "workspace.bazel",
    }
)
_NON_OPERATIONAL_PROFILE_PATH_PARTS = frozenset(
    {
        "benchmark",
        "benchmarks",
        "bench",
        "buildsrc",
        "doc",
        "docs",
        "documentation",
        "docsrc",
        "demos",
        "examples",
        "features",
        "fixtures",
        "samples",
        "specs",
        "tutorial",
        "tutorials",
        "resource",
        "resources",
        "static",
        "test",
        "tests",
        "vignette",
        "vignettes",
    }
)
_NAMESPACE_PACKAGE_TOKENS = frozenset({"example", "examples", "sample", "samples"})
_DOCUMENTATION_PRIMARY_ECOSYSTEMS = frozenset({"rst", "tex", "typst", "asciidoc", "org"})
_DOCUMENTATION_OPERATIONAL_PATH_PARTS = frozenset(
    {
        "doc",
        "docs",
        "documentation",
        "docsrc",
        "tutorial",
        "tutorials",
        "vignette",
        "vignettes",
    }
)
_SCENARIO_PRIMARY_ECOSYSTEMS = frozenset({"gherkin"})
_SCENARIO_OPERATIONAL_PATH_PARTS = frozenset({"features", "specs"})
_NON_OPERATIONAL_PROJECT_PATH_PARTS = frozenset(
    set(_NON_OPERATIONAL_PROFILE_PATH_PARTS) | {"doc", "docs", "documentation"}
)
_C_FAMILY_SOURCE_TOKEN_RE = re.compile(
    r"(?P<path>[A-Za-z0-9_./+-]+\.(?:asm|c|cc|cpp|cxx|m|mm|s|h|hh|hpp|hxx|ipp|tpp))"
)
_ML_MANIFEST_PATH_RE = re.compile(
    r"(?P<path>[A-Za-z0-9_./+-]+\.(?:cm|fun|mlb|sig|sml))",
    re.IGNORECASE,
)
_SYSTEMVERILOG_MANIFEST_PATH_RE = re.compile(
    r"(?P<path>[A-Za-z0-9_./+-]+\.(?:sv|svh|v|vh))",
    re.IGNORECASE,
)
_GDSCRIPT_RESOURCE_RE = re.compile(r"res://(?P<path>[^\"'\s]+)", re.IGNORECASE)
_GDSCRIPT_SCENE_SCRIPT_RE = re.compile(
    r'\[ext_resource\s+type="Script"[^]]*path="(?P<path>res://[^"]+\.gd)"',
    re.IGNORECASE,
)
_ML_SOURCE_EXTENSIONS = (".sml", ".sig", ".fun")
_ZIG_SOURCE_TOKEN_RE = re.compile(r"(?P<path>[A-Za-z0-9_./+-]+\.zig)")
_HASKELL_SOURCE_EXTENSIONS = (".hs", ".hsc", ".lhs")
_CLOJURE_QUOTED_STRING_RE = re.compile(r'"(?P<value>[^"]+)"')
_CLOJURE_VECTOR_FIELD_RE = re.compile(
    r"(?P<field>:[A-Za-z0-9_-]+)\s*\[(?P<body>.*?)\]",
    re.DOTALL,
)
_CLOJURE_MAIN_RE = re.compile(r":main\s+(?P<target>[A-Za-z][A-Za-z0-9_.-]*)")
_LUA_ROCKSPEC_MODULE_RE = re.compile(
    r"\[\s*[\"'](?P<name>[^\"']+)[\"']\s*\]\s*=\s*[\"'](?P<path>[^\"']+\.lua)[\"']"
)
_LUA_ROCKSPEC_PACKAGE_RE = re.compile(r"package\s*=\s*[\"'](?P<name>[^\"']+)[\"']")
_CRYSTAL_SHARD_NAME_RE = re.compile(r"^\s*name:\s*(?P<name>[A-Za-z0-9_.-]+)\s*$", re.MULTILINE)
_CRYSTAL_SHARD_MAIN_RE = re.compile(r"^\s*main:\s*(?P<path>[^\s#]+)\s*$", re.MULTILINE)
_ADA_PROJECT_FIELD_RE = re.compile(
    r"\bfor\s+(?P<field>source_dirs|main|source_files)\s+use\s+(?P<body>\(.*?\)|\"[^\"]+\")\s*;",
    re.IGNORECASE | re.DOTALL,
)


def _perl_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(config_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}lib",
        f"{root_prefix}script",
        f"{root_prefix}bin",
        f"{root_prefix}app",
    }
    config_paths = {normalized_path}
    entrypoint_paths: set[str] = set()
    project_root = repo_path / project_dir
    for subdir_name, patterns in (
        ("lib", ("*.pm", "*.pl")),
        ("script", ("*.pl", "*.pm", "*.psgi")),
        ("bin", ("*.pl", "*.pm", "*.psgi")),
        ("app", ("*.pl", "*.pm", "*.psgi")),
    ):
        subdir = project_root / subdir_name
        if not subdir.is_dir():
            continue
        relative_root = repository_service._normalize_repository_relative_path(
            str(subdir.relative_to(repo_path))
        )
        if relative_root:
            support_roots.add(relative_root)
        for pattern in patterns:
            for candidate in sorted(subdir.rglob(pattern)):
                relative_path = repository_service._normalize_repository_relative_path(
                    str(candidate.relative_to(repo_path))
                )
                if (
                    relative_path
                    and not repository_service._is_test_path(relative_path)
                    and not _is_non_operational_profile_path(relative_path)
                ):
                    entrypoint_paths.add(relative_path)
    if entrypoint_paths:
        return entrypoint_paths, support_roots, config_paths
    for pattern in ("*.pm", "*.pl", "*.psgi"):
        for candidate in sorted(project_root.glob(pattern)):
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                relative_path
                and not repository_service._is_test_path(relative_path)
                and not _is_non_operational_profile_path(relative_path)
            ):
                entrypoint_paths.add(relative_path)
    return entrypoint_paths, support_roots, config_paths


def _r_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(config_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}R",
        f"{root_prefix}src",
        f"{root_prefix}inst",
    }
    config_paths = {normalized_path}
    project_root = repo_path / project_dir
    for sibling_name in ("DESCRIPTION", "NAMESPACE"):
        sibling_path = repository_service._normalize_repository_relative_path(
            str(project_dir / sibling_name)
        )
        if sibling_path and (repo_path / sibling_path).is_file():
            config_paths.add(sibling_path)
    entrypoint_paths: set[str] = set()
    package_root = project_root / "R"
    if package_root.is_dir():
        for pattern in ("*.R", "*.r"):
            for candidate in sorted(package_root.rglob(pattern)):
                relative_path = repository_service._normalize_repository_relative_path(
                    str(candidate.relative_to(repo_path))
                )
                if (
                    relative_path
                    and not repository_service._is_test_path(relative_path)
                    and not _is_non_operational_profile_path(relative_path)
                ):
                    entrypoint_paths.add(relative_path)
    if entrypoint_paths:
        return entrypoint_paths, support_roots, config_paths
    for candidate_name in ("app.R", "server.R", "ui.R", "app.r", "server.r", "ui.r"):
        candidate_path = repository_service._normalize_repository_relative_path(
            str(project_dir / candidate_name)
        )
        if candidate_path and (repo_path / candidate_path).is_file():
            entrypoint_paths.add(candidate_path)
    return entrypoint_paths, support_roots, config_paths


def _julia_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(config_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}ext",
    }
    config_paths = {normalized_path}
    manifest_path = repository_service._normalize_repository_relative_path(
        str(project_dir / "Manifest.toml")
    )
    if manifest_path and (repo_path / manifest_path).is_file():
        config_paths.add(manifest_path)
    entrypoint_paths = {
        f"{root_prefix}src/main.jl",
    }
    payload = _safe_load_toml_dict(repo_path / normalized_path)
    package_name = payload.get("name") if isinstance(payload, dict) else None
    if isinstance(package_name, str) and package_name.strip():
        entrypoint_paths.add(f"{root_prefix}src/{package_name.strip()}.jl")
    return entrypoint_paths, support_roots, config_paths


def _shard_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(config_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}lib",
        f"{root_prefix}bin",
    }
    config_paths = {normalized_path}
    entrypoint_paths = {
        f"{root_prefix}src/main.cr",
    }
    manifest_path = repo_path / normalized_path
    try:
        text = manifest_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    package_match = _CRYSTAL_SHARD_NAME_RE.search(text)
    package_name = str(package_match.group("name") or "").strip() if package_match else ""
    if package_name:
        normalized_name = re.sub(r"[^a-z0-9_]+", "_", package_name.lower()).strip("_")
        if normalized_name:
            entrypoint_paths.add(f"{root_prefix}src/{normalized_name}.cr")
    for match in _CRYSTAL_SHARD_MAIN_RE.finditer(text):
        resolved_path = repository_service._normalize_repository_relative_path(
            str(project_dir / match.group("path"))
        )
        if resolved_path:
            entrypoint_paths.add(resolved_path)
    return entrypoint_paths, support_roots, config_paths


def _is_repo_profile_manifest_name(name: str) -> bool:
    lower_name = name.lower()
    return (
        lower_name in _REPO_PROFILE_MANIFEST_BASENAMES
        or lower_name == "pkgindex.tcl"
        or (lower_name.startswith("tsconfig.") and lower_name.endswith(".json"))
        or (lower_name.startswith("jsconfig.") and lower_name.endswith(".json"))
        or lower_name.endswith(".cabal")
        or lower_name.endswith(".gemspec")
        or lower_name.endswith(".podspec")
        or lower_name.endswith(".rockspec")
        or lower_name.endswith(".nimble")
        or lower_name.endswith(".opam")
        or lower_name.endswith(".core")
        or lower_name.endswith(".mlb")
        or lower_name.endswith(".cm")
        or lower_name.endswith(".app.src")
        or lower_name.endswith(".sbt")
        or lower_name.endswith(".csproj")
        or lower_name.endswith(".fsproj")
        or lower_name.endswith(".vbproj")
        or lower_name.endswith(".hxml")
        or lower_name.endswith(".ipkg")
        or lower_name.endswith(".vbp")
        or lower_name.endswith(".yyp")
        or lower_name.endswith(".wsf")
        or lower_name.endswith(".asd")
        or lower_name.endswith(".lvproj")
        or lower_name.endswith(".lvlib")
        or lower_name.endswith(".lvclass")
        or lower_name.endswith(".gpr")
        or lower_name.endswith(".dproj")
        or lower_name.endswith(".lpi")
        or lower_name.endswith(".lpk")
        or lower_name.endswith(".sln")
        or lower_name.endswith(".sqlproj")
        or lower_name.endswith(".dbproj")
        or lower_name.endswith(".psd1")
        or lower_name.endswith(".mqproj")
        or lower_name.endswith(".agda-lib")
        or lower_name.endswith(".gms")
        or lower_name.endswith(".scad")
    )


def _is_xpp_descriptor_config_path(repo_path: Path, relative_path: str) -> bool:
    normalized_path = repository_service._normalize_repository_relative_path(relative_path)
    if not normalized_path:
        return False
    path = PurePosixPath(normalized_path)
    if path.suffix.lower() != ".xml" or path.parent.name.lower() != "descriptor":
        return False
    candidate = repo_path / normalized_path
    if not candidate.is_file() or candidate.is_symlink():
        return False
    try:
        text = candidate.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return repository_service.xpp_adapter.is_probable_xpp_descriptor_config(
        path=Path(normalized_path),
        text=text,
    )


def _is_cfml_box_config_path(repo_path: Path, relative_path: str) -> bool:
    normalized_path = repository_service._normalize_repository_relative_path(relative_path)
    if not normalized_path:
        return False
    path = PurePosixPath(normalized_path)
    if path.name.lower() != "box.json":
        return False
    candidate = repo_path / normalized_path
    if not candidate.is_file() or candidate.is_symlink():
        return False
    search_roots: list[Path] = []
    project_root = candidate.parent
    if project_root.is_dir():
        search_roots.append(project_root)
    if repo_path not in search_roots:
        search_roots.append(repo_path)
    seen_paths: set[str] = set()
    for search_root in search_roots:
        for suffix in ("*.cfc", "*.cfm", "*.cfml"):
            for source_path in sorted(search_root.rglob(suffix)):
                if not source_path.is_file() or source_path.is_symlink():
                    continue
                relative_source_path = repository_service._normalize_repository_relative_path(
                    str(source_path.relative_to(repo_path))
                )
                if (
                    not relative_source_path
                    or relative_source_path in seen_paths
                    or repository_service._is_test_path(relative_source_path)
                    or _is_non_operational_profile_path(relative_source_path)
                ):
                    continue
                seen_paths.add(relative_source_path)
                if _probe_language_for_path(relative_source_path, repo_path=repo_path) == "cfml":
                    return True
    return False


def _is_delphi_project_config_path(repo_path: Path, relative_path: str) -> bool:
    normalized_path = repository_service._normalize_repository_relative_path(relative_path)
    if not normalized_path:
        return False
    path = PurePosixPath(normalized_path)
    if path.suffix.lower() != ".dproj":
        return False
    candidate = repo_path / normalized_path
    if not candidate.is_file() or candidate.is_symlink():
        return False
    try:
        text = candidate.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    if not repository_service.delphi_adapter.is_probable_delphi_source(
        path=Path(normalized_path),
        text=text,
    ):
        return False
    search_roots: list[Path] = []
    project_root = candidate.parent
    if project_root.is_dir():
        search_roots.append(project_root)
    if repo_path not in search_roots:
        search_roots.append(repo_path)
    seen_paths: set[str] = set()
    for search_root in search_roots:
        for suffix in ("*.dpr", "*.dpk", "*.pas"):
            for source_path in sorted(search_root.rglob(suffix)):
                if not source_path.is_file() or source_path.is_symlink():
                    continue
                relative_source_path = repository_service._normalize_repository_relative_path(
                    str(source_path.relative_to(repo_path))
                )
                if (
                    not relative_source_path
                    or relative_source_path in seen_paths
                    or repository_service._is_test_path(relative_source_path)
                    or _is_non_operational_profile_path(relative_source_path)
                ):
                    continue
                seen_paths.add(relative_source_path)
                if _probe_language_for_path(relative_source_path, repo_path=repo_path) == "delphi":
                    return True
    return False


def _is_eiffel_project_config_path(repo_path: Path, relative_path: str) -> bool:
    normalized_path = repository_service._normalize_repository_relative_path(relative_path)
    if not normalized_path:
        return False
    path = PurePosixPath(normalized_path)
    if path.suffix.lower() not in {".ecf", ".ace"}:
        return False
    candidate = repo_path / normalized_path
    if not candidate.is_file() or candidate.is_symlink():
        return False
    try:
        text = candidate.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    if not repository_service.eiffel_adapter.is_probable_eiffel_source(
        path=Path(normalized_path),
        text=text,
    ):
        return False
    search_roots = [candidate.parent, repo_path]
    seen_paths: set[str] = set()
    for search_root in search_roots:
        if not search_root.is_dir():
            continue
        for source_path in sorted(search_root.rglob("*.e")):
            if not source_path.is_file() or source_path.is_symlink():
                continue
            relative_source_path = repository_service._normalize_repository_relative_path(
                str(source_path.relative_to(repo_path))
            )
            if (
                not relative_source_path
                or relative_source_path in seen_paths
                or repository_service._is_test_path(relative_source_path)
                or _is_non_operational_profile_path(relative_source_path)
            ):
                continue
            seen_paths.add(relative_source_path)
            if _probe_language_for_path(relative_source_path, repo_path=repo_path) == "eiffel":
                return True
    return False


def _is_purescript_bower_config_path(repo_path: Path, relative_path: str) -> bool:
    normalized_path = repository_service._normalize_repository_relative_path(relative_path)
    if not normalized_path:
        return False
    path = PurePosixPath(normalized_path)
    if path.name.lower() != "bower.json":
        return False
    candidate = repo_path / normalized_path
    if not candidate.is_file() or candidate.is_symlink():
        return False
    project_root = candidate.parent
    search_roots = [
        project_root / "src",
        project_root / "app",
        project_root / "test",
        project_root / "tests",
        project_root / "examples",
        project_root,
    ]
    seen_paths: set[str] = set()
    for search_root in search_roots:
        if not search_root.is_dir():
            continue
        for source_path in sorted(search_root.rglob("*.purs")):
            if not source_path.is_file() or source_path.is_symlink():
                continue
            relative_source_path = repository_service._normalize_repository_relative_path(
                str(source_path.relative_to(repo_path))
            )
            if (
                not relative_source_path
                or relative_source_path in seen_paths
                or repository_service._is_test_path(relative_source_path)
                or _is_non_operational_profile_path(relative_source_path)
            ):
                continue
            seen_paths.add(relative_source_path)
            if _probe_language_for_path(relative_source_path, repo_path=repo_path) == "purescript":
                return True
    return False


def _is_rescript_config_path(repo_path: Path, relative_path: str) -> bool:
    normalized_path = repository_service._normalize_repository_relative_path(relative_path)
    if not normalized_path:
        return False
    path = PurePosixPath(normalized_path)
    if path.name.lower() not in repository_service.rescript_adapter.RESCRIPT_CONFIG_BASENAMES:
        return False
    candidate = repo_path / normalized_path
    if not candidate.is_file() or candidate.is_symlink():
        return False
    try:
        text = candidate.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return repository_service.rescript_adapter.is_probable_rescript_config(
        path=Path(normalized_path),
        text=text,
    )


def _is_moonbit_config_path(repo_path: Path, relative_path: str) -> bool:
    normalized_path = repository_service._normalize_repository_relative_path(relative_path)
    if not normalized_path:
        return False
    path = PurePosixPath(normalized_path)
    if path.name.lower() not in repository_service.moonbit_adapter.MOONBIT_CONFIG_BASENAMES:
        return False
    candidate = repo_path / normalized_path
    if not candidate.is_file() or candidate.is_symlink():
        return False
    try:
        text = candidate.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return repository_service.moonbit_adapter.is_probable_moonbit_config(
        path=Path(normalized_path),
        text=text,
    )


def _is_puppet_metadata_config_path(repo_path: Path, relative_path: str) -> bool:
    normalized_path = repository_service._normalize_repository_relative_path(relative_path)
    if not normalized_path or PurePosixPath(normalized_path).name.lower() != "metadata.json":
        return False
    candidate = repo_path / normalized_path
    if not candidate.is_file() or candidate.is_symlink():
        return False
    try:
        text = candidate.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return repository_service.puppet_adapter.is_probable_puppet_source(
        path=Path(normalized_path),
        text=text,
    )


def _is_odin_ols_config_path(repo_path: Path, relative_path: str) -> bool:
    normalized_path = repository_service._normalize_repository_relative_path(relative_path)
    if not normalized_path or PurePosixPath(normalized_path).name.lower() != "ols.json":
        return False
    candidate = repo_path / normalized_path
    if not candidate.is_file() or candidate.is_symlink():
        return False
    try:
        text = candidate.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return repository_service.odin_adapter.is_probable_odin_source(
        path=Path(normalized_path),
        text=text,
    )


def _is_cue_module_config_path(repo_path: Path, relative_path: str) -> bool:
    normalized_path = repository_service._normalize_repository_relative_path(relative_path)
    if not normalized_path:
        return False
    path = PurePosixPath(normalized_path)
    if path.name.lower() != "module.cue" or path.parent.name.lower() != "cue.mod":
        return False
    candidate = repo_path / normalized_path
    if not candidate.is_file() or candidate.is_symlink():
        return False
    try:
        text = candidate.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return repository_service.cue_adapter.is_probable_cue_source(
        path=Path(normalized_path),
        text=text,
    )


def _is_qmake_project_config_path(repo_path: Path, relative_path: str) -> bool:
    normalized_path = repository_service._normalize_repository_relative_path(relative_path)
    if not normalized_path:
        return False
    path = PurePosixPath(normalized_path)
    if (
        path.suffix.lower() not in repository_service.qmake_adapter.QMAKE_SUFFIXES
        and path.name.lower() not in repository_service.qmake_adapter.QMAKE_CONFIG_BASENAMES
    ):
        return False
    candidate = repo_path / normalized_path
    if not candidate.is_file() or candidate.is_symlink():
        return False
    try:
        text = candidate.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return repository_service.qmake_adapter.is_probable_qmake_source(
        path=Path(normalized_path),
        text=text,
    )


def _profile_path_tokens(path: str) -> set[str]:
    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return set()
    tokens: set[str] = set()
    for part in PurePosixPath(normalized_path).parts:
        lowered_part = part.lower()
        tokens.add(lowered_part)
        tokens.update(
            token for token in re.split(r"[^a-z0-9]+", lowered_part) if token
        )
    return tokens


def _is_namespace_style_source_path(path: str) -> bool:
    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return False
    language = repository_service._language_for_path(Path(normalized_path))
    if language not in {"java", "kotlin", "kt", "kts", "scala"}:
        return False
    parts = [part.lower() for part in PurePosixPath(normalized_path).parts]
    source_roots = (
        ("src", "main", "java"),
        ("src", "main", "kotlin"),
        ("src", "main", "scala"),
        ("src", "java"),
        ("src", "kotlin"),
        ("src", "scala"),
    )
    return any(
        len(parts) > len(source_root) + 1 and parts[: len(source_root)] == list(source_root)
        for source_root in source_roots
    )


def _is_non_operational_profile_path(path: str) -> bool:
    matched_tokens = _profile_path_tokens(path) & _NON_OPERATIONAL_PROFILE_PATH_PARTS
    if matched_tokens and _is_namespace_style_source_path(path):
        matched_tokens = {
            token for token in matched_tokens if token not in _NAMESPACE_PACKAGE_TOKENS
        }
    return bool(matched_tokens)


def _is_non_operational_profile_path_for_ecosystems(
    path: str,
    *,
    ecosystems: set[str] | None = None,
    repo_path: Path | None = None,
) -> bool:
    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return False
    matched_tokens = _profile_path_tokens(normalized_path) & _NON_OPERATIONAL_PROFILE_PATH_PARTS
    if matched_tokens and _is_namespace_style_source_path(normalized_path):
        matched_tokens = {
            token for token in matched_tokens if token not in _NAMESPACE_PACKAGE_TOKENS
        }
    if not matched_tokens:
        return False
    canonical_ecosystems = {
        canonical_repository_language(ecosystem)
        for ecosystem in (ecosystems or set())
        if canonical_repository_language(ecosystem)
    }
    if not canonical_ecosystems and repo_path is not None:
        detected_language = canonical_repository_language(
            _probe_language_for_path(normalized_path, repo_path=repo_path)
        )
        if detected_language:
            canonical_ecosystems.add(detected_language)
    if (
        canonical_ecosystems & _DOCUMENTATION_PRIMARY_ECOSYSTEMS
        and matched_tokens <= _DOCUMENTATION_OPERATIONAL_PATH_PARTS
    ):
        return False
    if (
        canonical_ecosystems & _SCENARIO_PRIMARY_ECOSYSTEMS
        and matched_tokens <= _SCENARIO_OPERATIONAL_PATH_PARTS
    ):
        return False
    return True


def _is_non_operational_project_path(path: str) -> bool:
    return bool(_profile_path_tokens(path) & _NON_OPERATIONAL_PROJECT_PATH_PARTS)


def _probe_language_for_path(path: str, *, repo_path: Path | None = None) -> str:
    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return "unknown"
    text: str | None = None
    candidate_path = Path(normalized_path)
    if repo_path is not None and (
        candidate_path.name.lower() in repository_service.hack_adapter.HACK_CONFIG_BASENAMES
        or candidate_path.suffix.lower()
        in {".hack", ".hh", ".hhi", ".php"}
        or
        candidate_path.suffix.lower()
        in {
        "",
        ".as",
        ".apex",
        ".applescript",
        ".auk",
        ".awk",
        ".bas",
        ".cls",
        ".ctl",
        ".dfm",
        ".dpk",
        ".dpr",
        ".dproj",
        ".e",
        ".ecf",
        ".el",
        ".dockerfile",
        ".coffee",
        ".litcoffee",
        ".fmx",
        ".agda",
        ".agda-lib",
        ".gms",
        ".gleam",
        ".idr",
        ".ipkg",
        ".janet",
        ".lagda",
        ".lidr",
        ".raku",
        ".rakumod",
        ".rakutest",
        ".pm6",
        ".p6",
        ".pp",
        ".hx",
        ".hxml",
        ".scad",
        ".ace",
        ".frm",
        ".gawk",
        ".h",
        ".inc",
        ".l5x",
        ".m",
        ".mqproj",
        ".mawk",
        ".mm",
        ".nawk",
        ".pas",
        ".pl",
        ".pch",
        ".purs",
        ".sql",
        ".sqlproj",
        ".st",
        ".rkt",
        ".rktl",
        ".robot",
        ".resource",
        ".tpl",
        ".rst",
        ".rest",
        ".adoc",
        ".asciidoc",
        ".asc",
        ".org",
        ".scpt",
        ".scm",
        ".sld",
        ".sps",
        ".dbproj",
        ".prg",
        ".ss",
        ".trigger",
        ".vim",
        ".v",
        ".vh",
        ".vhd",
        ".vhdl",
        ".vbp",
        ".sv",
        ".svh",
        ".wl",
        ".wls",
        ".wsf",
        ".xml",
        }
        or repository_service.starlark_adapter.has_starlark_path_hints(candidate_path)
    ):
        try:
            text = (repo_path / normalized_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = None
    return repository_service._language_for_path(candidate_path, text=text, repo_root=repo_path)


def _is_profile_entrypoint_noise(path: str) -> bool:
    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return True
    basename = PurePosixPath(normalized_path).name.lower()
    if basename == "contents.m":
        return True
    if basename in {"pacletinfo.m", "pacletinfo.wl"}:
        return True
    return basename.endswith(
        (
            ".intf.abap",
            ".incl.abap",
            ".clas.locals_def.abap",
            ".clas.locals_imp.abap",
            ".clas.testclasses.abap",
            ".cpy",
            ".inc",
            ".rpginc",
            ".rpgleinc",
            ".mqh",
            ".pks",
            ".d.ts",
            ".min.js",
            ".min.cjs",
            ".min.mjs",
            ".min.jsx",
            ".min.ts",
            ".min.tsx",
        )
)


def _is_operational_profile_entrypoint_candidate(
    path: str,
    *,
    repo_path: Path | None = None,
) -> bool:
    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return False
    language = _probe_language_for_path(normalized_path, repo_path=repo_path)
    basename = PurePosixPath(normalized_path).name.lower()
    if language == "robotframework":
        return (
            PurePosixPath(normalized_path).suffix.lower() == ".robot"
            and basename
            not in {"resource.robot", "common.resource", "keywords.resource", "variables.resource"}
        )
    if language == "nextflow":
        return PurePosixPath(normalized_path).suffix.lower() == ".nf"
    if repository_service._is_test_path(normalized_path):
        return False
    if _is_non_operational_profile_path_for_ecosystems(
        normalized_path,
        ecosystems={language},
        repo_path=repo_path,
    ):
        return False
    if _is_profile_entrypoint_noise(normalized_path):
        return False
    if language == "assembly" and PurePosixPath(normalized_path).suffix.lower() == ".inc":
        return False
    if language == "objectivec" and PurePosixPath(normalized_path).suffix.lower() in {
        ".h",
        ".pch",
    }:
        return False
    if language == "ml" and PurePosixPath(normalized_path).suffix.lower() == ".sig":
        return False
    if language == "rpg" and PurePosixPath(normalized_path).suffix.lower() in {
        ".rpginc",
        ".rpgleinc",
    }:
        return False
    if language == "ladder" and repo_path is not None:
        candidate_path = repo_path / normalized_path
        try:
            text = candidate_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        if not repository_service.ladder_adapter.is_probable_operational_entrypoint(
            path=Path(normalized_path),
            text=text,
        ):
            return False
    if language == "vb6" and PurePosixPath(normalized_path).suffix.lower() in {
        ".cls",
        ".ctl",
        ".vbp",
    }:
        return False
    if language == "labview" and PurePosixPath(normalized_path).suffix.lower() in {
        ".ctl",
        ".lvproj",
    }:
        return False
    if language == "tcl" and PurePosixPath(normalized_path).name.lower() == "pkgindex.tcl":
        return False
    if language == "delphi" and PurePosixPath(normalized_path).suffix.lower() in {
        ".dfm",
        ".fmx",
    }:
        return False
    if language == "systemverilog" and PurePosixPath(normalized_path).suffix.lower() in {
        ".svh",
        ".vh",
    }:
        return False
    if language == "verilog" and PurePosixPath(normalized_path).suffix.lower() == ".vh":
        return False
    if language == "vhdl":
        basename = PurePosixPath(normalized_path).name.lower()
        if (
            _profile_path_tokens(normalized_path) & {"tb", "testbench"}
            or basename.endswith(("_tb.vhd", "_tb.vhdl", "_test.vhd", "_test.vhdl"))
        ):
            return False
    if language == "gdscript":
        basename = PurePosixPath(normalized_path).name.lower()
        if basename.startswith("test_") or basename.endswith("_test.gd"):
            return False
    if language == "vhdl" and repo_path is not None:
        candidate_path = repo_path / normalized_path
        try:
            text = candidate_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        if not repository_service.vhdl_adapter.is_probable_operational_entrypoint(
            path=Path(normalized_path),
            text=text,
        ):
            return False
    if language == "gdscript" and repo_path is not None:
        candidate_path = repo_path / normalized_path
        try:
            text = candidate_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        if not repository_service.gdscript_adapter.is_probable_operational_entrypoint(
            path=Path(normalized_path),
            text=text,
        ):
            return False
    if language == "apex" and repo_path is not None:
        candidate_path = repo_path / normalized_path
        try:
            text = candidate_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        if repository_service.apex_adapter.is_probable_test_source(
            path=Path(normalized_path),
            text=text,
        ):
            return False
    return _is_repo_profile_code_candidate(normalized_path, repo_path=repo_path)


def _repository_connector(repo_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"repository-probe:{repo_path}"),
        org_id=uuid.uuid5(uuid.NAMESPACE_URL, "repository-probe-org"),
        owner_key_id=None,
        connector_type=SimpleNamespace(value="local_repo"),
        config_json=json.dumps({"path": str(repo_path)}),
    )


def _resolve_diagnostic_base_path(
    repo_path: Path,
    *,
    diagnostic_command: str | None,
    diagnostic_base_path: str | None,
) -> Path:
    base_value = diagnostic_base_path
    if base_value is None and diagnostic_command:
        match = _COMMAND_CD_RE.match(diagnostic_command)
        if match:
            base_value = match.group("path").strip()
    if not base_value:
        return repo_path
    candidate = (repo_path / base_value).resolve()
    if candidate == repo_path or repo_path in candidate.parents:
        return candidate
    return repo_path


def _resolve_diagnostic_project_path(
    repo_path: Path,
    *,
    diagnostic_command: str | None,
    diagnostic_base_path: Path,
) -> str | None:
    if not diagnostic_command:
        return None
    match = _PROJECT_ARG_RE.search(diagnostic_command)
    if match is None:
        return None
    candidate = (diagnostic_base_path / match.group("path").strip()).resolve()
    if candidate == repo_path or repo_path in candidate.parents:
        return str(candidate.relative_to(repo_path))
    return None


def _normalize_relative_path(
    repo_path: Path,
    raw_path: str,
    *,
    base_path: Path | None = None,
) -> str | None:
    candidate = Path(raw_path.strip())
    if not candidate.is_absolute():
        candidate = ((base_path or repo_path) / candidate).resolve()
    else:
        candidate = candidate.resolve()
    if candidate == repo_path or repo_path in candidate.parents:
        return str(candidate.relative_to(repo_path))
    return None


def parse_repository_diagnostics(
    *,
    repo_path: Path,
    output: str,
    base_path: Path | None = None,
) -> list[RepositoryDiagnostic]:
    diagnostics: list[RepositoryDiagnostic] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        ts_match = _TSC_DIAGNOSTIC_RE.match(line)
        if ts_match:
            normalized = _normalize_relative_path(
                repo_path,
                ts_match.group("path"),
                base_path=base_path,
            )
            diagnostics.append(
                RepositoryDiagnostic(
                    path=normalized,
                    line=int(ts_match.group("line")),
                    severity="error",
                    code=ts_match.group("code"),
                    message=ts_match.group("message").strip(),
                )
            )
            continue
        python_match = _PYTHON_TRACEBACK_FILE_RE.match(raw_line)
        if python_match:
            normalized = _normalize_relative_path(
                repo_path,
                python_match.group("path"),
                base_path=base_path,
            )
            function_name = str(python_match.group("function") or "").strip()
            diagnostics.append(
                RepositoryDiagnostic(
                    path=normalized,
                    line=int(python_match.group("line")),
                    severity="error",
                    code=None,
                    message=(
                        f"Python traceback frame in {function_name}"
                        if function_name
                        else "Python traceback frame"
                    ),
                )
            )
            continue
        node_match = _NODE_STACK_FRAME_RE.match(raw_line)
        if node_match:
            normalized = _normalize_relative_path(
                repo_path,
                node_match.group("path"),
                base_path=base_path,
            )
            function_name = str(node_match.group("function") or "").strip()
            diagnostics.append(
                RepositoryDiagnostic(
                    path=normalized,
                    line=int(node_match.group("line")),
                    severity="error",
                    code=None,
                    message=(
                        f"JavaScript stack frame in {function_name}"
                        if function_name
                        else "JavaScript stack frame"
                    ),
                )
            )
            continue
        rust_match = _RUST_SPAN_RE.match(raw_line)
        if rust_match:
            normalized = _normalize_relative_path(
                repo_path,
                rust_match.group("path"),
                base_path=base_path,
            )
            diagnostics.append(
                RepositoryDiagnostic(
                    path=normalized,
                    line=int(rust_match.group("line")),
                    severity="error",
                    code=None,
                    message="Rust compiler span",
                )
            )
            continue
        colon_match = _COLON_DIAGNOSTIC_RE.match(line)
        if colon_match:
            normalized = _normalize_relative_path(
                repo_path,
                colon_match.group("path"),
                base_path=base_path,
            )
            diagnostics.append(
                RepositoryDiagnostic(
                    path=normalized,
                    line=int(colon_match.group("line")),
                    severity="error",
                    code=None,
                    message=colon_match.group("message").strip(),
                )
            )
    return diagnostics


def _focus_paths_from_diagnostics(
    *,
    repo_path: Path,
    diagnostics: list[RepositoryDiagnostic],
    explicit_focus_paths: list[str],
) -> list[str]:
    focus_paths: list[str] = []
    seen: set[str] = set()

    def _add(value: str | None) -> None:
        if value is None:
            return
        normalized = value.strip().strip("/")
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        focus_paths.append(normalized)

    for value in explicit_focus_paths:
        _add(value)
    for diagnostic in diagnostics:
        if diagnostic.path:
            _add(diagnostic.path)
            parent = str(Path(diagnostic.path).parent)
            if parent not in {".", ""}:
                _add(parent)
    if not focus_paths:
        for default_path in ("services", "packages", "adapters", "scripts"):
            if (repo_path / default_path).exists():
                _add(default_path)
    return focus_paths


def _effective_focus_paths_for_snapshot(
    *,
    diagnostics: list[RepositoryDiagnostic],
    connected_files: list[str],
    fallback_focus_paths: list[str],
    config_focus_paths: list[str],
) -> list[str]:
    if connected_files and diagnostics:
        return list(
            dict.fromkeys(
                connected_files
                + [
                    path
                    for path in fallback_focus_paths
                    if _looks_like_concrete_file_seed(path)
                ]
                + config_focus_paths
            )
        )
    if connected_files:
        return list(
            dict.fromkeys(
                connected_files
                + [
                    path
                    for path in fallback_focus_paths
                    if _looks_like_concrete_file_seed(path)
                ]
                + config_focus_paths
            )
        )
    return list(
        dict.fromkeys(
            (connected_files if connected_files else fallback_focus_paths)
            + fallback_focus_paths
            + config_focus_paths
        )
    )


def _candidate_config_focus_paths(
    *,
    repo_path: Path,
    focus_paths: list[str],
    diagnostic_base_path: Path,
    diagnostic_project_path: str | None,
) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def _add(path: Path) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            return
        if not resolved.exists() or not resolved.is_file():
            return
        if not (resolved == repo_path or repo_path in resolved.parents):
            return
        relative = str(resolved.relative_to(repo_path)).replace("\\", "/")
        if relative in seen:
            return
        seen.add(relative)
        candidates.append(relative)

    for focus_path in focus_paths:
        focus_candidate = (repo_path / focus_path).resolve()
        if focus_candidate.exists():
            current = focus_candidate if focus_candidate.is_dir() else focus_candidate.parent
            while current == repo_path or repo_path in current.parents:
                for name in (
                    "tsconfig.test.json",
                    "tsconfig.json",
                    "tsconfig.base.json",
                    "tsconfig.eslint.json",
                    "package.json",
                ):
                    _add(current / name)
                if current == repo_path:
                    break
                current = current.parent

    current = diagnostic_base_path
    while current == repo_path or repo_path in current.parents:
        for name in (
            "tsconfig.test.json",
            "tsconfig.json",
            "tsconfig.base.json",
            "tsconfig.eslint.json",
            "package.json",
        ):
            _add(current / name)
        if current == repo_path:
            break
        current = current.parent

    if diagnostic_project_path:
        _add(repo_path / diagnostic_project_path)

    return candidates


def _inventory_repo_surface(
    *,
    repo_path: Path,
    focus_paths: list[str],
    include_patterns: list[str],
    exclude_dirnames: set[str],
    max_file_size_bytes: int,
) -> dict[str, Any]:
    file_count = 0
    total_bytes = 0
    suffix_counts: Counter[str] = Counter()
    for relative in _probe_repository_file_paths(
        repo_path=repo_path,
        focus_paths=focus_paths,
        include_patterns=include_patterns,
        exclude_dirnames=exclude_dirnames,
        max_files=None,
    ):
        candidate = repo_path / relative
        try:
            size = candidate.stat().st_size
        except OSError:
            continue
        if size > max_file_size_bytes:
            continue
        file_count += 1
        total_bytes += size
        suffix_counts[candidate.suffix.lower() or "<none>"] += 1
    return {
        "file_count": file_count,
        "total_bytes": total_bytes,
        "total_megabytes": round(total_bytes / 1024 / 1024, 2),
        "top_suffixes": dict(suffix_counts.most_common(12)),
    }


def _git_repo_relative_files(repo_path: Path) -> list[str] | None:
    if not repository_service._is_git_repository(repo_path):
        return None
    commands = [
        ["git", "-C", str(repo_path), "ls-files"],
        ["git", "-C", str(repo_path), "ls-files", "--others", "--exclude-standard"],
    ]
    relative_paths: set[str] = set()
    for command in commands:
        output = str(repository_service._git_command(command, timeout=120.0))
        for line in output.splitlines():
            normalized = repository_service._normalize_repository_relative_path(line)
            if normalized:
                relative_paths.add(normalized)
    return sorted(relative_paths)


def _matches_focus_paths(relative_path: str, focus_paths: list[str]) -> bool:
    if not focus_paths:
        return True
    for focus_path in focus_paths:
        normalized_focus = repository_service._normalize_repository_relative_path(focus_path)
        if not normalized_focus:
            continue
        if relative_path == normalized_focus or relative_path.startswith(f"{normalized_focus}/"):
            return True
    return False


_TEMPLATE_SURFACE_ECOSYSTEMS = frozenset(
    {
        "astro",
        "blade",
        "erb",
        "ejs",
        "haml",
        "handlebars",
        "jinja",
        "liquid",
        "mustache",
        "nunjucks",
        "pug",
        "slim",
        "svelte",
        "twig",
        "vue",
    }
)
_TEMPLATE_SURFACE_PARTS = frozenset({"views", "templates", "layouts", "partials", "shared", "components"})


def _probe_collection_rank(
    relative_path: str,
    *,
    repo_path: Path | None = None,
) -> tuple[int, int, int, int, str]:
    normalized_path = repository_service._normalize_repository_relative_path(relative_path)
    if not normalized_path:
        return (1, 1, 1, 1, relative_path)
    basename = PurePosixPath(normalized_path).name.lower()
    part_set = {part.lower() for part in PurePosixPath(normalized_path).parts}
    language = _probe_language_for_path(normalized_path, repo_path=repo_path)
    is_test = 1 if repository_service._is_test_path(normalized_path) else 0
    is_manifest = (
        0
        if _is_repo_profile_manifest_name(basename)
        or (repo_path is not None and _is_xpp_descriptor_config_path(repo_path, normalized_path))
        or (repo_path is not None and _is_cfml_box_config_path(repo_path, normalized_path))
        else 1
    )
    is_non_code = (
        1
        if language in repository_service._NON_CODE_GRAPH_LANGUAGES
        or language in {"unknown", "txt"}
        else 0
    )
    platform_noise = (
        1
        if (
            normalized_path.startswith(".github/")
            or normalized_path.startswith("docs/")
            or part_set & {"doc", "docs", "docs_src", "example", "examples", "sample", "samples"}
            or basename
            in {"readme.md", "changelog.md", "contributing.md", "license", "license.txt"}
        )
        else 0
    )
    template_surface_priority = (
        0
        if language in _TEMPLATE_SURFACE_ECOSYSTEMS and part_set & _TEMPLATE_SURFACE_PARTS
        else 1
    )
    return (
        is_test,
        min(is_non_code, is_manifest),
        template_surface_priority,
        platform_noise,
        normalized_path,
    )


def _probe_repository_file_paths(
    *,
    repo_path: Path,
    focus_paths: list[str],
    include_patterns: list[str],
    exclude_dirnames: set[str],
    max_files: int | None,
) -> list[str]:
    git_relative_files = _git_repo_relative_files(repo_path)
    if git_relative_files is not None:
        collected: list[str] = []
        for relative in git_relative_files:
            if any(part in exclude_dirnames for part in Path(relative).parts[:-1]):
                continue
            if not _matches_focus_paths(relative, focus_paths):
                continue
            if include_patterns and not any(
                repository_service._matches_repository_pattern(relative, pattern)
                for pattern in include_patterns
            ):
                continue
            candidate = repo_path / relative
            if not candidate.exists() or not candidate.is_file() or candidate.is_symlink():
                continue
            collected.append(relative)
        ordered = sorted(
            collected,
            key=lambda relative_path: _probe_collection_rank(
                relative_path,
                repo_path=repo_path,
            ),
        )
        if max_files is not None:
            return ordered[:max_files]
        return ordered

    roots = [repo_path / path for path in focus_paths] if focus_paths else [repo_path]
    collected_paths: list[str] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            candidates = [root]
        else:
            candidates = []
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [name for name in dirnames if name not in exclude_dirnames]
                candidates.extend(Path(dirpath) / name for name in filenames)
        for candidate in candidates:
            if candidate in seen or not candidate.is_file() or candidate.is_symlink():
                continue
            seen.add(candidate)
            relative = str(candidate.relative_to(repo_path)).replace("\\", "/")
            if include_patterns and not any(
                repository_service._matches_repository_pattern(relative, pattern)
                for pattern in include_patterns
            ):
                continue
            collected_paths.append(relative)
    ordered = sorted(
        collected_paths,
        key=lambda relative_path: _probe_collection_rank(
            relative_path,
            repo_path=repo_path,
        ),
    )
    if max_files is not None:
        return ordered[:max_files]
    return ordered


def _candidate_repository_file_paths(
    *,
    repo_path: Path,
    seed_paths: list[str],
    bridge_paths: list[str],
    include_patterns: list[str],
    max_files: int,
) -> list[str]:
    collected: list[str] = []
    seen: set[str] = set()

    def _bridge_root_top_level_group_count(bridge_paths: list[str]) -> int:
        top_level_groups: set[str] = set()
        for bridge_path in bridge_paths:
            normalized_path = repository_service._normalize_repository_relative_path(bridge_path)
            if not normalized_path:
                continue
            top_level_groups.add(PurePosixPath(normalized_path).parts[0])
        return len(top_level_groups)

    def _bridge_root_spread_limit(*, remaining_files: int, bridge_path_count: int) -> int:
        if remaining_files <= 0 or bridge_path_count <= 0:
            return 0
        per_bridge_limit = max(1, min(4, (remaining_files // bridge_path_count) or 1))
        if bridge_path_count >= 48:
            return min(per_bridge_limit, 1)
        if bridge_path_count >= 24:
            return min(per_bridge_limit, 3)
        return per_bridge_limit

    def _ordered_file_paths(file_paths: list[str]) -> list[str]:
        return sorted(file_paths, key=_probe_collection_rank)

    def _collect_per_focus_path(
        focus_paths: list[str],
        *,
        per_focus_limit: int,
        total_limit: int,
    ) -> None:
        if per_focus_limit <= 0 or total_limit <= len(collected):
            return
        normalized_focus_paths = list(
            dict.fromkeys(
                repository_service._normalize_repository_relative_path(path)
                for path in focus_paths
                if str(path).strip()
            )
        )
        normalized_focus_paths = [path for path in normalized_focus_paths if path]
        if not normalized_focus_paths:
            return
        if not _should_group_focus_path_scan(normalized_focus_paths):
            for focus_path in normalized_focus_paths:
                if len(collected) >= total_limit:
                    return
                _collect(
                    [focus_path],
                    min(per_focus_limit, total_limit - len(collected)),
                )
            return
        remaining_total = total_limit - len(collected)
        if remaining_total <= 0:
            return
        candidate_file_paths = _probe_repository_file_paths(
            repo_path=repo_path,
            focus_paths=normalized_focus_paths,
            include_patterns=include_patterns,
            exclude_dirnames=set(repository_service._DEFAULT_EXCLUDED_PATH_PARTS),
            max_files=None if len(normalized_focus_paths) > 1 else remaining_total,
        )
        ordered_focus_paths = sorted(
            normalized_focus_paths,
            key=lambda path: (-len(path), path),
        )
        per_focus_counts: Counter[str] = Counter()
        for relative_path in _ordered_file_paths(candidate_file_paths):
            matched_focus_path = next(
                (
                    focus_path
                    for focus_path in ordered_focus_paths
                    if relative_path == focus_path or relative_path.startswith(f"{focus_path}/")
                ),
                None,
            )
            if matched_focus_path is None:
                continue
            if per_focus_counts[matched_focus_path] >= per_focus_limit:
                continue
            if relative_path in seen:
                continue
            seen.add(relative_path)
            collected.append(relative_path)
            per_focus_counts[matched_focus_path] += 1
            if len(collected) >= total_limit:
                return

    def _collect(focus_paths: list[str], remaining_files: int) -> None:
        if remaining_files <= 0:
            return
        candidate_file_paths = _probe_repository_file_paths(
            repo_path=repo_path,
            focus_paths=focus_paths,
            include_patterns=include_patterns,
            exclude_dirnames=set(repository_service._DEFAULT_EXCLUDED_PATH_PARTS),
            max_files=remaining_files,
        )
        for relative_path in _ordered_file_paths(candidate_file_paths):
            if relative_path in seen:
                continue
            seen.add(relative_path)
            collected.append(relative_path)
            if len(collected) >= max_files:
                return

    normalized_seed_paths = [
        repository_service._normalize_repository_relative_path(path)
        for path in seed_paths
        if str(path).strip()
    ]
    normalized_bridge_paths = [
        repository_service._normalize_repository_relative_path(path)
        for path in bridge_paths
        if str(path).strip()
    ]
    concrete_seed_paths = [
        path for path in normalized_seed_paths if path and _looks_like_concrete_file_seed(path)
    ]
    if normalized_seed_paths:
        seed_budget = min(
            max_files,
            max(
                len(concrete_seed_paths) * 12,
                len(normalized_seed_paths) * 6,
                min(64, max_files),
            ),
        )
        _collect(normalized_seed_paths, seed_budget)
    remaining_files = max_files - len(collected)
    if remaining_files > 0 and normalized_bridge_paths:
        bridge_path_count = len(normalized_bridge_paths)
        bridge_spread_limit = 0
        if bridge_path_count > 1:
            bridge_spread_limit = _bridge_root_spread_limit(
                remaining_files=remaining_files,
                bridge_path_count=bridge_path_count,
            )
            reserved_bridge_budget = min(
                remaining_files,
                bridge_spread_limit * bridge_path_count,
            )
            _collect_per_focus_path(
                normalized_bridge_paths,
                per_focus_limit=bridge_spread_limit,
                total_limit=len(collected) + reserved_bridge_budget,
            )
            remaining_files = max_files - len(collected)
        bridge_budget = min(
            remaining_files,
            max(min(96, max_files), min(256, max(max_files // 4, 1))),
        )
        if (
            bridge_budget > 0
            and bridge_path_count >= 24
            and _bridge_root_top_level_group_count(normalized_bridge_paths) >= 8
        ):
            distributed_bridge_limit = _bridge_root_spread_limit(
                remaining_files=bridge_budget,
                bridge_path_count=bridge_path_count,
            )
            distributed_bridge_budget = min(
                bridge_budget,
                distributed_bridge_limit * bridge_path_count,
            )
            _collect_per_focus_path(
                normalized_bridge_paths,
                per_focus_limit=distributed_bridge_limit,
                total_limit=len(collected) + distributed_bridge_budget,
            )
        else:
            _collect(normalized_bridge_paths, bridge_budget)
        remaining_files = max_files - len(collected)
    if remaining_files > 0 and len(collected) < min(32, max_files):
        fallback_budget = min(
            remaining_files,
            max(min(64, max_files), min(128, max(max_files // 8, 1))),
        )
        _collect([], fallback_budget)
    return collected


def _should_group_focus_path_scan(focus_paths: list[str]) -> bool:
    normalized_focus_paths = list(
        dict.fromkeys(
            repository_service._normalize_repository_relative_path(path)
            for path in focus_paths
            if str(path).strip()
        )
    )
    normalized_focus_paths = [path for path in normalized_focus_paths if path]
    focus_path_count = len(normalized_focus_paths)
    if focus_path_count < 2:
        return False

    def _is_source_root_focus_path(path: str) -> bool:
        if repository_service._is_test_path(path) or _is_non_operational_profile_path(path):
            return False
        parts = PurePosixPath(path).parts
        if not parts:
            return False
        basename = parts[-1].lower()
        if basename == "src" or basename.startswith("src-"):
            return True
        return (
            len(parts) >= 3
            and parts[-2].lower() == "main"
            and parts[-3].lower() == "src"
        )

    top_level_group_count = len(
        {
            PurePosixPath(path).parts[0]
            for path in normalized_focus_paths
            if PurePosixPath(path).parts
        }
    )
    if focus_path_count >= 24:
        return True
    if focus_path_count >= 20 and top_level_group_count <= 2:
        return True
    return focus_path_count >= 5 and all(
        _is_source_root_focus_path(path)
        for path in normalized_focus_paths
    )


def _should_use_seeded_profile_candidate_scan(
    *,
    seed_paths: list[str],
    bridge_paths: list[str],
) -> bool:
    normalized_seed_paths = [
        normalized_path
        for path in seed_paths
        if (
            normalized_path := repository_service._normalize_repository_relative_path(path)
        )
    ]
    if normalized_seed_paths:
        return True
    normalized_bridge_paths = [
        normalized_path
        for path in bridge_paths
        if (
            normalized_path := repository_service._normalize_repository_relative_path(path)
        )
    ]
    if not normalized_bridge_paths:
        return False
    top_level_group_count = len(
        {
            PurePosixPath(path).parts[0]
            for path in normalized_bridge_paths
            if PurePosixPath(path).parts
        }
    )
    return not (
        len(normalized_bridge_paths) <= 10
        and top_level_group_count > 2
    )


def _normalized_candidate_file_paths(
    *,
    repo_path: Path,
    candidate_file_paths: list[str],
    include_patterns: list[str],
    max_files: int,
) -> list[str]:
    normalized_paths: list[str] = []
    seen: set[str] = set()
    excluded_parts = set(repository_service._DEFAULT_EXCLUDED_PATH_PARTS)
    for raw_path in candidate_file_paths:
        normalized_path = repository_service._normalize_repository_relative_path(raw_path)
        if not normalized_path or normalized_path in seen:
            continue
        if any(part in excluded_parts for part in PurePosixPath(normalized_path).parts[:-1]):
            continue
        candidate = repo_path / normalized_path
        if not candidate.exists() or not candidate.is_file() or candidate.is_symlink():
            continue
        if include_patterns and not any(
            repository_service._matches_repository_pattern(normalized_path, pattern)
            for pattern in include_patterns
        ):
            continue
        seen.add(normalized_path)
        normalized_paths.append(normalized_path)
    ordered_paths = sorted(normalized_paths, key=_probe_collection_rank)
    return ordered_paths[:max_files]


def _looks_like_concrete_file_seed(path: str) -> bool:
    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return False
    basename = PurePosixPath(normalized_path).name
    if not basename:
        return False
    return bool(PurePosixPath(basename).suffix) or (
        basename in repository_service._TEXT_FILE_BASENAMES
    )


def _connected_map_candidate_file_limit(
    *,
    max_files: int,
    max_connected_files: int,
    concrete_seed_count: int,
) -> int:
    if concrete_seed_count >= 8:
        return min(max_files, max(256, max_connected_files))
    if concrete_seed_count >= 3:
        return min(max_files, max(320, max_connected_files + (max_connected_files // 2)))
    return min(max_files, max(800, max_connected_files * 4))


def _seed_dependency_files(
    *,
    candidate_file_paths: list[str],
    seed_paths: list[str],
    max_connected_files: int,
) -> list[str]:
    seeds: list[str] = []
    seen: set[str] = set()
    candidate_lookup = set(candidate_file_paths)
    for seed_path in seed_paths:
        normalized_seed = repository_service._normalize_repository_relative_path(seed_path)
        if not normalized_seed:
            continue
        if normalized_seed in candidate_lookup and normalized_seed not in seen:
            seen.add(normalized_seed)
            seeds.append(normalized_seed)
            continue
        scoped_matches = [
            file_path
            for file_path in candidate_file_paths
            if file_path == normalized_seed or file_path.startswith(f"{normalized_seed}/")
        ]
        for scoped_match in scoped_matches:
            if scoped_match in seen:
                continue
            seen.add(scoped_match)
            seeds.append(scoped_match)
            if len(seeds) >= max_connected_files:
                return seeds
    return seeds


def _safe_load_toml_dict(path: Path) -> dict[str, Any] | None:
    if tomllib is None:
        return None
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _candidate_existing_paths(
    repo_path: Path,
    *,
    paths: set[str],
) -> list[str]:
    existing_paths: list[str] = []
    for raw_path in sorted(paths):
        normalized_path = repository_service._normalize_repository_relative_path(raw_path)
        if not normalized_path:
            continue
        candidate = repo_path / normalized_path
        if candidate.is_file():
            existing_paths.append(normalized_path)
    return existing_paths


def _candidate_existing_roots(
    repo_path: Path,
    *,
    roots: set[str],
) -> list[str]:
    existing_roots: list[str] = []
    for raw_root in sorted(roots):
        normalized_root = repository_service._normalize_repository_relative_path(raw_root)
        if not normalized_root:
            continue
        candidate = repo_path / normalized_root
        if candidate.is_dir():
            existing_roots.append(normalized_root)
    return existing_roots


def _candidate_existing_leaf_roots(
    repo_path: Path,
    *,
    roots: set[str],
    entrypoint_paths: set[str] | None = None,
) -> list[str]:
    existing_roots = _candidate_existing_roots(repo_path, roots=roots)
    scannable_roots = _normalized_scannable_support_roots(existing_roots)
    if entrypoint_paths:
        scannable_roots = _prune_top_level_auxiliary_roots_without_entrypoints(
            support_roots=scannable_roots,
            entrypoint_paths=entrypoint_paths,
        )
    return sorted(scannable_roots)


def _normalized_scannable_support_roots(
    support_roots: list[str] | set[str],
) -> set[str]:
    normalized_support_roots = {
        normalized_root
        for root in support_roots
        if (
            normalized_root := repository_service._normalize_repository_relative_path(root)
        )
    }
    if not normalized_support_roots:
        return set()
    leaf_support_roots = _leaf_support_roots(normalized_support_roots)
    if not leaf_support_roots:
        return set()

    auxiliary_root_basenames = {"bin", "exe"}
    roots_by_parent: dict[str, list[str]] = {}
    for root in leaf_support_roots:
        parent = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(root).parent)
        )
        roots_by_parent.setdefault(parent or "", []).append(root)

    pruned_support_roots = set(leaf_support_roots)
    for sibling_roots in roots_by_parent.values():
        if not any(
            PurePosixPath(root).name.lower() not in auxiliary_root_basenames
            for root in sibling_roots
        ):
            continue
        for root in sibling_roots:
            if PurePosixPath(root).name.lower() in auxiliary_root_basenames:
                pruned_support_roots.discard(root)
    return pruned_support_roots or leaf_support_roots


def _prune_top_level_auxiliary_roots_without_entrypoints(
    *,
    support_roots: set[str],
    entrypoint_paths: set[str],
) -> set[str]:
    normalized_entrypoints = {
        normalized_path
        for path in entrypoint_paths
        if (
            normalized_path := repository_service._normalize_repository_relative_path(path)
        )
    }
    if not normalized_entrypoints:
        return set(support_roots)
    auxiliary_root_basenames = {"bin", "exe"}
    if not any(
        PurePosixPath(root).name.lower() not in auxiliary_root_basenames
        for root in support_roots
    ):
        return set(support_roots)

    pruned_support_roots = set(support_roots)
    for root in support_roots:
        root_parts = PurePosixPath(root).parts
        if len(root_parts) != 1:
            continue
        if root_parts[-1].lower() not in auxiliary_root_basenames:
            continue
        if any(
            entrypoint == root or entrypoint.startswith(f"{root}/")
            for entrypoint in normalized_entrypoints
        ):
            continue
        pruned_support_roots.discard(root)
    return pruned_support_roots or set(support_roots)


def _package_json_export_targets(value: Any) -> set[str]:
    targets: set[str] = set()
    if isinstance(value, str):
        targets.add(value)
        return targets
    if isinstance(value, list):
        for item in value:
            targets.update(_package_json_export_targets(item))
        return targets
    if isinstance(value, dict):
        for item in value.values():
            targets.update(_package_json_export_targets(item))
    return targets


def _package_json_profile_hints(
    repo_path: Path,
    package_json_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(package_json_path)
    if not normalized_path:
        return set(), set(), set()
    package_json = repository_service._safe_load_jsonc_dict(repo_path / normalized_path)
    if package_json is None:
        return set(), set(), set()
    package_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(package_dir) in {"", "."} else f"{package_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
    }
    entrypoint_paths: set[str] = set()
    config_paths = {normalized_path}

    def _add_target_entrypoint(raw_target: str) -> None:
        normalized_target = repository_service._normalize_repository_relative_path(
            str(package_dir / raw_target.strip())
        )
        if not normalized_target:
            return
        entrypoint_paths.add(normalized_target)
        target_parent = PurePosixPath(normalized_target).parent
        normalized_parent = repository_service._normalize_repository_relative_path(
            str(target_parent)
        )
        if normalized_parent:
            support_roots.add(normalized_parent)

    for field in ("main", "module", "browser", "types", "typings", "source"):
        raw_value = package_json.get(field)
        if isinstance(raw_value, str) and raw_value.strip():
            _add_target_entrypoint(raw_value)
    raw_bin = package_json.get("bin")
    if isinstance(raw_bin, str) and raw_bin.strip():
        _add_target_entrypoint(raw_bin)
    elif isinstance(raw_bin, dict):
        for raw_value in raw_bin.values():
            if isinstance(raw_value, str) and raw_value.strip():
                _add_target_entrypoint(raw_value)
    for export_target in _package_json_export_targets(package_json.get("exports")):
        if export_target.strip().startswith("."):
            _add_target_entrypoint(export_target)
    scripts = package_json.get("scripts")
    if isinstance(scripts, dict):
        script_text = " ".join(
            str(value) for value in scripts.values() if isinstance(value, str) and value.strip()
        ).lower()
        frontend_tokens = ("vite", "react-scripts", "next", "nuxt", "astro", "vue-cli-service")
        if any(token in script_text for token in frontend_tokens):
            support_roots.update(
                f"{root_prefix}{name}" for name in ("app", "components", "composables", "layouts", "pages", "routes", "client", "views")
            )
            entrypoint_paths.update(
                {
                    f"{root_prefix}src/main.tsx",
                    f"{root_prefix}src/main.jsx",
                    f"{root_prefix}src/main.ts",
                    f"{root_prefix}src/main.js",
                    f"{root_prefix}src/index.tsx",
                    f"{root_prefix}src/index.jsx",
                    f"{root_prefix}src/index.ts",
                    f"{root_prefix}src/index.js",
                    f"{root_prefix}src/App.tsx",
                    f"{root_prefix}src/App.jsx",
                    f"{root_prefix}src/App.vue",
                    f"{root_prefix}src/app.vue",
                    f"{root_prefix}src/app/page.tsx",
                    f"{root_prefix}src/pages/Index.tsx",
                    f"{root_prefix}src/pages/index.vue",
                    f"{root_prefix}pages/index.vue",
                }
            )
        if any(token in script_text for token in ("node", "tsx", "ts-node", "nodemon")):
            support_roots.update(
                f"{root_prefix}{name}" for name in ("server", "routes", "client")
            )
            entrypoint_paths.update(
                {
                    f"{root_prefix}src/main.ts",
                    f"{root_prefix}src/index.ts",
                    f"{root_prefix}src/server.ts",
                    f"{root_prefix}src/server.js",
                    f"{root_prefix}server.ts",
                    f"{root_prefix}server.js",
                }
            )
    return entrypoint_paths, support_roots, config_paths


def _tsconfig_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(config_path)
    if not normalized_path:
        return set(), set(), set()
    config_payload = repository_service._safe_load_jsonc_dict(repo_path / normalized_path)
    compiler_options = repository_service._resolved_tsconfig_compiler_options(
        root_path=repo_path,
        config_file_path=normalized_path,
    )
    config_dir = PurePosixPath(normalized_path).parent
    support_roots = {
        repository_service._normalize_repository_relative_path(str(config_dir)) or "",
    }
    entrypoint_paths: set[str] = set()
    config_paths = {normalized_path}
    base_url = compiler_options.get("baseUrl")
    if isinstance(base_url, str) and base_url.strip():
        support_roots.add(
            repository_service._normalize_repository_relative_pattern(
                str(config_dir / base_url.strip())
            )
        )
    raw_paths = compiler_options.get("paths")
    if isinstance(raw_paths, dict):
        for targets in raw_paths.values():
            target_values = targets if isinstance(targets, list) else [targets]
            for raw_target in target_values:
                if not isinstance(raw_target, str) or not raw_target.strip():
                    continue
                resolved_target = repository_service._normalize_repository_relative_pattern(
                    str(config_dir / raw_target.strip())
                )
                if not resolved_target:
                    continue
                support_roots.add(resolved_target.split("*", 1)[0].rstrip("/"))
    include_values = config_payload.get("include") if isinstance(config_payload, dict) else None
    if isinstance(include_values, list):
        for item in include_values:
            if not isinstance(item, str) or not item.strip():
                continue
            support_roots.add(
                repository_service._normalize_repository_relative_pattern(
                    str(config_dir / item.strip())
                ).split("*", 1)[0].rstrip("/")
            )
    entrypoint_paths.update(
        {
            str(config_dir / "src/main.ts"),
            str(config_dir / "src/main.tsx"),
            str(config_dir / "src/index.ts"),
            str(config_dir / "src/index.tsx"),
            str(config_dir / "src/App.tsx"),
            str(config_dir / "src/app/page.tsx"),
        }
    )
    return entrypoint_paths, support_roots, config_paths


def _pyproject_profile_hints(
    repo_path: Path,
    pyproject_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(pyproject_path)
    if not normalized_path:
        return set(), set(), set()
    payload = _safe_load_toml_dict(repo_path / normalized_path)
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}app",
    }
    entrypoint_paths = {
        f"{root_prefix}main.py",
        f"{root_prefix}app.py",
        f"{root_prefix}manage.py",
        f"{root_prefix}src/main.py",
        f"{root_prefix}src/__main__.py",
    }
    config_paths = {normalized_path}
    if not isinstance(payload, dict):
        return entrypoint_paths, support_roots, config_paths
    project = payload.get("project")
    if isinstance(project, dict):
        scripts = project.get("scripts")
        if isinstance(scripts, dict):
            for value in scripts.values():
                if not isinstance(value, str) or not value.strip():
                    continue
                module_name = value.split(":", 1)[0].strip()
                if not module_name:
                    continue
                entrypoint_paths.add(f"{root_prefix}{module_name.replace('.', '/')}.py")
                entrypoint_paths.add(f"{root_prefix}src/{module_name.replace('.', '/')}.py")
    return entrypoint_paths, support_roots, config_paths


def _pubspec_profile_hints(
    repo_path: Path,
    pubspec_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(pubspec_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}lib",
        f"{root_prefix}bin",
        f"{root_prefix}tool",
    }
    entrypoint_paths = {
        f"{root_prefix}lib/main.dart",
        f"{root_prefix}bin/main.dart",
    }
    config_paths = {normalized_path}
    package_name = repository_service._read_dart_pubspec_name(repo_path / normalized_path)
    if not package_name:
        return entrypoint_paths, support_roots, config_paths
    for candidate_name in {package_name, package_name.replace("-", "_")}:
        if not candidate_name:
            continue
        entrypoint_paths.add(f"{root_prefix}lib/{candidate_name}.dart")
        entrypoint_paths.add(f"{root_prefix}bin/{candidate_name}.dart")
    return entrypoint_paths, support_roots, config_paths


def _yaml_path_field_values(text: str, field_name: str) -> tuple[str, ...]:
    values: list[str] = []
    lines = text.splitlines()
    for index, raw_line in enumerate(lines):
        stripped_line = raw_line.strip()
        if not stripped_line.startswith(f"{field_name}:"):
            continue
        after_colon = stripped_line[len(field_name) + 1 :].strip()
        if after_colon.startswith("[") and "]" in after_colon:
            body = after_colon[1 : after_colon.index("]")]
            inline_values = [
                str(match.group("value") or "").strip()
                for match in _QUOTED_SEGMENT_RE.finditer(body)
            ]
            if not inline_values:
                inline_values = [
                    segment.strip().strip("'\"")
                    for segment in body.split(",")
                    if segment.strip()
                ]
            values.extend(value for value in inline_values if value)
            continue
        if after_colon and not after_colon.startswith("#"):
            scalar_value = after_colon.split("#", 1)[0].strip().strip("'\"")
            if scalar_value:
                values.append(scalar_value)
            continue
        base_indent = len(raw_line) - len(raw_line.lstrip(" "))
        for subline in lines[index + 1 :]:
            if not subline.strip():
                continue
            current_indent = len(subline) - len(subline.lstrip(" "))
            if current_indent <= base_indent:
                break
            stripped_subline = subline.strip()
            if not stripped_subline.startswith("-"):
                continue
            raw_value = stripped_subline[1:].strip().split("#", 1)[0].strip().strip("'\"")
            if raw_value:
                values.append(raw_value)
    return tuple(dict.fromkeys(value for value in values if value))


def _dbt_project_profile_hints(
    repo_path: Path,
    dbt_project_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(dbt_project_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    config_paths = {normalized_path}
    try:
        text = (repo_path / normalized_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""

    model_roots = _yaml_path_field_values(text, "model-paths") or ("models",)
    analysis_roots = _yaml_path_field_values(text, "analysis-paths") or ("analyses",)
    snapshot_roots = _yaml_path_field_values(text, "snapshot-paths") or ("snapshots",)
    support_roots = {root_prefix.rstrip("/")}
    entrypoint_paths: set[str] = set()

    for raw_root in (*model_roots, *analysis_roots, *snapshot_roots):
        normalized_root = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_root)
        )
        if normalized_root:
            support_roots.add(normalized_root)

    for raw_root in (*model_roots, *analysis_roots, *snapshot_roots):
        candidate_root = repo_path / project_dir / raw_root
        if not candidate_root.is_dir():
            continue
        try:
            sql_files = sorted(candidate_root.rglob("*.sql"))
        except OSError:
            sql_files = []
        for candidate_path in sql_files:
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate_path.relative_to(repo_path))
            )
            if (
                relative_path
                and not repository_service._is_test_path(relative_path)
                and not _is_non_operational_profile_path(relative_path)
            ):
                entrypoint_paths.add(relative_path)

    return entrypoint_paths, support_roots, config_paths


def _cargo_profile_hints(
    repo_path: Path,
    cargo_toml_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(cargo_toml_path)
    if not normalized_path:
        return set(), set(), set()
    payload = _safe_load_toml_dict(repo_path / normalized_path)
    cargo_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(cargo_dir) in {"", "."} else f"{cargo_dir}/"
    support_roots = {root_prefix.rstrip("/"), f"{root_prefix}src", f"{root_prefix}bin"}
    entrypoint_paths = {f"{root_prefix}src/main.rs", f"{root_prefix}src/lib.rs"}
    config_paths = {normalized_path}
    if not isinstance(payload, dict):
        return entrypoint_paths, support_roots, config_paths
    lib_payload = payload.get("lib")
    if isinstance(lib_payload, dict):
        lib_path = lib_payload.get("path")
        if isinstance(lib_path, str) and lib_path.strip():
            entrypoint_paths.add(str(cargo_dir / lib_path.strip()))
    bin_payload = payload.get("bin")
    if isinstance(bin_payload, list):
        for entry in bin_payload:
            if not isinstance(entry, dict):
                continue
            bin_path = entry.get("path")
            if isinstance(bin_path, str) and bin_path.strip():
                entrypoint_paths.add(str(cargo_dir / bin_path.strip()))
    return entrypoint_paths, support_roots, config_paths


def _fortran_fpm_profile_hints(
    repo_path: Path,
    fpm_toml_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(fpm_toml_path)
    if not normalized_path:
        return set(), set(), set()
    payload = _safe_load_toml_dict(repo_path / normalized_path)
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {root_prefix.rstrip("/"), f"{root_prefix}src", f"{root_prefix}app"}
    entrypoint_paths = {
        f"{root_prefix}src/main.f90",
        f"{root_prefix}src/main.f95",
        f"{root_prefix}src/main.f03",
        f"{root_prefix}src/main.f08",
        f"{root_prefix}src/main.f",
        f"{root_prefix}app/main.f90",
        f"{root_prefix}app/main.f95",
        f"{root_prefix}app/main.f03",
        f"{root_prefix}app/main.f08",
        f"{root_prefix}app/main.f",
    }
    config_paths = {normalized_path}
    package_name = payload.get("name") if isinstance(payload, dict) else None
    if isinstance(package_name, str) and package_name.strip():
        normalized_name = re.sub(r"[^a-z0-9_]+", "_", package_name.lower()).strip("_")
        if normalized_name:
            for suffix in (".f90", ".f95", ".f03", ".f08", ".f", ".for"):
                entrypoint_paths.add(f"{root_prefix}src/{normalized_name}{suffix}")
                entrypoint_paths.add(f"{root_prefix}app/{normalized_name}{suffix}")
    return entrypoint_paths, support_roots, config_paths


def _pascal_project_profile_hints(
    project_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(project_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    if _is_non_operational_project_path(str(project_dir)):
        return set(), set(), {normalized_path}
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    stem = PurePosixPath(normalized_path).stem
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}source",
        f"{root_prefix}lib",
        f"{root_prefix}units",
    }
    entrypoint_paths = {
        f"{root_prefix}{stem}.pas",
        f"{root_prefix}{stem}.pp",
        f"{root_prefix}{stem}.lpr",
        f"{root_prefix}{stem}.dpr",
        f"{root_prefix}{stem}.dpk",
        f"{root_prefix}main.lpr",
        f"{root_prefix}main.dpr",
        f"{root_prefix}program.lpr",
        f"{root_prefix}program.dpr",
        f"{root_prefix}src/{stem}.pas",
        f"{root_prefix}src/{stem}.pp",
        f"{root_prefix}source/{stem}.pas",
        f"{root_prefix}source/{stem}.pp",
    }
    return entrypoint_paths, support_roots, {normalized_path}


def _delphi_profile_hints(
    repo_path: Path,
    project_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(project_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    if _is_non_operational_project_path(str(project_dir)):
        return set(), set(), {normalized_path}
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    stem = PurePosixPath(normalized_path).stem
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}source",
        f"{root_prefix}src",
        f"{root_prefix}packages",
        f"{root_prefix}runtime",
        f"{root_prefix}design",
    }
    entrypoint_paths = {
        f"{root_prefix}{stem}.dpr",
        f"{root_prefix}{stem}.dpk",
        f"{root_prefix}{stem}.pas",
        f"{root_prefix}main.dpr",
        f"{root_prefix}main.pas",
        f"{root_prefix}source/{stem}.pas",
        f"{root_prefix}src/{stem}.pas",
    }
    manifest_path = repo_path / normalized_path
    try:
        text = manifest_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    for match in re.finditer(
        r"<MainSource>\s*(?P<path>[^<]+?)\s*</MainSource>",
        text,
        flags=re.IGNORECASE,
    ):
        resolved_path = repository_service._normalize_repository_relative_path(
            str(project_dir / str(match.group("path") or "").strip())
        )
        if resolved_path:
            entrypoint_paths.add(resolved_path)
    return entrypoint_paths, support_roots, {normalized_path}


def _tsql_profile_hints(
    repo_path: Path,
    project_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(project_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    if _is_non_operational_project_path(str(project_dir)):
        return set(), set(), {normalized_path}
    project_root = repo_path / project_dir
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {root_prefix.rstrip("/")}
    entrypoint_paths: set[str] = set()
    manifest_path = repo_path / normalized_path
    try:
        text = manifest_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    for included_path in repository_service.tsql_adapter.project_included_paths(
        text=text,
        project_file_path=normalized_path,
    ):
        if (
            included_path
            and not repository_service._is_test_path(included_path)
            and not _is_non_operational_profile_path(included_path)
        ):
            entrypoint_paths.add(included_path)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(included_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    for folder_path in repository_service.tsql_adapter.project_folder_paths(
        text=text,
        project_file_path=normalized_path,
    ):
        if folder_path and not _is_non_operational_profile_path(folder_path):
            support_roots.add(folder_path)
    if project_root.is_dir():
        for child in sorted(project_root.iterdir()):
            if not child.is_dir():
                continue
            relative_child = repository_service._normalize_repository_relative_path(
                str(child.relative_to(repo_path))
            )
            if (
                relative_child
                and not _is_non_operational_profile_path(relative_child)
                and repository_service.tsql_adapter.has_tsql_path_hints(child)
            ):
                support_roots.add(relative_child)
        if not entrypoint_paths:
            for candidate in sorted(project_root.rglob("*.sql")):
                if not candidate.is_file() or candidate.is_symlink():
                    continue
                relative_path = repository_service._normalize_repository_relative_path(
                    str(candidate.relative_to(repo_path))
                )
                if (
                    not relative_path
                    or repository_service._is_test_path(relative_path)
                    or _is_non_operational_profile_path(relative_path)
                    or _probe_language_for_path(relative_path, repo_path=repo_path) != "tsql"
                ):
                    continue
                entrypoint_paths.add(relative_path)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(relative_path).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
    return entrypoint_paths, support_roots, {normalized_path}


def _normalized_ada_unit_stem(raw_name: str | None) -> str | None:
    if not isinstance(raw_name, str) or not raw_name.strip():
        return None
    normalized_name = re.sub(r"[^a-z0-9]+", "-", raw_name.lower()).strip("-")
    return normalized_name or None


def _ada_project_quoted_values(text: str, field: str) -> tuple[str, ...]:
    values: list[str] = []
    for match in _ADA_PROJECT_FIELD_RE.finditer(text):
        current_field = str(match.group("field") or "").strip().lower()
        if current_field != field.lower():
            continue
        values.extend(
            segment.group("value")
            for segment in _QUOTED_SEGMENT_RE.finditer(str(match.group("body") or ""))
        )
    return tuple(dict.fromkeys(value.strip() for value in values if value.strip()))


def _ada_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(config_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_path = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    if _is_non_operational_project_path(str(project_dir)):
        return set(), set(), {normalized_path}
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}source",
        f"{root_prefix}ada",
        f"{root_prefix}lib",
    }
    entrypoint_paths = {
        f"{root_prefix}main.adb",
        f"{root_prefix}src/main.adb",
        f"{root_prefix}source/main.adb",
        f"{root_prefix}ada/main.adb",
    }
    config_paths = {normalized_path}
    unit_stems: set[str] = set()

    if manifest_path.name.lower() == "alire.toml":
        if tomllib is not None:
            try:
                payload = tomllib.loads(manifest_path.read_text(encoding="utf-8", errors="replace"))
            except (OSError, tomllib.TOMLDecodeError):
                payload = {}
        else:
            payload = {}
        if isinstance(payload, dict):
            normalized_name = _normalized_ada_unit_stem(payload.get("name"))
            if normalized_name:
                unit_stems.add(normalized_name)
            raw_executables = payload.get("executables")
            if isinstance(raw_executables, list):
                for executable in raw_executables:
                    normalized_executable = _normalized_ada_unit_stem(executable)
                    if normalized_executable:
                        unit_stems.add(normalized_executable)
            raw_project_files = payload.get("project-files")
            if isinstance(raw_project_files, list):
                for project_file in raw_project_files:
                    if not isinstance(project_file, str) or not project_file.strip():
                        continue
                    resolved_project_path = repository_service._normalize_repository_relative_path(
                        str(project_dir / project_file.strip())
                    )
                    if resolved_project_path and (repo_path / resolved_project_path).is_file():
                        config_paths.add(resolved_project_path)
    else:
        try:
            project_text = manifest_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            project_text = ""
        for raw_source_dir in _ada_project_quoted_values(project_text, "source_dirs"):
            normalized_root = repository_service._normalize_repository_relative_path(
                str(project_dir / raw_source_dir)
            )
            if normalized_root:
                support_roots.add(normalized_root)
        for raw_main_file in _ada_project_quoted_values(project_text, "main"):
            normalized_main_path = repository_service._normalize_repository_relative_path(
                str(project_dir / raw_main_file)
            )
            if normalized_main_path:
                entrypoint_paths.add(normalized_main_path)
        for raw_source_file in _ada_project_quoted_values(project_text, "source_files"):
            normalized_source_path = repository_service._normalize_repository_relative_path(
                str(project_dir / raw_source_file)
            )
            if normalized_source_path:
                entrypoint_paths.add(normalized_source_path)
        normalized_name = _normalized_ada_unit_stem(PurePosixPath(normalized_path).stem)
        if normalized_name:
            unit_stems.add(normalized_name)

    for support_root in tuple(sorted(support_roots)):
        normalized_support_root = repository_service._normalize_repository_relative_path(
            support_root
        )
        if not normalized_support_root:
            continue
        support_roots.add(normalized_support_root)
        for unit_stem in unit_stems:
            entrypoint_paths.add(f"{normalized_support_root}/{unit_stem}.adb")
            entrypoint_paths.add(f"{normalized_support_root}/{unit_stem}.ads")
            entrypoint_paths.add(f"{normalized_support_root}/{unit_stem}.ada")

    return entrypoint_paths, support_roots, config_paths


def _dub_sdl_quoted_values(text: str, key: str) -> tuple[str, ...]:
    values: list[str] = []
    for raw_line in text.splitlines():
        stripped_line = raw_line.strip()
        if not stripped_line or stripped_line.startswith("//"):
            continue
        if not stripped_line.startswith(f"{key} "):
            continue
        values.extend(match.group(1) for match in re.finditer(r'"([^"]+)"', stripped_line))
    return tuple(values)


def _normalized_d_package_name(raw_name: str | None) -> str | None:
    if not isinstance(raw_name, str) or not raw_name.strip():
        return None
    normalized_name = re.sub(r"[^a-z0-9_]+", "_", raw_name.lower()).strip("_")
    return normalized_name or None


def _dub_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(config_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_path = repo_path / normalized_path
    package_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(package_dir) in {"", "."} else f"{package_dir}/"
    config_paths = {normalized_path}
    package_name: str | None = None
    source_roots: set[str] = set()
    configuration_names: set[str] = set()

    if manifest_path.name == "dub.json":
        payload = repository_service._safe_load_jsonc_dict(manifest_path)
        if payload is None:
            return set(), set(), set()
        package_name = payload.get("name") if isinstance(payload.get("name"), str) else None
        for field in ("sourcePaths", "importPaths"):
            raw_value = payload.get(field)
            raw_values = raw_value if isinstance(raw_value, list) else [raw_value]
            for item in raw_values:
                if isinstance(item, str) and item.strip():
                    normalized_root = repository_service._normalize_repository_relative_path(
                        str(package_dir / item.strip())
                    )
                    if normalized_root:
                        source_roots.add(normalized_root)
        raw_configurations = payload.get("configurations")
        if isinstance(raw_configurations, list):
            for entry in raw_configurations:
                if not isinstance(entry, dict):
                    continue
                for field in ("name", "targetName"):
                    raw_value = entry.get(field)
                    if isinstance(raw_value, str) and raw_value.strip():
                        configuration_names.add(raw_value.strip())
        raw_subpackages = payload.get("subPackages")
        if isinstance(raw_subpackages, list):
            for raw_value in raw_subpackages:
                if not isinstance(raw_value, str) or not raw_value.strip():
                    continue
                subpackage_dir = repository_service._normalize_repository_relative_path(
                    str(package_dir / raw_value.strip())
                )
                if not subpackage_dir:
                    continue
                for manifest_name in ("dub.json", "dub.sdl"):
                    candidate_manifest = repository_service._normalize_repository_relative_path(
                        f"{subpackage_dir}/{manifest_name}"
                    )
                    if candidate_manifest and (repo_path / candidate_manifest).is_file():
                        config_paths.add(candidate_manifest)
                for candidate_root in ("src", "source"):
                    normalized_root = repository_service._normalize_repository_relative_path(
                        f"{subpackage_dir}/{candidate_root}"
                    )
                    if normalized_root:
                        source_roots.add(normalized_root)
    else:
        try:
            sdl_text = manifest_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return set(), set(), set()
        package_name = next(iter(_dub_sdl_quoted_values(sdl_text, "name")), None)
        for field in ("sourcePaths", "importPaths"):
            for raw_value in _dub_sdl_quoted_values(sdl_text, field):
                normalized_root = repository_service._normalize_repository_relative_path(
                    str(package_dir / raw_value.strip())
                )
                if normalized_root:
                    source_roots.add(normalized_root)
        configuration_names.update(_dub_sdl_quoted_values(sdl_text, "targetName"))

    if not source_roots:
        for candidate_root in ("src", "source"):
            normalized_root = repository_service._normalize_repository_relative_path(
                f"{root_prefix}{candidate_root}"
            )
            if normalized_root:
                source_roots.add(normalized_root)

    support_roots = set(source_roots)
    entrypoint_paths: set[str] = set()
    normalized_name = _normalized_d_package_name(package_name)
    for source_root in sorted(source_roots):
        entrypoint_paths.add(f"{source_root}/main.d")
        entrypoint_paths.add(f"{source_root}/app.d")
        if normalized_name:
            entrypoint_paths.add(f"{source_root}/{normalized_name}.d")
            entrypoint_paths.add(f"{source_root}/{normalized_name}/main.d")
            entrypoint_paths.add(f"{source_root}/{normalized_name}/{normalized_name}.d")
        for configuration_name in sorted(configuration_names):
            normalized_configuration = _normalized_d_package_name(configuration_name)
            if not normalized_configuration:
                continue
            entrypoint_paths.add(f"{source_root}/{normalized_configuration}.d")
            entrypoint_paths.add(f"{source_root}/{normalized_configuration}/main.d")
            if normalized_name:
                entrypoint_paths.add(f"{source_root}/{normalized_name}/{normalized_configuration}.d")
                entrypoint_paths.add(
                    f"{source_root}/{normalized_name}/{normalized_configuration}/main.d"
                )
    return entrypoint_paths, support_roots, config_paths


def _go_module_profile_hints(go_mod_path: str) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(go_mod_path)
    if not normalized_path:
        return set(), set(), set()
    module_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(module_dir) in {"", "."} else f"{module_dir}/"
    support_roots = {root_prefix.rstrip("/"), f"{root_prefix}cmd", f"{root_prefix}internal"}
    entrypoint_paths = {f"{root_prefix}main.go"}
    config_paths = {normalized_path}
    return entrypoint_paths, support_roots, config_paths


def _candidate_clojure_module_paths(
    *,
    project_dir: PurePosixPath,
    source_dir: str,
    module_name: str,
) -> tuple[str, ...]:
    normalized_module = module_name.strip()
    if not normalized_module:
        return ()
    source_prefix = repository_service._normalize_repository_relative_path(
        str(project_dir / source_dir)
    )
    module_path = "/".join(segment.replace("-", "_") for segment in normalized_module.split("."))
    candidate_paths: list[str] = []
    for extension in (".clj", ".cljc", ".cljs"):
        relative_candidate = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(source_prefix or "") / f"{module_path}{extension}")
        )
        if relative_candidate:
            candidate_paths.append(relative_candidate)
    return tuple(dict.fromkeys(candidate_paths))


def _collect_clojure_vector_field_values(
    text: str,
    *,
    field_names: set[str],
) -> dict[str, list[str]]:
    values_by_field = {field_name: [] for field_name in field_names}
    for match in _CLOJURE_VECTOR_FIELD_RE.finditer(text):
        field_name = match.group("field").lstrip(":").lower()
        if field_name not in values_by_field:
            continue
        values_by_field[field_name].extend(
            quoted_match.group("value").strip()
            for quoted_match in _CLOJURE_QUOTED_STRING_RE.finditer(match.group("body"))
            if quoted_match.group("value").strip()
        )
    return values_by_field


def _clojure_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}src/main/clojure",
        f"{root_prefix}src/clj",
        f"{root_prefix}src/cljc",
        f"{root_prefix}src/cljs",
        f"{root_prefix}lib",
    }
    entrypoint_paths = {
        f"{root_prefix}src/core.clj",
        f"{root_prefix}src/main.clj",
        f"{root_prefix}src/main/clojure/core.clj",
        f"{root_prefix}src/main/clojure/main.clj",
        f"{root_prefix}src/clj/core.clj",
        f"{root_prefix}src/cljc/core.cljc",
        f"{root_prefix}src/cljs/core.cljs",
    }
    config_paths = {normalized_path}
    try:
        text = (repo_path / normalized_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return entrypoint_paths, support_roots, config_paths
    field_values = _collect_clojure_vector_field_values(
        text,
        field_names={"paths", "source-paths", "src-dirs"},
    )
    raw_source_dirs = [
        source_dir
        for source_dir in (
            field_values["paths"] + field_values["source-paths"] + field_values["src-dirs"]
        )
        if source_dir and not _is_non_operational_profile_path(source_dir)
    ] or ["src"]
    for source_dir in raw_source_dirs:
        normalized_source_dir = repository_service._normalize_repository_relative_path(
            str(project_dir / source_dir)
        )
        if normalized_source_dir and not _is_non_operational_profile_path(normalized_source_dir):
            support_roots.add(normalized_source_dir)
    for match in _CLOJURE_MAIN_RE.finditer(text):
        main_target = match.group("target").strip()
        if not main_target:
            continue
        for source_dir in raw_source_dirs:
            entrypoint_paths.update(
                _candidate_clojure_module_paths(
                    project_dir=project_dir,
                    source_dir=source_dir,
                    module_name=main_target,
                )
            )
    return entrypoint_paths, support_roots, config_paths


def _pom_profile_hints(pom_xml_path: str) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(pom_xml_path)
    if not normalized_path:
        return set(), set(), set()
    pom_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(pom_dir) in {"", "."} else f"{pom_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}src/main/java",
        f"{root_prefix}src/main/kotlin",
    }
    entrypoint_paths = {
        f"{root_prefix}src/main/java/Application.java",
        f"{root_prefix}src/main/java/Main.java",
        f"{root_prefix}src/main/kotlin/Application.kt",
        f"{root_prefix}src/main/kotlin/Main.kt",
    }
    config_paths = {normalized_path}
    return entrypoint_paths, support_roots, config_paths


def _normalize_gradle_project_root(project_name: str) -> str:
    normalized = project_name.strip().strip(":")
    if not normalized:
        return ""
    return normalized.replace(":", "/")


def _gradle_project_root_hints(project_root: str) -> tuple[set[str], set[str]]:
    root_prefix = "" if project_root in {"", "."} else f"{project_root}/"
    support_roots = {
        f"{root_prefix}src/main/java",
        f"{root_prefix}src/main/groovy",
        f"{root_prefix}src/main/kotlin",
    }
    entrypoint_paths = {
        f"{root_prefix}src/main/java/Application.java",
        f"{root_prefix}src/main/java/Main.java",
        f"{root_prefix}src/main/groovy/Application.groovy",
        f"{root_prefix}src/main/groovy/Main.groovy",
        f"{root_prefix}src/main/kotlin/Application.kt",
        f"{root_prefix}src/main/kotlin/Main.kt",
    }
    return entrypoint_paths, support_roots


def _iter_gradle_included_project_roots(text: str) -> tuple[str, ...]:
    project_roots: set[str] = set()
    lines = text.splitlines()
    line_index = 0
    while line_index < len(lines):
        stripped_line = lines[line_index].strip()
        if not (
            stripped_line == "include"
            or stripped_line.startswith("include ")
            or stripped_line.startswith("include(")
        ):
            line_index += 1
            continue
        block_lines = [stripped_line]
        line_index += 1
        while line_index < len(lines):
            continuation = lines[line_index].strip()
            if not continuation:
                break
            if continuation.startswith(("'", '"')) or continuation.startswith(","):
                block_lines.append(continuation)
                line_index += 1
                continue
            break
        block_text = " ".join(block_lines)
        for match in _QUOTED_SEGMENT_RE.finditer(block_text):
            normalized_root = _normalize_gradle_project_root(str(match.group("value") or ""))
            if normalized_root:
                project_roots.add(normalized_root)
    return tuple(sorted(project_roots))


def _gradle_profile_hints(
    repo_path: Path,
    gradle_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(gradle_path)
    if not normalized_path:
        return set(), set(), set()
    gradle_dir = PurePosixPath(normalized_path).parent
    project_root = "" if str(gradle_dir) in {"", "."} else str(gradle_dir)
    entrypoint_paths, support_roots = _gradle_project_root_hints(project_root)
    config_paths = {normalized_path}

    gradle_name = PurePosixPath(normalized_path).name.lower()
    if gradle_name not in {"settings.gradle", "settings.gradle.kts"}:
        return entrypoint_paths, support_roots, config_paths

    settings_path = repo_path / normalized_path
    if not settings_path.is_file():
        return entrypoint_paths, support_roots, config_paths

    settings_text = settings_path.read_text(encoding="utf-8", errors="replace")
    for included_root in _iter_gradle_included_project_roots(settings_text):
        included_entrypoints, included_support_roots = _gradle_project_root_hints(included_root)
        entrypoint_paths.update(included_entrypoints)
        support_roots.update(included_support_roots)
    return entrypoint_paths, support_roots, config_paths


def _cmake_like_profile_hints(
    *,
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}include",
        f"{root_prefix}src",
        f"{root_prefix}source",
        f"{root_prefix}sources",
        f"{root_prefix}lib",
        f"{root_prefix}libs",
    }
    entrypoint_paths = {
        f"{root_prefix}main.c",
        f"{root_prefix}main.cc",
        f"{root_prefix}main.cpp",
        f"{root_prefix}main.cxx",
        f"{root_prefix}main.m",
        f"{root_prefix}main.mm",
        f"{root_prefix}src/main.c",
        f"{root_prefix}src/main.cc",
        f"{root_prefix}src/main.cpp",
        f"{root_prefix}src/main.cxx",
        f"{root_prefix}src/main.m",
        f"{root_prefix}src/main.mm",
    }
    config_paths = {normalized_path}
    try:
        text = manifest.read_text(encoding="utf-8")
    except OSError:
        return entrypoint_paths, support_roots, config_paths
    for match in _C_FAMILY_SOURCE_TOKEN_RE.finditer(text):
        raw_path = match.group("path").strip()
        if not raw_path or raw_path.startswith(("$", "/")):
            continue
        resolved_path = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(project_dir) / raw_path)
        )
        if not resolved_path or resolved_path.startswith("/"):
            continue
        entrypoint_paths.add(resolved_path)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, support_roots, config_paths


def _c_family_manifest_ecosystems(
    *,
    repo_path: Path,
    manifest_path: str,
) -> set[str]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return {"cpp"}
    manifest = repo_path / normalized_path
    try:
        text = manifest.read_text(encoding="utf-8")
    except OSError:
        return {"cpp"}

    manifest_ecosystems: set[str] = set()
    for match in _C_FAMILY_SOURCE_TOKEN_RE.finditer(text):
        suffix = PurePosixPath(str(match.group("path") or "").strip()).suffix.lower()
        if suffix == ".c":
            manifest_ecosystems.add("c")
        elif suffix in {".cc", ".cpp", ".cxx"}:
            manifest_ecosystems.add("cpp")
        elif suffix in {".vala", ".vapi"}:
            manifest_ecosystems.add("vala")
    if "vala" not in manifest_ecosystems:
        project_dir = PurePosixPath(normalized_path).parent
        for candidate_root in (
            repo_path / project_dir,
            repo_path / project_dir / "src",
            repo_path / project_dir / "lib",
        ):
            if not candidate_root.is_dir():
                continue
            try:
                has_vala_sources = any(candidate_root.rglob("*.vala")) or any(
                    candidate_root.rglob("*.vapi")
                )
            except OSError:
                continue
            if has_vala_sources:
                manifest_ecosystems.add("vala")
                break
    return manifest_ecosystems or {"cpp"}


def _cmake_profile_hints(
    repo_path: Path,
    cmake_path: str,
) -> tuple[set[str], set[str], set[str]]:
    return _cmake_like_profile_hints(repo_path=repo_path, manifest_path=cmake_path)


def _profile_root_from_glob_pattern(
    *,
    project_dir: PurePosixPath,
    raw_pattern: str,
) -> str | None:
    normalized_pattern = str(raw_pattern or "").strip().replace("\\", "/")
    if not normalized_pattern or normalized_pattern.startswith(("http://", "https://", "$")):
        return None
    normalized_pattern = normalized_pattern.split("{", 1)[0]
    for delimiter in ("**", "*", "[", "?"):
        if delimiter in normalized_pattern:
            normalized_pattern = normalized_pattern.split(delimiter, 1)[0]
            break
    normalized_pattern = normalized_pattern.rstrip("/")
    resolved_root = repository_service._normalize_repository_relative_path(
        str(project_dir / normalized_pattern)
    )
    if resolved_root:
        return resolved_root
    project_root = repository_service._normalize_repository_relative_path(str(project_dir))
    return project_root or None


def _podspec_profile_hints(
    repo_path: Path,
    podspec_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(podspec_path)
    if not normalized_path:
        return set(), set(), set()
    podspec = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}Classes",
        f"{root_prefix}Sources",
        f"{root_prefix}Source",
        f"{root_prefix}src",
        f"{root_prefix}include",
    }
    entrypoint_paths = {
        f"{root_prefix}main.m",
        f"{root_prefix}main.mm",
        f"{root_prefix}src/main.m",
        f"{root_prefix}src/main.mm",
        f"{root_prefix}Sources/main.m",
        f"{root_prefix}Sources/main.mm",
    }
    config_paths = {normalized_path}
    try:
        text = podspec.read_text(encoding="utf-8")
    except OSError:
        return entrypoint_paths, support_roots, config_paths
    for match in _QUOTED_SEGMENT_RE.finditer(text):
        raw_pattern = str(match.group("value") or "").strip()
        lower_pattern = raw_pattern.lower()
        if not any(
            token in lower_pattern
            for token in (".h", ".m", ".mm", ".pch", "classes", "sources", "source", "src")
        ):
            continue
        derived_root = _profile_root_from_glob_pattern(
            project_dir=project_dir,
            raw_pattern=raw_pattern,
        )
        if derived_root and not _is_non_operational_project_path(derived_root):
            support_roots.add(derived_root)
        if any(token in raw_pattern for token in ("*", "?", "[", "{")):
            continue
        normalized_candidate = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_pattern)
        )
        if normalized_candidate and PurePosixPath(normalized_candidate).suffix.lower() in {
            ".h",
            ".m",
            ".mm",
            ".pch",
        }:
            entrypoint_paths.add(normalized_candidate)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(normalized_candidate).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, support_roots, config_paths


def _meson_profile_hints(
    repo_path: Path,
    meson_path: str,
) -> tuple[set[str], set[str], set[str]]:
    return _cmake_like_profile_hints(repo_path=repo_path, manifest_path=meson_path)


def _qmake_profile_hints(
    repo_path: Path,
    qmake_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(qmake_path)
    if not normalized_path:
        return set(), set(), set()
    manifest = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}include",
        f"{root_prefix}src",
        f"{root_prefix}source",
        f"{root_prefix}sources",
        f"{root_prefix}lib",
        f"{root_prefix}libs",
    }
    entrypoint_paths = {
        f"{root_prefix}main.c",
        f"{root_prefix}main.cc",
        f"{root_prefix}main.cpp",
        f"{root_prefix}main.cxx",
        f"{root_prefix}main.m",
        f"{root_prefix}main.mm",
        f"{root_prefix}src/main.c",
        f"{root_prefix}src/main.cc",
        f"{root_prefix}src/main.cpp",
        f"{root_prefix}src/main.cxx",
        f"{root_prefix}src/main.m",
        f"{root_prefix}src/main.mm",
    }
    config_paths = {normalized_path}
    try:
        text = manifest.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return entrypoint_paths, support_roots, config_paths
    for match in _C_FAMILY_SOURCE_TOKEN_RE.finditer(text):
        raw_path = match.group("path").strip()
        if not raw_path or raw_path.startswith(("$", "/")):
            continue
        resolved_path = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(project_dir) / raw_path)
        )
        if not resolved_path or resolved_path.startswith("/"):
            continue
        entrypoint_paths.add(resolved_path)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for include_target, _line_number in repository_service.qmake_adapter.iter_include_targets(text):
        resolved_path = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(project_dir) / include_target)
        )
        if not resolved_path or PurePosixPath(resolved_path).suffix.lower() not in {
            ".pro",
            ".pri",
            ".prf",
        }:
            continue
        config_paths.add(resolved_path)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for _label, explicit_path, _depends, _line_number in repository_service.qmake_adapter.iter_subdir_entries(
        text
    ):
        subdir_target = explicit_path or ""
        if not subdir_target:
            continue
        resolved_path = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(project_dir) / subdir_target)
        )
        if not resolved_path:
            continue
        resolved = repo_path / resolved_path
        if resolved.is_file() and resolved.suffix.lower() in {".pro", ".pri", ".prf"}:
            config_paths.add(resolved_path)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(resolved_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
            continue
        if resolved.is_dir():
            support_roots.add(resolved_path)
            child_name = PurePosixPath(resolved_path).name
            for candidate_name in (f"{child_name}.pro", f"{child_name}.pri", f"{child_name}.prf"):
                child_path = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(resolved_path) / candidate_name)
                )
                if child_path and (repo_path / child_path).is_file():
                    config_paths.add(child_path)
                    break
    return entrypoint_paths, support_roots, config_paths


def _composer_profile_hints(
    repo_path: Path,
    composer_json_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(composer_json_path)
    if not normalized_path:
        return set(), set(), set()
    payload = repository_service._safe_load_jsonc_dict(repo_path / normalized_path)
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}app",
        f"{root_prefix}src",
        f"{root_prefix}lib",
    }
    entrypoint_paths = {
        f"{root_prefix}artisan",
        f"{root_prefix}public/index.php",
        f"{root_prefix}server.php",
        f"{root_prefix}index.php",
    }
    config_paths = {normalized_path}
    if not isinstance(payload, dict):
        return entrypoint_paths, support_roots, config_paths
    for raw_bin in payload.get("bin") if isinstance(payload.get("bin"), list) else []:
        if isinstance(raw_bin, str) and raw_bin.strip():
            entrypoint_paths.add(str(project_dir / raw_bin.strip()))
    for autoload_key in ("autoload", "autoload-dev"):
        autoload = payload.get(autoload_key)
        if not isinstance(autoload, dict):
            continue
        for mapping_key in ("psr-4", "psr-0"):
            mapping = autoload.get(mapping_key)
            if not isinstance(mapping, dict):
                continue
            for target in mapping.values():
                target_values = target if isinstance(target, list) else [target]
                for raw_target in target_values:
                    if not isinstance(raw_target, str) or not raw_target.strip():
                        continue
                    support_roots.add(
                        repository_service._normalize_repository_relative_pattern(
                            str(project_dir / raw_target.strip())
                        ).split("*", 1)[0].rstrip("/")
                    )
        for file_key in ("files", "classmap"):
            mapping = autoload.get(file_key)
            if not isinstance(mapping, list):
                continue
            for raw_target in mapping:
                if isinstance(raw_target, str) and raw_target.strip():
                    entrypoint_paths.add(str(project_dir / raw_target.strip()))
    return entrypoint_paths, support_roots, config_paths


def _mix_profile_hints(
    repo_path: Path,
    mix_exs_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(mix_exs_path)
    if not normalized_path:
        return set(), set(), set()
    mix_path = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}lib",
        f"{root_prefix}config",
    }
    entrypoint_paths = {
        f"{root_prefix}lib/application.ex",
    }
    config_paths = {normalized_path}
    try:
        text = mix_path.read_text(encoding="utf-8")
    except OSError:
        return entrypoint_paths, support_roots, config_paths
    app_match = re.search(r"app:\s*:([A-Za-z0-9_]+)", text)
    if app_match:
        app_name = app_match.group(1).strip()
        entrypoint_paths.add(f"{root_prefix}lib/{app_name}.ex")
        entrypoint_paths.add(f"{root_prefix}lib/{app_name}/application.ex")
    return entrypoint_paths, support_roots, config_paths


def _swift_package_profile_hints(
    repo_path: Path,
    package_swift_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(package_swift_path)
    if not normalized_path:
        return set(), set(), set()
    package_path = repo_path / normalized_path
    package_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(package_dir) in {"", "."} else f"{package_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}Sources",
    }
    entrypoint_paths = {
        f"{root_prefix}Sources/main.swift",
    }
    config_paths = {normalized_path}
    try:
        text = package_path.read_text(encoding="utf-8")
    except OSError:
        return entrypoint_paths, support_roots, config_paths
    name_match = re.search(r'name:\s*"([^"]+)"', text)
    if name_match:
        package_name = name_match.group(1).strip()
        if package_name:
            entrypoint_paths.add(f"{root_prefix}Sources/{package_name}/main.swift")
    return entrypoint_paths, support_roots, config_paths


def _powershell_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    manifest_stem = PurePosixPath(normalized_path).stem
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}source",
        f"{root_prefix}Public",
        f"{root_prefix}Private",
        f"{root_prefix}Classes",
    }
    entrypoint_paths = {
        f"{root_prefix}{manifest_stem}.psm1",
        f"{root_prefix}src/{manifest_stem}.psm1",
    }
    config_paths = {normalized_path}

    def _add_entrypoint(raw_target: str) -> None:
        normalized_target = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_target.strip())
        )
        if not normalized_target:
            return
        entrypoint_paths.add(normalized_target)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_target).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)

    try:
        text = manifest.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return entrypoint_paths, support_roots, config_paths
    for match in _POWERSHELL_MANIFEST_FIELD_RE.finditer(text):
        raw_target = str(match.group("value") or "").strip()
        if raw_target:
            _add_entrypoint(raw_target)
    for match in _POWERSHELL_MANIFEST_LIST_RE.finditer(text):
        for quoted_match in _QUOTED_SEGMENT_RE.finditer(str(match.group("body") or "")):
            raw_target = str(quoted_match.group("value") or "").strip()
            if raw_target:
                _add_entrypoint(raw_target)
    return entrypoint_paths, support_roots, config_paths


def _scala_build_profile_hints(
    repo_path: Path,
    scala_build_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(scala_build_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}project",
    }
    support_roots.update(
        _scala_build_support_roots(
            repo_path=repo_path,
            project_dir=project_dir,
        )
    )
    entrypoint_paths = {
        f"{root_prefix}src/main/scala/Main.scala",
        f"{root_prefix}src/main/java/Main.java",
    }
    config_paths = {normalized_path}
    return entrypoint_paths, support_roots, config_paths


def _scala_build_support_roots(
    *,
    repo_path: Path,
    project_dir: PurePosixPath,
) -> set[str]:
    base_dir = repo_path / project_dir
    if not base_dir.exists() or not base_dir.is_dir():
        return set()
    excluded_dirnames = set(repository_service._DEFAULT_EXCLUDED_PATH_PARTS)
    support_roots: set[str] = set()
    for dirpath, dirnames, _filenames in os.walk(base_dir):
        current_dir = Path(dirpath)
        dirnames[:] = [name for name in dirnames if name not in excluded_dirnames]
        try:
            relative_path = current_dir.relative_to(repo_path)
        except ValueError:
            dirnames[:] = []
            continue
        normalized_path = repository_service._normalize_repository_relative_path(
            str(relative_path)
        )
        if not normalized_path:
            continue
        if repository_service._is_test_path(normalized_path) or _is_non_operational_profile_path(
            normalized_path
        ):
            dirnames[:] = []
            continue
        relative_depth = len(current_dir.relative_to(base_dir).parts)
        if relative_depth >= 5:
            dirnames[:] = []
        parts = PurePosixPath(normalized_path).parts
        basename = parts[-1].lower() if parts else ""
        if basename == "src" or basename.startswith("src-"):
            support_roots.add(normalized_path)
            continue
        if len(parts) >= 3 and basename in {"scala", "java"}:
            if parts[-2].lower() == "main" and parts[-3].lower() == "src":
                support_roots.add(normalized_path)
    return support_roots


def _zig_build_profile_hints(
    repo_path: Path,
    build_zig_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(build_zig_path)
    if not normalized_path:
        return set(), set(), set()
    build_path = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}lib",
    }
    entrypoint_paths = {
        f"{root_prefix}src/main.zig",
        f"{root_prefix}src/root.zig",
        f"{root_prefix}main.zig",
        f"{root_prefix}root.zig",
    }
    config_paths = {normalized_path}
    try:
        text = build_path.read_text(encoding="utf-8")
    except OSError:
        return entrypoint_paths, support_roots, config_paths
    for match in _ZIG_SOURCE_TOKEN_RE.finditer(text):
        raw_path = match.group("path").strip()
        if not raw_path or raw_path.startswith(("$", "/")):
            continue
        resolved_path = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(project_dir) / raw_path)
        )
        if (
            not resolved_path
            or resolved_path.startswith("/")
            or repository_service._is_test_path(resolved_path)
            or _is_non_operational_profile_path(resolved_path)
        ):
            continue
        entrypoint_paths.add(resolved_path)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
        sibling_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).with_suffix(""))
        )
        if sibling_dir and (repo_path / sibling_dir).is_dir():
            support_roots.add(sibling_dir)
    return entrypoint_paths, support_roots, config_paths


def _append_manifest_field_value(
    *,
    values_by_field: dict[str, list[str]],
    field_name: str,
    raw_value: str,
) -> None:
    normalized_value = raw_value.strip()
    if not normalized_value:
        return
    if field_name in {"main", "main-is"}:
        values_by_field[field_name].append(normalized_value)
        return
    tokens = [
        token.strip()
        for comma_group in normalized_value.split(",")
        for token in comma_group.split()
        if token.strip()
    ]
    values_by_field[field_name].extend(tokens)


def _collect_manifest_field_values(
    text: str,
    *,
    field_names: set[str],
) -> dict[str, list[str]]:
    values_by_field = {field_name: [] for field_name in field_names}
    active_field: str | None = None
    active_indent: int | None = None
    for raw_line in text.splitlines():
        stripped_line = raw_line.strip()
        if not stripped_line or stripped_line.startswith(("--", "#")):
            continue
        indented_line = raw_line.lstrip()
        current_indent = len(raw_line) - len(indented_line)
        field_match = re.match(r"^(?P<field>[A-Za-z0-9_-]+)\s*:\s*(?P<value>.*)$", indented_line)
        if field_match is not None:
            field_name = field_match.group("field").lower()
            if field_name in values_by_field:
                active_field = field_name
                active_indent = current_indent
                _append_manifest_field_value(
                    values_by_field=values_by_field,
                    field_name=field_name,
                    raw_value=field_match.group("value"),
                )
            else:
                active_field = None
                active_indent = None
            continue
        if active_field is None or active_indent is None or current_indent <= active_indent:
            active_field = None
            active_indent = None
            continue
        continuation = indented_line
        if continuation.startswith("- "):
            continuation = continuation[2:].strip()
        _append_manifest_field_value(
            values_by_field=values_by_field,
            field_name=active_field,
            raw_value=continuation,
        )
    return values_by_field


def _candidate_haskell_module_paths(
    *,
    project_dir: PurePosixPath,
    source_dir: str,
    module_name: str,
) -> tuple[str, ...]:
    normalized_module = module_name.strip()
    if not normalized_module:
        return ()
    source_prefix = repository_service._normalize_repository_relative_path(
        str(project_dir / source_dir)
    )
    module_path = normalized_module.replace(".", "/")
    candidate_paths: list[str] = []
    for extension in _HASKELL_SOURCE_EXTENSIONS:
        relative_candidate = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(source_prefix or "") / f"{module_path}{extension}")
        )
        if relative_candidate:
            candidate_paths.append(relative_candidate)
    return tuple(dict.fromkeys(candidate_paths))


def _haskell_cabal_profile_hints(
    repo_path: Path,
    cabal_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(cabal_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_path = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}app",
        f"{root_prefix}lib",
    }
    entrypoint_paths = {
        f"{root_prefix}app/Main.hs",
        f"{root_prefix}src/Main.hs",
        f"{root_prefix}lib/Main.hs",
    }
    config_paths = {normalized_path}
    try:
        text = manifest_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return entrypoint_paths, support_roots, config_paths
    field_values = _collect_manifest_field_values(
        text,
        field_names={"hs-source-dirs", "main-is", "exposed-modules", "other-modules"},
    )
    raw_source_dirs = [
        source_dir
        for source_dir in field_values["hs-source-dirs"]
        if source_dir and not _is_non_operational_profile_path(source_dir)
    ] or ["."]
    for source_dir in raw_source_dirs:
        normalized_source_dir = repository_service._normalize_repository_relative_path(
            str(project_dir / source_dir)
        )
        if normalized_source_dir and not _is_non_operational_profile_path(normalized_source_dir):
            support_roots.add(normalized_source_dir)
    for main_path in field_values["main-is"]:
        for source_dir in raw_source_dirs:
            resolved_path = repository_service._normalize_repository_relative_path(
                str(project_dir / source_dir / main_path)
            )
            if resolved_path:
                entrypoint_paths.add(resolved_path)
    for module_name in field_values["exposed-modules"] + field_values["other-modules"]:
        for source_dir in raw_source_dirs:
            entrypoint_paths.update(
                _candidate_haskell_module_paths(
                    project_dir=project_dir,
                    source_dir=source_dir,
                    module_name=module_name,
                )
            )
    return entrypoint_paths, support_roots, config_paths


def _haskell_package_yaml_profile_hints(
    repo_path: Path,
    package_yaml_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(package_yaml_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_path = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}app",
        f"{root_prefix}lib",
    }
    entrypoint_paths = {
        f"{root_prefix}app/Main.hs",
        f"{root_prefix}src/Main.hs",
        f"{root_prefix}lib/Main.hs",
    }
    config_paths = {normalized_path}
    try:
        text = manifest_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return entrypoint_paths, support_roots, config_paths
    field_values = _collect_manifest_field_values(
        text,
        field_names={"source-dirs", "main", "exposed-modules", "other-modules"},
    )
    raw_source_dirs = [
        source_dir
        for source_dir in field_values["source-dirs"]
        if source_dir and not _is_non_operational_profile_path(source_dir)
    ] or ["src", "app", "lib"]
    for source_dir in raw_source_dirs:
        normalized_source_dir = repository_service._normalize_repository_relative_path(
            str(project_dir / source_dir)
        )
        if normalized_source_dir and not _is_non_operational_profile_path(normalized_source_dir):
            support_roots.add(normalized_source_dir)
    for main_path in field_values["main"]:
        for source_dir in raw_source_dirs:
            resolved_path = repository_service._normalize_repository_relative_path(
                str(project_dir / source_dir / main_path)
            )
            if resolved_path:
                entrypoint_paths.add(resolved_path)
    for module_name in field_values["exposed-modules"] + field_values["other-modules"]:
        for source_dir in raw_source_dirs:
            entrypoint_paths.update(
                _candidate_haskell_module_paths(
                    project_dir=project_dir,
                    source_dir=source_dir,
                    module_name=module_name,
                )
            )
    return entrypoint_paths, support_roots, config_paths


def _haskell_project_profile_hints(
    project_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(project_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}app",
        f"{root_prefix}lib",
    }
    entrypoint_paths = {
        f"{root_prefix}app/Main.hs",
        f"{root_prefix}src/Main.hs",
        f"{root_prefix}lib/Main.hs",
    }
    config_paths = {normalized_path}
    return entrypoint_paths, support_roots, config_paths


def _csproj_profile_hints(csproj_path: str) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(csproj_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    if _is_non_operational_project_path(str(project_dir)):
        return set(), set(), {normalized_path}
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
    }
    entrypoint_paths = {
        f"{root_prefix}Program.cs",
        f"{root_prefix}Program.fs",
        f"{root_prefix}Program.vb",
        f"{root_prefix}Main.cs",
        f"{root_prefix}Main.fs",
        f"{root_prefix}Main.vb",
        f"{root_prefix}Startup.cs",
        f"{root_prefix}Startup.fs",
        f"{root_prefix}Startup.vb",
        f"{root_prefix}App.xaml.cs",
        f"{root_prefix}App.fs",
        f"{root_prefix}App.xaml.vb",
        f"{root_prefix}Application.vb",
    }
    config_paths = {normalized_path}
    return entrypoint_paths, support_roots, config_paths


def _sln_project_paths(
    repo_path: Path,
    sln_path: str,
) -> tuple[str, ...]:
    normalized_path = repository_service._normalize_repository_relative_path(sln_path)
    if not normalized_path:
        return ()
    solution_path = repo_path / normalized_path
    try:
        text = solution_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ()
    solution_dir = PurePosixPath(normalized_path).parent
    project_paths: list[str] = []
    seen: set[str] = set()
    for match in _SLN_PROJECT_RE.finditer(text):
        raw_project_path = match.group("path").replace("\\", "/").strip()
        if not raw_project_path:
            continue
        normalized_project_path = repository_service._normalize_repository_relative_path(
            str(solution_dir / raw_project_path)
        )
        if not normalized_project_path or normalized_project_path in seen:
            continue
        seen.add(normalized_project_path)
        project_paths.append(normalized_project_path)
    return tuple(project_paths)


def _sln_profile_hints(
    repo_path: Path,
    sln_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(sln_path)
    if not normalized_path:
        return set(), set(), set()
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    config_paths: set[str] = {normalized_path}
    project_paths = _sln_project_paths(repo_path, normalized_path)
    for project_path in project_paths:
        project_entrypoints, project_roots, project_configs = _csproj_profile_hints(project_path)
        entrypoint_paths.update(project_entrypoints)
        support_roots.update(project_roots)
        config_paths.update(project_configs)
    if entrypoint_paths or support_roots or len(config_paths) > 1:
        return entrypoint_paths, support_roots, config_paths
    return _csproj_profile_hints(normalized_path)


def _gemfile_profile_hints(
    repo_path: Path,
    gemfile_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(gemfile_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}lib",
        f"{root_prefix}app",
        f"{root_prefix}bin",
        f"{root_prefix}exe",
    }
    package_names = _ruby_package_names_for_profile(
        repo_path=repo_path,
        normalized_path=normalized_path,
    )
    entrypoint_paths = _ruby_package_entrypoint_paths(
        repo_path=repo_path,
        project_dir=project_dir,
        package_names=package_names,
    )
    config_paths = {normalized_path}
    return entrypoint_paths, support_roots, config_paths


def _erlang_project_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(config_path)
    if not normalized_path:
        return set(), set(), set()
    config_posix_path = PurePosixPath(normalized_path)
    project_dir = config_posix_path.parent
    if config_posix_path.name.lower().endswith(".app.src") and project_dir.name == "src":
        project_dir = project_dir.parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    config_paths = {normalized_path}
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}include",
    }
    entrypoint_paths: set[str] = set()
    project_root = repo_path / project_dir
    source_root = project_root / "src"
    if source_root.is_dir():
        for candidate in sorted(source_root.glob("*.erl")):
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if relative_path and not repository_service._is_test_path(relative_path):
                entrypoint_paths.add(relative_path)
    apps_root = project_root / "apps"
    if apps_root.is_dir():
        support_roots.add(f"{root_prefix}apps")
        for app_dir in sorted(child for child in apps_root.iterdir() if child.is_dir()):
            for subdir_name in ("src", "include"):
                subdir = app_dir / subdir_name
                if not subdir.is_dir():
                    continue
                relative_root = repository_service._normalize_repository_relative_path(
                    str(subdir.relative_to(repo_path))
                )
                if relative_root:
                    support_roots.add(relative_root)
                if subdir_name != "src":
                    continue
                for candidate in sorted(subdir.glob("*.erl")):
                    relative_path = repository_service._normalize_repository_relative_path(
                        str(candidate.relative_to(repo_path))
                    )
                    if relative_path and not repository_service._is_test_path(relative_path):
                        entrypoint_paths.add(relative_path)
    return entrypoint_paths, support_roots, config_paths


def _nim_project_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(config_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    config_paths = {normalized_path}
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}lib",
        f"{root_prefix}source",
    }
    entrypoint_paths: set[str] = set()
    project_root = repo_path / project_dir
    source_dirs = [project_root / "src", project_root / "lib", project_root / "source"]
    for source_dir in source_dirs:
        if not source_dir.is_dir():
            continue
        relative_root = repository_service._normalize_repository_relative_path(
            str(source_dir.relative_to(repo_path))
        )
        if relative_root:
            support_roots.add(relative_root)
        for candidate in sorted(source_dir.rglob("*.nim")):
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                relative_path
                and not repository_service._is_test_path(relative_path)
                and not _is_non_operational_profile_path(relative_path)
            ):
                entrypoint_paths.add(relative_path)

    package_roots: list[Path] = []
    config_basename = PurePosixPath(normalized_path).name.lower()
    if config_basename.endswith(".nimble"):
        package_candidates = {
            PurePosixPath(normalized_path).stem,
            re.sub(r"[^a-z0-9_]+", "_", repo_path.name.lower()).strip("_"),
        }
        for package_name in sorted(name for name in package_candidates if name):
            root_module = project_root / f"{package_name}.nim"
            if root_module.is_file():
                relative_path = repository_service._normalize_repository_relative_path(
                    str(root_module.relative_to(repo_path))
                )
                if (
                    relative_path
                    and not repository_service._is_test_path(relative_path)
                    and not _is_non_operational_profile_path(relative_path)
                ):
                    entrypoint_paths.add(relative_path)
            package_root = project_root / package_name
            if not package_root.is_dir():
                continue
            package_roots.append(package_root)
    for package_root in package_roots:
        relative_root = repository_service._normalize_repository_relative_path(
            str(package_root.relative_to(repo_path))
        )
        if relative_root:
            support_roots.add(relative_root)
        for candidate in sorted(package_root.rglob("*.nim")):
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                relative_path
                and not repository_service._is_test_path(relative_path)
                and not _is_non_operational_profile_path(relative_path)
            ):
                entrypoint_paths.add(relative_path)
    if entrypoint_paths:
        return entrypoint_paths, support_roots, config_paths
    for candidate in sorted(project_root.glob("*.nim")):
        relative_path = repository_service._normalize_repository_relative_path(
            str(candidate.relative_to(repo_path))
        )
        if (
            relative_path
            and not repository_service._is_test_path(relative_path)
            and not _is_non_operational_profile_path(relative_path)
        ):
            entrypoint_paths.add(relative_path)
    return entrypoint_paths, support_roots, config_paths


def _elm_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    config_paths = {normalized_path}
    support_roots = {
        str(project_dir)
        for project_dir in (project_dir,)
        if str(project_dir) not in {"", "."}
    }
    entrypoint_paths: set[str] = set()
    try:
        payload = json.loads(manifest_file.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        payload = {}

    source_roots: list[str] = []
    raw_source_directories = payload.get("source-directories")
    if isinstance(raw_source_directories, list):
        for raw_source_root in raw_source_directories:
            if not isinstance(raw_source_root, str) or not raw_source_root.strip():
                continue
            resolved_path = repository_service._normalize_repository_relative_path(
                str(project_dir / raw_source_root.strip())
            )
            if not resolved_path:
                continue
            absolute_path = repo_path / resolved_path
            if absolute_path.is_dir():
                support_roots.add(resolved_path)
                source_roots.append(resolved_path)
                continue
            if (
                absolute_path.is_file()
                and _probe_language_for_path(resolved_path, repo_path=repo_path) == "elm"
            ):
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(resolved_path).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
                    source_roots.append(parent_dir)
                if _is_operational_profile_entrypoint_candidate(
                    resolved_path,
                    repo_path=repo_path,
                ):
                    entrypoint_paths.add(resolved_path)

    if not source_roots:
        for fallback_dir in ("src", "app", "examples", "example"):
            candidate_dir = repository_service._normalize_repository_relative_path(
                str(project_dir / fallback_dir)
            )
            if candidate_dir and (repo_path / candidate_dir).is_dir():
                support_roots.add(candidate_dir)
                source_roots.append(candidate_dir)

    def _iter_module_names(value: Any) -> list[str]:
        if isinstance(value, str):
            normalized = value.strip()
            return [normalized] if normalized else []
        if isinstance(value, list):
            module_names: list[str] = []
            for item in value:
                module_names.extend(_iter_module_names(item))
            return module_names
        if isinstance(value, dict):
            module_names: list[str] = []
            for item in value.values():
                module_names.extend(_iter_module_names(item))
            return module_names
        return []

    for module_name in _iter_module_names(payload.get("exposed-modules")):
        module_relative_path = module_name.replace(".", "/") + ".elm"
        candidate_roots = source_roots or [
            repository_service._normalize_repository_relative_path(str(project_dir / "src"))
        ]
        for source_root in candidate_roots:
            normalized_root = repository_service._normalize_repository_relative_path(source_root)
            if not normalized_root:
                continue
            resolved_path = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(normalized_root) / module_relative_path)
            )
            if (
                not resolved_path
                or not (repo_path / resolved_path).is_file()
                or _probe_language_for_path(resolved_path, repo_path=repo_path) != "elm"
            ):
                continue
            support_roots.add(normalized_root)
            if _is_operational_profile_entrypoint_candidate(
                resolved_path,
                repo_path=repo_path,
            ):
                entrypoint_paths.add(resolved_path)

    for source_root in source_roots:
        main_module_path = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(source_root) / "Main.elm")
        )
        if (
            not main_module_path
            or not (repo_path / main_module_path).is_file()
            or _probe_language_for_path(main_module_path, repo_path=repo_path) != "elm"
        ):
            continue
        if _is_operational_profile_entrypoint_candidate(
            main_module_path,
            repo_path=repo_path,
        ):
            entrypoint_paths.add(main_module_path)

    if entrypoint_paths or not source_roots:
        return entrypoint_paths, support_roots, config_paths

    for source_root in source_roots:
        source_dir = repo_path / source_root
        if not source_dir.is_dir():
            continue
        for candidate in sorted(source_dir.rglob("*.elm")):
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                relative_path
                and _is_operational_profile_entrypoint_candidate(
                    relative_path,
                    repo_path=repo_path,
                )
            ):
                entrypoint_paths.add(relative_path)
    return entrypoint_paths, support_roots, config_paths


def _ocaml_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(config_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    config_paths = {normalized_path}
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}lib",
        f"{root_prefix}bin",
        f"{root_prefix}app",
    }
    entrypoint_paths: set[str] = set()
    project_root = repo_path / project_dir
    search_roots: list[Path] = []
    config_name = PurePosixPath(normalized_path).name.lower()
    if config_name == "dune":
        search_roots.append(project_root)
    elif config_name == "dune-project":
        for dune_file in sorted(project_root.rglob("dune")):
            if not dune_file.is_file():
                continue
            relative_dune = repository_service._normalize_repository_relative_path(
                str(dune_file.relative_to(repo_path))
            )
            if not relative_dune or _is_non_operational_profile_path(relative_dune):
                continue
            search_roots.append(dune_file.parent)
            relative_root = repository_service._normalize_repository_relative_path(
                str(dune_file.parent.relative_to(repo_path))
            )
            if relative_root:
                support_roots.add(relative_root)
    else:
        search_roots.extend(project_root / subdir for subdir in ("src", "lib", "bin", "app"))
        search_roots.append(project_root)
    seen_roots: set[str] = set()
    for search_root in search_roots:
        if not search_root.is_dir():
            continue
        relative_root = repository_service._normalize_repository_relative_path(
            str(search_root.relative_to(repo_path))
        )
        if relative_root in seen_roots:
            continue
        seen_roots.add(relative_root or "")
        if relative_root:
            support_roots.add(relative_root)
        for extension in ("*.ml", "*.mli"):
            if config_name == "dune":
                iterator = search_root.glob(extension)
            else:
                iterator = search_root.rglob(extension)
            for candidate in sorted(iterator):
                relative_path = repository_service._normalize_repository_relative_path(
                    str(candidate.relative_to(repo_path))
                )
                if (
                    relative_path
                    and not repository_service._is_test_path(relative_path)
                    and not _is_non_operational_profile_path(relative_path)
                ):
                    entrypoint_paths.add(relative_path)
    return entrypoint_paths, support_roots, config_paths


def _ml_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(config_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_path = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    if _is_non_operational_project_path(str(project_dir)):
        return set(), set(), {normalized_path}
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    config_paths = {normalized_path}
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}lib",
        f"{root_prefix}basis",
        f"{root_prefix}compiler",
    }
    entrypoint_paths = {
        f"{root_prefix}main.sml",
        f"{root_prefix}src/main.sml",
        f"{root_prefix}lib/main.sml",
    }
    try:
        text = manifest_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return entrypoint_paths, support_roots, config_paths

    discovered_paths: list[str] = []
    for match in _ML_MANIFEST_PATH_RE.finditer(text):
        raw_path = str(match.group("path") or "").strip()
        if not raw_path or raw_path.startswith(("$", "/")):
            continue
        resolved_path = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_path)
        )
        if not resolved_path or resolved_path.startswith("/"):
            continue
        discovered_paths.append(resolved_path)

    if manifest_path.suffix.lower() == ".cm" and not discovered_paths:
        return set(), set(), set()

    for resolved_path in discovered_paths:
        if _is_non_operational_profile_path(resolved_path):
            continue
        suffix = PurePosixPath(resolved_path).suffix.lower()
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if suffix in {".mlb", ".cm"}:
            config_paths.add(resolved_path)
            if parent_dir:
                support_roots.add(parent_dir)
            continue
        if suffix not in _ML_SOURCE_EXTENSIONS or repository_service._is_test_path(resolved_path):
            continue
        if parent_dir:
            support_roots.add(parent_dir)
        entrypoint_paths.add(resolved_path)
    return entrypoint_paths, support_roots, config_paths


def _classic_visual_basic_profile_hints(
    repo_path: Path,
    project_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(project_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_path = repo_path / normalized_path
    try:
        text = manifest_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set(), set(), set()
    if not repository_service.classic_visual_basic_adapter.is_probable_classic_visual_basic_source(
        path=Path(normalized_path),
        text=text,
    ):
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    support_roots = {
        str(project_dir)
        for project_dir in (project_dir,)
        if str(project_dir) not in {"", "."}
    }
    config_paths = {normalized_path}
    entrypoint_paths: set[str] = set()
    form_paths: list[str] = []
    fallback_paths: list[str] = []
    startup_name = repository_service.classic_visual_basic_adapter.project_startup_name(
        text
    ).lower()
    for entry in repository_service.classic_visual_basic_adapter.project_component_entries(
        text,
        manifest_path=normalized_path,
    ):
        resolved_path = repository_service._normalize_repository_relative_path(str(entry["path"]))
        if not resolved_path or repository_service._is_test_path(resolved_path):
            continue
        if not (repo_path / resolved_path).is_file():
            continue
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
        component_kind = str(entry["component_kind"]).lower()
        component_name = str(entry["component_name"]).lower()
        if startup_name and startup_name == component_name:
            entrypoint_paths.add(resolved_path)
            continue
        if component_kind in {"form", "mdiform"}:
            form_paths.append(resolved_path)
            continue
        if component_kind == "module" and startup_name in {"main", "sub main"}:
            entrypoint_paths.add(resolved_path)
            continue
        fallback_paths.append(resolved_path)
    if entrypoint_paths:
        return entrypoint_paths, support_roots, config_paths
    if form_paths:
        entrypoint_paths.update(form_paths)
        return entrypoint_paths, support_roots, config_paths
    entrypoint_paths.update(fallback_paths)
    return entrypoint_paths, support_roots, config_paths


def _xpp_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(config_path)
    if not normalized_path or not _is_xpp_descriptor_config_path(repo_path, normalized_path):
        return set(), set(), set()
    descriptor_path = PurePosixPath(normalized_path)
    config_paths = {normalized_path}
    support_roots: set[str] = set()
    entrypoint_paths: set[str] = set()

    module_container = descriptor_path.parent.parent
    model_name = descriptor_path.stem
    candidate_roots: list[PurePosixPath] = []
    if str(module_container) not in {"", "."}:
        support_roots.add(str(module_container))
        candidate_roots.append(module_container / model_name)
        candidate_roots.append(module_container)

    seen_roots: set[str] = set()
    ordered_roots: list[str] = []
    for candidate_root in candidate_roots:
        normalized_root = repository_service._normalize_repository_relative_path(
            str(candidate_root)
        )
        if (
            not normalized_root
            or normalized_root in seen_roots
            or not (repo_path / normalized_root).is_dir()
        ):
            continue
        seen_roots.add(normalized_root)
        ordered_roots.append(normalized_root)
        support_roots.add(normalized_root)

    for root in ordered_roots:
        root_path = repo_path / root
        for suffix in ("*.xml", "*.xpp", "*.xpo"):
            for candidate in sorted(root_path.rglob(suffix)):
                relative_path = repository_service._normalize_repository_relative_path(
                    str(candidate.relative_to(repo_path))
                )
                if (
                    not relative_path
                    or repository_service._is_test_path(relative_path)
                    or _is_non_operational_profile_path(relative_path)
                    or not _is_repo_profile_code_candidate(relative_path, repo_path=repo_path)
                ):
                    continue
                entrypoint_paths.add(relative_path)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(relative_path).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
    return entrypoint_paths, support_roots, config_paths


def _cfml_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(config_path)
    if not normalized_path or not _is_cfml_box_config_path(repo_path, normalized_path):
        return set(), set(), set()
    manifest_path = PurePosixPath(normalized_path)
    project_dir = manifest_path.parent
    config_paths = {normalized_path}
    support_roots: set[str] = set()
    entrypoint_paths: set[str] = set()

    candidate_roots: list[str] = []
    for raw_root in (
        "",
        "api",
        "handlers",
        "models",
        "controllers",
        "views",
        "config",
        "modules",
        "modules_app",
        "public",
        "services",
        "src",
    ):
        resolved_root = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_root)
        )
        if not resolved_root or not (repo_path / resolved_root).is_dir():
            continue
        support_roots.add(resolved_root)
        candidate_roots.append(resolved_root)

    for raw_entrypoint in (
        "Application.cfc",
        "Application.cfm",
        "index.cfm",
        "public/Application.cfc",
        "public/index.cfm",
    ):
        resolved_path = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_entrypoint)
        )
        if (
            not resolved_path
            or not (repo_path / resolved_path).is_file()
            or repository_service._is_test_path(resolved_path)
            or _is_non_operational_profile_path(resolved_path)
            or _probe_language_for_path(resolved_path, repo_path=repo_path) != "cfml"
        ):
            continue
        entrypoint_paths.add(resolved_path)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)

    if entrypoint_paths:
        return entrypoint_paths, support_roots, config_paths

    scan_roots = candidate_roots or [
        repository_service._normalize_repository_relative_path(str(project_dir))
    ]
    for scan_root in scan_roots:
        if not scan_root:
            continue
        scan_root_path = repo_path / scan_root
        if not scan_root_path.is_dir():
            continue
        for suffix in ("*.cfc", "*.cfm", "*.cfml"):
            for candidate in sorted(scan_root_path.rglob(suffix)):
                relative_path = repository_service._normalize_repository_relative_path(
                    str(candidate.relative_to(repo_path))
                )
                if (
                    not relative_path
                    or repository_service._is_test_path(relative_path)
                    or _is_non_operational_profile_path(relative_path)
                    or _probe_language_for_path(relative_path, repo_path=repo_path) != "cfml"
                ):
                    continue
                entrypoint_paths.add(relative_path)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(relative_path).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
    return entrypoint_paths, support_roots, config_paths


def _actionscript_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    config_paths = {normalized_path}
    support_roots = {
        str(project_dir)
        for project_dir in (project_dir,)
        if str(project_dir) not in {"", "."}
    }
    entrypoint_paths: set[str] = set()
    try:
        payload = json.loads(manifest_file.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    compiler_options = payload.get("compilerOptions", {})
    if not isinstance(compiler_options, dict):
        compiler_options = {}

    def _iter_string_values(value: Any) -> tuple[str, ...]:
        if isinstance(value, str):
            return (value,)
        if isinstance(value, list):
            return tuple(item for item in value if isinstance(item, str))
        return ()

    source_roots: list[str] = []
    for raw_source_root in (
        *_iter_string_values(payload.get("source-path")),
        *_iter_string_values(payload.get("include-sources")),
        *_iter_string_values(compiler_options.get("source-path")),
        *_iter_string_values(compiler_options.get("include-sources")),
    ):
        resolved_path = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_source_root)
        )
        if not resolved_path or not (repo_path / resolved_path).exists():
            continue
        if (repo_path / resolved_path).is_dir():
            support_roots.add(resolved_path)
            source_roots.append(resolved_path)
            continue
        if (
            not (repo_path / resolved_path).is_file()
            or _probe_language_for_path(resolved_path, repo_path=repo_path) != "actionscript"
        ):
            continue
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
            source_roots.append(parent_dir)
        if _is_operational_profile_entrypoint_candidate(
            resolved_path,
            repo_path=repo_path,
        ):
            entrypoint_paths.add(resolved_path)

    for raw_file_path in _iter_string_values(payload.get("files")):
        resolved_path = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_file_path)
        )
        if (
            not resolved_path
            or not (repo_path / resolved_path).is_file()
            or _probe_language_for_path(resolved_path, repo_path=repo_path) != "actionscript"
        ):
            continue
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if parent_dir and not source_roots:
            support_roots.add(parent_dir)
        if _is_operational_profile_entrypoint_candidate(
            resolved_path,
            repo_path=repo_path,
        ):
            entrypoint_paths.add(resolved_path)

    main_class = ""
    for candidate_value in (payload.get("mainClass"), compiler_options.get("mainClass")):
        if isinstance(candidate_value, str) and candidate_value.strip():
            main_class = candidate_value.strip()
            break
    if main_class:
        main_class_path = main_class.replace(".", "/") + ".as"
        candidate_roots = source_roots or [
            repository_service._normalize_repository_relative_path(str(project_dir / "src")),
            repository_service._normalize_repository_relative_path(str(project_dir / "source")),
            repository_service._normalize_repository_relative_path(str(project_dir)),
        ]
        for candidate_root in candidate_roots:
            normalized_root = repository_service._normalize_repository_relative_path(candidate_root)
            if not normalized_root:
                continue
            resolved_path = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(normalized_root) / main_class_path)
            )
            if (
                not resolved_path
                or not (repo_path / resolved_path).is_file()
                or _probe_language_for_path(resolved_path, repo_path=repo_path) != "actionscript"
            ):
                continue
            support_roots.add(normalized_root)
            if _is_operational_profile_entrypoint_candidate(
                resolved_path,
                repo_path=repo_path,
            ):
                entrypoint_paths.add(resolved_path)

    if support_roots:
        return entrypoint_paths, support_roots, config_paths

    for fallback_dir in ("src", "source", "as3", "actionscript"):
        candidate_dir = repository_service._normalize_repository_relative_path(
            str(project_dir / fallback_dir)
        )
        if candidate_dir and (repo_path / candidate_dir).is_dir():
            support_roots.add(candidate_dir)
    return entrypoint_paths, support_roots, config_paths


def _systemverilog_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    config_paths = {normalized_path}
    support_roots = {
        str(project_dir)
        for project_dir in (project_dir,)
        if str(project_dir) not in {"", "."}
    }
    entrypoint_paths: set[str] = set()
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        manifest_text = ""

    discovered_paths: list[str] = []
    for match in _SYSTEMVERILOG_MANIFEST_PATH_RE.finditer(manifest_text):
        raw_path = str(match.group("path") or "").strip()
        if not raw_path or raw_path.startswith(("$", "/", "+")):
            continue
        resolved_path = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_path)
        )
        if not resolved_path or resolved_path.startswith("/"):
            continue
        if not (repo_path / resolved_path).is_file():
            continue
        if _probe_language_for_path(resolved_path, repo_path=repo_path) != "systemverilog":
            continue
        discovered_paths.append(resolved_path)

    for resolved_path in discovered_paths:
        if _is_non_operational_profile_path(resolved_path):
            continue
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
        if _is_operational_profile_entrypoint_candidate(
            resolved_path,
            repo_path=repo_path,
        ):
            entrypoint_paths.add(resolved_path)

    if support_roots:
        return entrypoint_paths, support_roots, config_paths

    for fallback_dir in ("rtl", "src", "hdl", "verilog", "tb", "dv"):
        candidate_dir = repository_service._normalize_repository_relative_path(
            str(project_dir / fallback_dir)
        )
        if candidate_dir and (repo_path / candidate_dir).is_dir():
            support_roots.add(candidate_dir)
    return entrypoint_paths, support_roots, config_paths


def _gml_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    config_paths = {normalized_path}
    support_roots = {
        str(project_dir)
        for project_dir in (project_dir,)
        if str(project_dir) not in {"", "."}
    }
    entrypoint_paths: set[str] = set()
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        manifest_text = ""
    payload = repository_service.gml_adapter.load_game_maker_json(manifest_text)
    if not isinstance(payload, dict):
        payload = {}

    resource_entries = payload.get("resources")
    if not isinstance(resource_entries, list):
        resource_entries = []

    resolved_resource_paths: set[str] = set()
    for resource_entry in resource_entries:
        if not isinstance(resource_entry, dict):
            continue
        resource_id = resource_entry.get("id")
        raw_path = ""
        if isinstance(resource_id, dict):
            raw_path = str(resource_id.get("path") or "").strip()
        if not raw_path:
            raw_path = str(resource_entry.get("path") or "").strip()
        if not raw_path:
            continue
        resolved_resource_path = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_path)
        )
        if (
            not resolved_resource_path
            or not (repo_path / resolved_resource_path).is_file()
            or resolved_resource_path in resolved_resource_paths
        ):
            continue
        resolved_resource_paths.add(resolved_resource_path)
        resource_path = PurePosixPath(resolved_resource_path)
        resource_parent = repository_service._normalize_repository_relative_path(
            str(resource_path.parent)
        )
        if resource_parent:
            support_roots.add(resource_parent)
        top_level_dir = resource_path.parts[0] if resource_path.parts else ""
        if top_level_dir:
            support_roots.add(top_level_dir)

        if top_level_dir == "scripts":
            script_code_path = repository_service._normalize_repository_relative_path(
                str(resource_path.parent / f"{resource_path.stem}.gml")
            )
            if (
                not script_code_path
                or not (repo_path / script_code_path).is_file()
                or _probe_language_for_path(script_code_path, repo_path=repo_path) != "gml"
            ):
                continue
            if _is_operational_profile_entrypoint_candidate(
                script_code_path,
                repo_path=repo_path,
            ):
                entrypoint_paths.add(script_code_path)
            continue

        if top_level_dir != "objects" or not resource_parent:
            continue
        object_dir = repo_path / resource_parent
        if not object_dir.is_dir():
            continue
        for child_path in sorted(object_dir.glob("*.gml")):
            child_relative_path = repository_service._normalize_repository_relative_path(
                str(child_path.relative_to(repo_path))
            )
            if (
                not child_relative_path
                or _probe_language_for_path(child_relative_path, repo_path=repo_path) != "gml"
            ):
                continue
            if _is_operational_profile_entrypoint_candidate(
                child_relative_path,
                repo_path=repo_path,
            ):
                entrypoint_paths.add(child_relative_path)

    if support_roots:
        return entrypoint_paths, support_roots, config_paths

    for fallback_dir in ("scripts", "objects", "rooms", "sequences", "timelines"):
        candidate_dir = repository_service._normalize_repository_relative_path(
            str(project_dir / fallback_dir)
        )
        if candidate_dir and (repo_path / candidate_dir).is_dir():
            support_roots.add(candidate_dir)
    return entrypoint_paths, support_roots, config_paths


def _gdscript_project_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    config_paths = {normalized_path}
    support_roots = {
        str(project_dir)
        for project_dir in (project_dir,)
        if str(project_dir) not in {"", "."}
    }
    entrypoint_paths: set[str] = set()
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        manifest_text = ""

    def _resolve_godot_resource(raw_value: str) -> str | None:
        match = _GDSCRIPT_RESOURCE_RE.search(str(raw_value or ""))
        if match is None:
            return None
        resource_path = repository_service._normalize_repository_relative_path(
            str(project_dir / str(match.group("path") or ""))
        )
        if not resource_path:
            return None
        return resource_path

    def _scene_script_paths(raw_scene_path: str) -> set[str]:
        if str(raw_scene_path).startswith("res://"):
            resolved_scene_path = _resolve_godot_resource(raw_scene_path)
        else:
            resolved_scene_path = repository_service._normalize_repository_relative_path(
                str(raw_scene_path)
            )
        if not resolved_scene_path or not (repo_path / resolved_scene_path).is_file():
            return set()
        if PurePosixPath(resolved_scene_path).suffix.lower() == ".gd":
            return {resolved_scene_path}
        if PurePosixPath(resolved_scene_path).suffix.lower() not in {".tscn", ".scn"}:
            return set()
        try:
            scene_text = (repo_path / resolved_scene_path).read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            return set()
        script_paths: set[str] = set()
        for match in _GDSCRIPT_SCENE_SCRIPT_RE.finditer(scene_text):
            resource_path = _resolve_godot_resource(str(match.group("path") or ""))
            if resource_path and (repo_path / resource_path).is_file():
                script_paths.add(resource_path)
        return script_paths

    main_scene_value: str | None = None
    in_autoload_section = False
    for raw_line in manifest_text.splitlines():
        stripped_line = raw_line.strip()
        if not stripped_line or stripped_line.startswith(";"):
            continue
        if stripped_line.startswith("[") and stripped_line.endswith("]"):
            in_autoload_section = stripped_line.casefold() == "[autoload]"
            continue
        if stripped_line.startswith("run/main_scene="):
            main_scene_value = stripped_line.split("=", 1)[1]
            continue
        if not in_autoload_section:
            continue
        resource_path = _resolve_godot_resource(stripped_line)
        if resource_path is None or not (repo_path / resource_path).exists():
            continue
        if resource_path.endswith(".gd") and _is_operational_profile_entrypoint_candidate(
            resource_path,
            repo_path=repo_path,
        ):
            entrypoint_paths.add(resource_path)
        else:
            entrypoint_paths.update(_scene_script_paths(resource_path))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resource_path).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)

    if main_scene_value is not None:
        resolved_main_scene = _resolve_godot_resource(main_scene_value)
        if resolved_main_scene:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(resolved_main_scene).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
            if resolved_main_scene.endswith(".gd") and _is_operational_profile_entrypoint_candidate(
                resolved_main_scene,
                repo_path=repo_path,
            ):
                entrypoint_paths.add(resolved_main_scene)
            else:
                entrypoint_paths.update(_scene_script_paths(resolved_main_scene))

    for resolved_path in tuple(entrypoint_paths):
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
        resolved_parts = PurePosixPath(resolved_path).parts
        top_level_dir = resolved_parts[0] if resolved_parts else ""
        if top_level_dir:
            support_roots.add(top_level_dir)

    if support_roots:
        return entrypoint_paths, support_roots, config_paths

    for fallback_dir in ("src", "scripts", "addons", "autoload", "Scenes", "scenes"):
        candidate_dir = repository_service._normalize_repository_relative_path(
            str(project_dir / fallback_dir)
        )
        if candidate_dir and (repo_path / candidate_dir).is_dir():
            support_roots.add(candidate_dir)
    return entrypoint_paths, support_roots, config_paths


def _vhdl_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    config_paths = {normalized_path}
    support_roots = {
        str(project_dir)
        for project_dir in (project_dir,)
        if str(project_dir) not in {"", "."}
    }
    entrypoint_paths: set[str] = set()
    if tomllib is None:
        return entrypoint_paths, support_roots, config_paths
    try:
        payload = tomllib.loads(manifest_file.read_text(encoding="utf-8", errors="replace"))
    except (OSError, tomllib.TOMLDecodeError):
        payload = {}
    for library_config in payload.get("libraries", {}).values():
        if not isinstance(library_config, dict):
            continue
        for raw_path in library_config.get("files", ()):
            if not isinstance(raw_path, str):
                continue
            resolved_path = repository_service._normalize_repository_relative_path(
                str(project_dir / raw_path)
            )
            if not resolved_path or not (repo_path / resolved_path).is_file():
                continue
            if _probe_language_for_path(resolved_path, repo_path=repo_path) != "vhdl":
                continue
            basename = PurePosixPath(resolved_path).name.lower()
            if (
                _profile_path_tokens(resolved_path) & {"tb", "testbench"}
                or basename.endswith(("_tb.vhd", "_tb.vhdl", "_test.vhd", "_test.vhdl"))
            ):
                continue
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(resolved_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
            if _is_operational_profile_entrypoint_candidate(
                resolved_path,
                repo_path=repo_path,
            ):
                entrypoint_paths.add(resolved_path)
    if support_roots:
        return entrypoint_paths, support_roots, config_paths
    for fallback_dir in ("rtl", "src", "hdl", "vhdl", "tb", "sim"):
        candidate_dir = repository_service._normalize_repository_relative_path(
            str(project_dir / fallback_dir)
        )
        if candidate_dir and (repo_path / candidate_dir).is_dir():
            support_roots.add(candidate_dir)
    return entrypoint_paths, support_roots, config_paths


def _tcl_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    manifest_dir = PurePosixPath(normalized_path).parent
    config_paths = {normalized_path}
    support_roots = {
        str(manifest_dir)
        for manifest_dir in (manifest_dir,)
        if str(manifest_dir) not in {"", "."}
    }
    entrypoint_paths: set[str] = set()
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        manifest_text = ""

    file_target_re = re.compile(
        r"(?P<path>[A-Za-z0-9_./-]+\.(?:tcl|tm))\b",
        re.IGNORECASE,
    )
    for match in re.finditer(
        r"^\s*package\s+ifneeded\s+[^\n]+$",
        manifest_text,
        re.IGNORECASE | re.MULTILINE,
    ):
        for target_match in file_target_re.finditer(match.group(0)):
            raw_target = str(target_match.group("path") or "").strip()
            if not raw_target:
                continue
            resolved_path = repository_service._normalize_repository_relative_path(
                str(manifest_dir / raw_target)
            )
            if (
                not resolved_path
                or repository_service._is_test_path(resolved_path)
                or _is_non_operational_profile_path(resolved_path)
                or PurePosixPath(resolved_path).name.lower() == "pkgindex.tcl"
            ):
                continue
            if not (repo_path / resolved_path).is_file():
                continue
            entrypoint_paths.add(resolved_path)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(resolved_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)

    if entrypoint_paths:
        return entrypoint_paths, support_roots, config_paths

    project_root = repo_path / manifest_dir
    if not project_root.is_dir():
        return entrypoint_paths, support_roots, config_paths
    for extension in ("*.tcl", "*.tm"):
        for candidate in sorted(project_root.glob(extension)):
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                not relative_path
                or repository_service._is_test_path(relative_path)
                or _is_non_operational_profile_path(relative_path)
                or PurePosixPath(relative_path).name.lower() == "pkgindex.tcl"
            ):
                continue
            entrypoint_paths.add(relative_path)
    return entrypoint_paths, support_roots, config_paths


def _rpg_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    manifest_file = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        manifest_text = ""
    try:
        manifest_payload = json.loads(manifest_text) if manifest_text.strip() else {}
    except json.JSONDecodeError:
        manifest_payload = {}

    support_roots: set[str] = set()
    source_roots: list[str] = []

    def register_root(raw_value: str, *, source_root: bool) -> None:
        resolved_root = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_value)
        )
        if not resolved_root or _is_non_operational_profile_path(resolved_root):
            return
        candidate_root = repo_path / resolved_root
        if not candidate_root.exists():
            return
        support_roots.add(resolved_root)
        if source_root and candidate_root.is_dir() and resolved_root not in source_roots:
            source_roots.append(resolved_root)

    if str(project_dir) not in {"", "."}:
        register_root(".", source_root=True)
    for raw_include_path in manifest_payload.get("includePath", ()):
        if isinstance(raw_include_path, str) and raw_include_path.strip():
            register_root(raw_include_path.strip(), source_root=False)

    default_source_roots = (
        "QRPGLESRC",
        "QRPGSRC",
        "QSQLSRC",
        "programs",
        "src",
        "src/rpglesrc",
        "src/rpgsrc",
    )
    if PurePosixPath(normalized_path).name.lower() == ".ibmi.json":
        default_source_roots = (".", *default_source_roots)
    for root_value in default_source_roots:
        register_root(root_value, source_root=True)
    for root_value in (
        "QPROTOSRC",
        "includes",
        "include",
        "src/rpgleinc",
        "src/rpginc",
    ):
        register_root(root_value, source_root=False)

    entrypoint_paths: set[str] = set()
    for source_root in source_roots:
        source_path = repo_path / source_root
        if not source_path.is_dir():
            continue
        for pattern in ("*.rpg", "*.rpgle", "*.sqlrpg", "*.sqlrpgle", "*.rpginc", "*.rpgleinc"):
            for candidate_path in sorted(source_path.rglob(pattern)):
                relative_path = repository_service._normalize_repository_relative_path(
                    str(candidate_path.relative_to(repo_path))
                )
                if (
                    not relative_path
                    or repository_service._is_test_path(relative_path)
                    or _is_non_operational_profile_path(relative_path)
                ):
                    continue
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(relative_path).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
                if PurePosixPath(relative_path).suffix.lower() in {".rpginc", ".rpgleinc"}:
                    continue
                entrypoint_paths.add(relative_path)

    return entrypoint_paths, support_roots, config_paths


def _vbscript_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    try:
        text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set(), set(), {normalized_path}
    if not repository_service.vbscript_adapter.is_probable_vbscript_source(
        path=Path(normalized_path),
        text=text,
    ):
        return set(), set(), {normalized_path}
    project_dir = PurePosixPath(normalized_path).parent
    support_roots = {
        str(project_dir)
        for project_dir in (project_dir,)
        if str(project_dir) not in {"", "."}
    }
    for import_target in repository_service.vbscript_adapter.import_targets_for_text(
        path=PurePosixPath(normalized_path),
        text=text,
    ):
        resolved_path = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_path).parent / import_target)
        )
        if not resolved_path or repository_service._is_test_path(resolved_path):
            continue
        if _is_non_operational_profile_path(resolved_path):
            continue
        if not (repo_path / resolved_path).is_file():
            continue
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return {normalized_path}, support_roots, {normalized_path}


def _labview_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    manifest_file = repo_path / normalized_path
    try:
        text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set(), set(), config_paths
    if not repository_service.labview_adapter.is_probable_labview_source(
        path=Path(normalized_path),
        text=text,
    ):
        return set(), set(), config_paths

    project_dir = PurePosixPath(normalized_path).parent
    support_roots = {
        str(project_dir)
        for project_dir in (project_dir,)
        if str(project_dir) not in {"", "."}
    }
    entrypoint_paths: set[str] = set()

    for entry in repository_service.labview_adapter.project_item_entries(
        text,
        manifest_path=normalized_path,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
    ):
        target_path = repository_service._normalize_repository_relative_path(
            str(entry["target_file"])
        )
        if (
            not target_path
            or repository_service._is_test_path(target_path)
            or _is_non_operational_profile_path(target_path)
        ):
            continue
        if not (repo_path / target_path).is_file():
            continue
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(target_path).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
        if PurePosixPath(target_path).suffix.lower() == ".ctl":
            continue
        entrypoint_paths.add(target_path)

    if entrypoint_paths:
        return entrypoint_paths, support_roots, config_paths

    search_root = repo_path / project_dir
    for pattern in ("*.vi", "*.vim", "*.vit", "*.lvclass", "*.lvlib", "*.ctl"):
        for candidate_path in sorted(search_root.rglob(pattern)):
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate_path.relative_to(repo_path))
            )
            if (
                not relative_path
                or repository_service._is_test_path(relative_path)
                or _is_non_operational_profile_path(relative_path)
            ):
                continue
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(relative_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
            if PurePosixPath(relative_path).suffix.lower() == ".ctl":
                continue
            entrypoint_paths.add(relative_path)

    return entrypoint_paths, support_roots, config_paths


def _lisp_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    manifest_file = repo_path / normalized_path
    try:
        text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set(), set(), config_paths
    if not repository_service.lisp_adapter.is_probable_lisp_source(
        path=Path(normalized_path),
        text=text,
    ):
        return set(), set(), config_paths
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}lib",
        f"{root_prefix}systems",
        f"{root_prefix}lisp",
    }
    entrypoint_paths: set[str] = set()
    package_paths: list[str] = []
    component_paths: list[str] = []
    for entry in repository_service.lisp_adapter.project_component_entries(
        text,
        manifest_path=normalized_path,
    ):
        resolved_path = repository_service._normalize_repository_relative_path(str(entry["path"]))
        if not resolved_path or repository_service._is_test_path(resolved_path):
            continue
        if not (repo_path / resolved_path).is_file():
            continue
        component_paths.append(resolved_path)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
        basename = PurePosixPath(resolved_path).name.lower()
        if basename in {"package.lisp", "packages.lisp", "package.lsp", "packages.lsp"}:
            package_paths.append(resolved_path)
    if package_paths:
        entrypoint_paths.update(package_paths)
    if component_paths:
        entrypoint_paths.update(component_paths)
    if entrypoint_paths:
        return entrypoint_paths, support_roots, config_paths
    search_root = repo_path / project_dir
    for suffix in ("*.lisp", "*.lsp"):
        for candidate in sorted(search_root.rglob(suffix)):
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                relative_path
                and not repository_service._is_test_path(relative_path)
                and not _is_non_operational_profile_path(relative_path)
            ):
                entrypoint_paths.add(relative_path)
    return entrypoint_paths, support_roots, config_paths


def _puppet_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    project_dir = PurePosixPath(normalized_path).parent
    if _is_non_operational_project_path(str(project_dir)):
        return set(), set(), config_paths
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}manifests",
        f"{root_prefix}modules",
        f"{root_prefix}plans",
        f"{root_prefix}types",
        f"{root_prefix}functions",
        f"{root_prefix}tasks",
        f"{root_prefix}lib",
    }
    entrypoint_paths: set[str] = {
        f"{root_prefix}manifests/init.pp",
        f"{root_prefix}site.pp",
        f"{root_prefix}plans/init.pp",
    }
    search_root = repo_path / project_dir
    try:
        candidates = sorted(search_root.rglob("*.pp"))
    except OSError:
        candidates = []
    for candidate in candidates:
        try:
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
        except ValueError:
            continue
        if not relative_path or _is_non_operational_profile_path(relative_path):
            continue
        try:
            text = candidate.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.puppet_adapter.is_probable_puppet_source(
            path=Path(relative_path),
            text=text,
        ):
            continue
        entrypoint_paths.add(relative_path)
    return entrypoint_paths, support_roots, config_paths


def _hack_profile_hints_from_candidates(
    repo_path: Path,
    candidate_paths: list[str],
    *,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_manifest_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_manifest_path:
        return set(), set(), set()
    config_paths = {normalized_manifest_path}
    support_roots: set[str] = set()
    entrypoint_paths: set[str] = set()
    manifest_candidate = repo_path / normalized_manifest_path
    if manifest_candidate.is_file() and manifest_candidate.name.lower() in {
        "hhvm.autoload",
        "hh_autoload.json",
    }:
        try:
            roots = repository_service.hack_adapter.parse_hack_autoload_roots(
                manifest_candidate.read_text(encoding="utf-8", errors="replace")
            )
        except OSError:
            roots = ()
        for root in roots:
            normalized_root = repository_service._normalize_repository_relative_path(root)
            if normalized_root:
                support_roots.add(normalized_root)
    preferred_basenames = {
        "main.hack", "index.hack", "main.hh", "index.hh", "main.php", "index.php"
    }
    hack_files: list[str] = []
    for normalized_candidate in candidate_paths:
        if (
            not normalized_candidate
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "hack"
        ):
            continue
        hack_files.append(normalized_candidate)
        parent = PurePosixPath(normalized_candidate).parent
        if str(parent) not in {"", "."}:
            support_roots.add(str(parent.parts[0] if parent.parts else parent))
    non_test_hack_files = [
        path for path in hack_files if not repository_service._is_test_path(path)
    ]
    for candidate_path in non_test_hack_files:
        if PurePosixPath(candidate_path).name.lower() in preferred_basenames:
            entrypoint_paths.add(candidate_path)
    if not entrypoint_paths:
        entrypoint_paths.update(non_test_hack_files[:8] or hack_files[:8])
    return entrypoint_paths, support_roots, config_paths


def _emacslisp_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    manifest_file = repo_path / normalized_path
    try:
        text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set(), set(), config_paths
    if not repository_service.emacslisp_adapter.is_probable_emacslisp_source(
        path=Path(normalized_path),
        text=text,
    ):
        return set(), set(), config_paths
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        *(
            f"{root_prefix}{source_root}"
            for source_root in repository_service.emacslisp_adapter._EMACSLISP_SOURCE_ROOTS
        ),
    }
    entrypoint_paths: set[str] = set()
    seen_paths: set[str] = set()

    def _register_entrypoint(candidate_path: str) -> None:
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or normalized_candidate in seen_paths
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path)
            != "emacslisp"
        ):
            return
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            return
        seen_paths.add(normalized_candidate)
        entrypoint_paths.add(normalized_candidate)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)

    for entry in repository_service.emacslisp_adapter.cask_package_file_entries(text):
        _register_entrypoint(str(project_dir / entry))

    search_roots: list[Path] = [repo_path / project_dir]
    for source_root in repository_service.emacslisp_adapter._EMACSLISP_SOURCE_ROOTS:
        candidate_root = repo_path / project_dir / source_root
        if candidate_root.is_dir():
            search_roots.append(candidate_root)
    seen_search_roots: set[Path] = set()
    for search_root in search_roots:
        resolved_search_root = search_root.resolve()
        if not search_root.is_dir() or resolved_search_root in seen_search_roots:
            continue
        seen_search_roots.add(resolved_search_root)
        for candidate in sorted(search_root.rglob("*.el")):
            if not candidate.is_file() or candidate.is_symlink():
                continue
            _register_entrypoint(str(candidate.relative_to(repo_path)))
    return entrypoint_paths, support_roots, config_paths


def _vimscript_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    config_paths: set[str] = set()
    entrypoint_dirs = {"after", "colors", "compiler", "ftplugin", "indent", "plugin", "syntax"}
    support_dirs = entrypoint_dirs | {"autoload"}
    config_basenames = {".vimrc", "_vimrc", "gvimrc", "vimrc"}
    for candidate_path in candidate_file_paths:
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "vimscript"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts]
        basename = lowered_parts[-1]
        for index, part in enumerate(lowered_parts[:-1]):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        if basename in config_basenames:
            config_paths.add(normalized_candidate)
            entrypoint_paths.add(normalized_candidate)
            continue
        if any(part in entrypoint_dirs for part in lowered_parts[:-1]):
            entrypoint_paths.add(normalized_candidate)
            continue
        if (
            len(candidate_parts) == 1
            and PurePosixPath(normalized_candidate).suffix.lower() == ".vim"
        ):
            entrypoint_paths.add(normalized_candidate)
    return entrypoint_paths, support_roots, config_paths


def _autohotkey_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    config_paths: set[str] = set()
    support_dirs = {"lib", "include", "includes"}
    preferred_basenames = {"autoexec.ahk", "main.ahk", "index.ahk"}
    for candidate_path in candidate_file_paths:
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path)
            != "autohotkey"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts]
        basename = lowered_parts[-1]
        for index, part in enumerate(lowered_parts[:-1]):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        if basename in preferred_basenames or len(candidate_parts) == 1:
            entrypoint_paths.add(normalized_candidate)
            continue
        if not any(part in support_dirs for part in lowered_parts[:-1]):
            entrypoint_paths.add(normalized_candidate)
    return entrypoint_paths, support_roots, config_paths


def _autoit_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    config_paths: set[str] = set()
    support_dirs = {"include", "includes", "lib", "support"}
    preferred_basenames = {"autoit3.au3", "main.au3", "index.au3"}
    for candidate_path in candidate_file_paths:
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "autoit"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts]
        basename = lowered_parts[-1]
        for index, part in enumerate(lowered_parts[:-1]):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        if basename in preferred_basenames or len(candidate_parts) == 1:
            entrypoint_paths.add(normalized_candidate)
            continue
        if not any(part in support_dirs for part in lowered_parts[:-1]):
            entrypoint_paths.add(normalized_candidate)
    return entrypoint_paths, support_roots, config_paths


def _squirrel_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    squirrel_files: list[str] = []
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    support_dirs = {"code", "lib", "libs", "mods", "samples", "scripts", "src", "support", "vscripts"}
    preferred_basenames = {"index.nut", "init.nut", "main.nut"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "squirrel"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.squirrel_adapter.is_probable_squirrel_source(
            path=candidate_file,
            text=text,
        ):
            continue
        squirrel_files.append(normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts]
        basename = lowered_parts[-1]
        for index, part in enumerate(lowered_parts[:-1]):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        if basename in preferred_basenames or len(candidate_parts) == 1:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(squirrel_files)[:8])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _nushell_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    config_paths: set[str] = set()
    support_dirs = {"modules", "completions", "custom-completions", "scripts", "lib"}
    preferred_basenames = {"main.nu", "mod.nu"}
    config_basenames = {"config.nu", "env.nu"}
    for candidate_path in candidate_file_paths:
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "nushell"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts]
        basename = lowered_parts[-1]
        for index, part in enumerate(lowered_parts[:-1]):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        if basename in config_basenames:
            config_paths.add(normalized_candidate)
            support_roots.add("/".join(candidate_parts[:-1]))
            continue
        if basename in preferred_basenames or len(candidate_parts) == 1:
            entrypoint_paths.add(normalized_candidate)
            continue
        if not any(part in support_dirs for part in lowered_parts[:-1]):
            entrypoint_paths.add(normalized_candidate)
    return (
        entrypoint_paths,
        {root for root in support_roots if root},
        config_paths,
    )


def _fish_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    config_paths: set[str] = set()
    entrypoint_dirs = {"functions", "conf.d"}
    support_dirs = entrypoint_dirs | {"completions", "themes"}
    for candidate_path in candidate_file_paths:
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "fish"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts]
        for index, part in enumerate(lowered_parts[:-1]):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        if any(part in entrypoint_dirs for part in lowered_parts[:-1]):
            entrypoint_paths.add(normalized_candidate)
            continue
        if (
            len(candidate_parts) == 1
            and PurePosixPath(normalized_candidate).suffix.lower() == ".fish"
        ):
            entrypoint_paths.add(normalized_candidate)
    return entrypoint_paths, support_roots, config_paths


def _batchfile_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    entrypoint_dirs = {"bin", "cmd", "scripts", "tools"}
    support_dirs = entrypoint_dirs | {"build", "deploy", "install"}
    preferred_basenames = {
        "bootstrap.bat",
        "bootstrap.cmd",
        "build.bat",
        "build.cmd",
        "install.bat",
        "install.cmd",
        "main.bat",
        "main.cmd",
        "run.bat",
        "run.cmd",
        "setup.bat",
        "setup.cmd",
    }
    for candidate_path in candidate_file_paths:
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path)
            != "batchfile"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts]
        basename = lowered_parts[-1]
        for index, part in enumerate(lowered_parts[:-1]):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        if basename in preferred_basenames or len(candidate_parts) == 1:
            entrypoint_paths.add(normalized_candidate)
            continue
        if not any(part in support_dirs for part in lowered_parts[:-1]):
            entrypoint_paths.add(normalized_candidate)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _makefile_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    entrypoint_basenames = {"Makefile", "makefile", "GNUmakefile"}
    support_dirs = {"build", "config", "make", "mk", "rules", "scripts", "tools"}
    for candidate_path in candidate_file_paths:
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "makefile"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts]
        basename = candidate_parts[-1]
        for index, part in enumerate(lowered_parts[:-1]):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        if basename in entrypoint_basenames or len(candidate_parts) == 1:
            entrypoint_paths.add(normalized_candidate)
            continue
        if not any(part in support_dirs for part in lowered_parts[:-1]):
            entrypoint_paths.add(normalized_candidate)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _just_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    entrypoint_basenames = {"justfile", "Justfile", ".justfile"}
    support_dirs = {"build", "config", "just", "scripts", "tasks", "tools"}
    for candidate_path in candidate_file_paths:
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "just"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts]
        basename = candidate_parts[-1]
        for index, part in enumerate(lowered_parts[:-1]):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        if basename in entrypoint_basenames or len(candidate_parts) == 1:
            entrypoint_paths.add(normalized_candidate)
            continue
        if not any(part in support_dirs for part in lowered_parts[:-1]):
            entrypoint_paths.add(normalized_candidate)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _dockerfile_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    dockerfile_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    dependency_files: set[str] = set()
    support_dirs = {"build", "container", "containers", "docker", "images", "scripts", "tools"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate:
            continue
        candidate_file = repo_path / normalized_candidate
        if candidate_file.is_file() and not candidate_file.is_symlink():
            module_index.setdefault(normalized_candidate, normalized_candidate)
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "dockerfile"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.dockerfile_adapter.is_probable_dockerfile_source(
            path=candidate_file,
            text=text,
        ):
            continue
        dockerfile_files.append(normalized_candidate)
        for alias in repository_service.dockerfile_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in dockerfile_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.dockerfile_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if not dependency.target_file or dependency.target_file == normalized_candidate:
                continue
            dependency_files.add(dependency.target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(dependency.target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    for normalized_candidate in dockerfile_files:
        parent_parts = [part.lower() for part in PurePosixPath(normalized_candidate).parts[:-1]]
        if not any(part in support_dirs for part in parent_parts) or normalized_candidate in dependency_files:
            entrypoint_paths.add(normalized_candidate)
            continue
        if PurePosixPath(normalized_candidate).name.lower() in {"dockerfile", "containerfile"}:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(dockerfile_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _scss_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    scss_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "app.scss",
        "application.scss",
        "bootstrap.scss",
        "index.scss",
        "main.scss",
        "style.scss",
        "styles.scss",
        "theme.scss",
    }
    support_dirs = {"assets", "sass", "scss", "styles", "stylesheets"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "scss"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.scss_adapter.is_probable_scss_source(
            path=candidate_file,
            text=text,
        ):
            continue
        scss_files.append(normalized_candidate)
        for alias in repository_service.scss_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in scss_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.scss_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in scss_files:
        path = PurePosixPath(normalized_candidate)
        if (
            path.name.startswith("_")
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in scss_files
            if not PurePosixPath(normalized_candidate).name.startswith("_")
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _less_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    less_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "app.less",
        "application.less",
        "index.less",
        "main.less",
        "style.less",
        "styles.less",
        "theme.less",
        "variables.less",
    }
    support_dirs = {"assets", "less", "src", "styles", "stylesheets", "themes"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "less"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.less_adapter.is_probable_less_source(
            path=candidate_file,
            text=text,
        ):
            continue
        less_files.append(normalized_candidate)
        for alias in repository_service.less_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in less_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.less_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in less_files:
        path = PurePosixPath(normalized_candidate)
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(less_files)
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _stylus_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    stylus_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "app.styl",
        "application.styl",
        "index.styl",
        "main.styl",
        "style.styl",
        "styles.styl",
        "theme.styl",
        "variables.styl",
    }
    support_dirs = {"assets", "src", "styl", "stylus", "styles", "stylesheets", "themes"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "stylus"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.stylus_adapter.is_probable_stylus_source(
            path=candidate_file,
            text=text,
        ):
            continue
        stylus_files.append(normalized_candidate)
        for alias in repository_service.stylus_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in stylus_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.stylus_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in stylus_files:
        path = PurePosixPath(normalized_candidate)
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(stylus_files)
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _jinja_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    jinja_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "index.j2",
        "index.jinja",
        "index.jinja2",
        "main.j2",
        "main.jinja",
        "main.jinja2",
    }
    support_dirs = {"jinja", "jinja2", "partials", "roles", "templates", "views"}
    library_like_parts = {"include", "includes", "macros", "partials", "shared", "snippets"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "jinja"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.jinja_adapter.is_probable_jinja_source(
            path=candidate_file,
            text=text,
        ):
            continue
        jinja_files.append(normalized_candidate)
        for alias in repository_service.jinja_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in jinja_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.jinja_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in jinja_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or candidate_parts.intersection(library_like_parts)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in jinja_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(
                library_like_parts
            )
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _liquid_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    liquid_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "index.liquid",
        "main.liquid",
        "theme.liquid",
        "product.liquid",
        "collection.liquid",
        "article.liquid",
        "blog.liquid",
        "page.liquid",
    }
    support_dirs = {
        "includes",
        "layout",
        "layouts",
        "partials",
        "sections",
        "snippets",
        "templates",
        "_includes",
        "_layouts",
    }
    library_like_parts = {"includes", "partials", "snippets", "_includes"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "liquid"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.liquid_adapter.is_probable_liquid_source(
            path=candidate_file,
            text=text,
        ):
            continue
        liquid_files.append(normalized_candidate)
        for alias in repository_service.liquid_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in liquid_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.liquid_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in liquid_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or candidate_parts.intersection(library_like_parts)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in liquid_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(
                library_like_parts
            )
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _handlebars_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    handlebars_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "index.hbs",
        "default.hbs",
        "home.hbs",
        "post.hbs",
        "page.hbs",
        "tag.hbs",
        "author.hbs",
        "error.hbs",
    }
    support_dirs = {"components", "includes", "layouts", "partials", "templates", "views"}
    library_like_parts = {"components", "includes", "partials"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "handlebars"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.handlebars_adapter.is_probable_handlebars_source(
            path=candidate_file,
            text=text,
        ):
            continue
        handlebars_files.append(normalized_candidate)
        for alias in repository_service.handlebars_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in handlebars_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.handlebars_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in handlebars_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or candidate_parts.intersection(library_like_parts)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in handlebars_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(
                library_like_parts
            )
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _mustache_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    mustache_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "default.mustache",
        "error.mustache",
        "home.mustache",
        "index.mustache",
        "page.mustache",
        "post.mustache",
    }
    support_dirs = {"components", "includes", "layouts", "pages", "partials", "templates", "views"}
    library_like_parts = {"components", "includes", "partials"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "mustache"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.mustache_adapter.is_probable_mustache_source(
            path=candidate_file,
            text=text,
        ):
            continue
        mustache_files.append(normalized_candidate)
        for alias in repository_service.mustache_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in mustache_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.mustache_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in mustache_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or candidate_parts.intersection(library_like_parts)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in mustache_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(
                library_like_parts
            )
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _smarty_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    smarty_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "default.tpl",
        "home.tpl",
        "index.tpl",
        "layout.tpl",
        "page.tpl",
        "profiling.tpl",
    }
    support_dirs = {
        "_partials",
        "hooks",
        "layouts",
        "mails",
        "modules",
        "partials",
        "pdf",
        "templates",
        "themes",
        "views",
    }
    library_like_parts = {"_partials", "functions", "includes", "partials"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "smarty"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.smarty_adapter.is_probable_smarty_source(
            path=candidate_file,
            text=text,
        ):
            continue
        smarty_files.append(normalized_candidate)
        for alias in repository_service.smarty_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in smarty_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.smarty_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in smarty_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or candidate_parts.intersection(library_like_parts)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in smarty_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(
                library_like_parts
            )
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _graphviz_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    graphviz_files: list[str] = []
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    preferred_basenames = {
        "architecture.dot",
        "graph.dot",
        "index.dot",
        "main.dot",
        "overview.dot",
        "system.dot",
    }
    support_dirs = {"diagram", "diagrams", "dot", "dots", "graph", "graphs", "graphviz", "viz"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "graphviz"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.graphviz_adapter.is_probable_graphviz_source(
            path=candidate_file,
            text=text,
        ):
            continue
        graphviz_files.append(normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in graphviz_files:
        path = PurePosixPath(normalized_candidate)
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
        ):
            continue
        if path.name.lower() in preferred_basenames or path.parent.name.lower() in support_dirs:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(graphviz_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _mermaid_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    mermaid_files: list[str] = []
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    preferred_basenames = {
        "architecture.mmd",
        "diagram.mmd",
        "flowchart.mmd",
        "index.mmd",
        "main.mmd",
        "overview.mmd",
        "system.mmd",
    }
    support_dirs = {
        "architecture",
        "diagram",
        "diagrams",
        "docs",
        "flowcharts",
        "mermaid",
        "mmd",
        "viz",
    }
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "mermaid"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.mermaid_adapter.is_probable_mermaid_source(
            path=candidate_file,
            text=text,
        ):
            continue
        mermaid_files.append(normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in mermaid_files:
        path = PurePosixPath(normalized_candidate)
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
        ):
            continue
        if path.name.lower() in preferred_basenames or path.parent.name.lower() in support_dirs:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(mermaid_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _plantuml_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    plantuml_files: list[str] = []
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    preferred_basenames = {
        "architecture.puml",
        "c4.puml",
        "container.puml",
        "context.puml",
        "diagram.puml",
        "main.puml",
        "overview.puml",
        "system.puml",
    }
    support_dirs = {"architecture", "c4", "diagram", "diagrams", "docs", "plantuml", "puml", "uml", "viz"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if not normalized_candidate or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "plantuml":
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.plantuml_adapter.is_probable_plantuml_source(path=candidate_file, text=text):
            continue
        plantuml_files.append(normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(str(PurePosixPath(normalized_candidate).parent))
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in plantuml_files:
        path = PurePosixPath(normalized_candidate)
        if repository_service._is_test_path(normalized_candidate) or _is_non_operational_profile_path(normalized_candidate):
            continue
        if path.name.lower() in preferred_basenames or path.parent.name.lower() in support_dirs:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(plantuml_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _openqasm_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    openqasm_files: list[str] = []
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    preferred_basenames = {"adder.qasm", "circuit.qasm", "example.qasm", "main.qasm", "program.qasm", "qft.qasm", "teleport.qasm"}
    support_dirs = {"circuits", "examples", "openqasm", "qasm", "spec", "tests"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if not normalized_candidate or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "openqasm":
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.openqasm_adapter.is_probable_openqasm_source(path=candidate_file, text=text):
            continue
        openqasm_files.append(normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(str(PurePosixPath(normalized_candidate).parent))
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in openqasm_files:
        path = PurePosixPath(normalized_candidate)
        if repository_service._is_test_path(normalized_candidate) or _is_non_operational_profile_path(normalized_candidate):
            continue
        if path.name.lower() in preferred_basenames or path.parent.name.lower() in support_dirs:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(openqasm_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _nunjucks_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    nunjucks_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "index.njk",
        "index.nunj",
        "index.nunjucks",
        "main.njk",
        "main.nunj",
        "main.nunjucks",
        "base.njk",
        "layout.njk",
    }
    support_dirs = {
        "_components",
        "_includes",
        "_layouts",
        "components",
        "includes",
        "layouts",
        "partials",
        "snippets",
        "templates",
        "views",
    }
    library_like_parts = {"_components", "_includes", "components", "includes", "partials", "snippets"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "nunjucks"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.nunjucks_adapter.is_probable_nunjucks_source(
            path=candidate_file,
            text=text,
        ):
            continue
        nunjucks_files.append(normalized_candidate)
        for alias in repository_service.nunjucks_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in nunjucks_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.nunjucks_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in nunjucks_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or candidate_parts.intersection(library_like_parts)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in nunjucks_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(
                library_like_parts
            )
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _twig_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    twig_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "base.html.twig",
        "default.html.twig",
        "index.html.twig",
        "layout.html.twig",
        "page.html.twig",
    }
    support_dirs = {
        "_components",
        "_includes",
        "_layouts",
        "blocks",
        "components",
        "includes",
        "layouts",
        "macros",
        "pages",
        "partials",
        "templates",
        "themes",
        "views",
    }
    library_like_parts = {
        "_components",
        "_includes",
        "blocks",
        "components",
        "includes",
        "macros",
        "partials",
    }
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "twig":
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.twig_adapter.is_probable_twig_source(path=candidate_file, text=text):
            continue
        twig_files.append(normalized_candidate)
        for alias in repository_service.twig_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in twig_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.twig_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in twig_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or candidate_parts.intersection(library_like_parts)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in twig_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(
                library_like_parts
            )
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _haml_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    haml_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "application.html.haml",
        "index.html.haml",
        "home.html.haml",
        "show.html.haml",
        "page.html.haml",
    }
    support_dirs = {"app", "views", "layouts", "pages", "partials", "shared", "components", "templates"}
    library_like_parts = {"partials", "shared", "components"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if not normalized_candidate or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "haml":
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.haml_adapter.is_probable_haml_source(path=candidate_file, text=text):
            continue
        haml_files.append(normalized_candidate)
        for alias in repository_service.haml_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in haml_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.haml_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in haml_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or candidate_parts.intersection(library_like_parts)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in haml_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(
                library_like_parts
            )
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _slim_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    slim_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "application.html.slim",
        "index.html.slim",
        "home.html.slim",
        "show.html.slim",
        "page.html.slim",
    }
    support_dirs = {"app", "views", "layouts", "pages", "partials", "shared", "components", "templates"}
    library_like_parts = {"partials", "shared", "components"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if not normalized_candidate or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "slim":
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.slim_adapter.is_probable_slim_source(path=candidate_file, text=text):
            continue
        slim_files.append(normalized_candidate)
        for alias in repository_service.slim_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in slim_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.slim_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in slim_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or candidate_parts.intersection(library_like_parts)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in slim_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(
                library_like_parts
            )
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _erb_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    erb_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "application.html.erb",
        "index.html.erb",
        "home.html.erb",
        "show.html.erb",
        "page.html.erb",
    }
    support_dirs = {"app", "views", "layouts", "pages", "partials", "shared", "components", "templates"}
    library_like_parts = {"partials", "shared", "components"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if not normalized_candidate or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "erb":
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.erb_adapter.is_probable_erb_source(path=candidate_file, text=text):
            continue
        erb_files.append(normalized_candidate)
        for alias in repository_service.erb_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in erb_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.erb_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in erb_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or candidate_parts.intersection(library_like_parts)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in erb_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(
                library_like_parts
            )
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _pug_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    pug_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {"index.pug", "index.jade", "layout.pug", "layout.jade", "default.pug", "default.jade"}
    support_dirs = {"components", "includes", "layouts", "mixins", "pages", "partials", "templates", "views"}
    library_like_parts = {"components", "includes", "mixins", "partials"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if not normalized_candidate or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "pug":
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.pug_adapter.is_probable_pug_source(path=candidate_file, text=text):
            continue
        pug_files.append(normalized_candidate)
        for alias in repository_service.pug_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(str(PurePosixPath(normalized_candidate).parent))
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in pug_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.pug_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in pug_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or candidate_parts.intersection(library_like_parts)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in pug_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(library_like_parts)
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(str(PurePosixPath(imported_file).parent))
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _ejs_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    ejs_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "index.ejs",
        "layout.ejs",
        "default.ejs",
        "home.ejs",
        "page.ejs",
        "error.ejs",
    }
    support_dirs = {"components", "includes", "layouts", "pages", "partials", "templates", "views"}
    library_like_parts = {"components", "includes", "partials"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "ejs":
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.ejs_adapter.is_probable_ejs_source(path=candidate_file, text=text):
            continue
        ejs_files.append(normalized_candidate)
        for alias in repository_service.ejs_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in ejs_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.ejs_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in ejs_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or candidate_parts.intersection(library_like_parts)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in ejs_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(
                library_like_parts
            )
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _blade_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    blade_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "app.blade.php",
        "home.blade.php",
        "index.blade.php",
        "layout.blade.php",
        "welcome.blade.php",
    }
    support_dirs = {
        "components",
        "includes",
        "layouts",
        "partials",
        "resources",
        "sections",
        "views",
    }
    library_like_parts = {"components", "includes", "partials"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "blade"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.blade_adapter.is_probable_blade_source(
            path=candidate_file,
            text=text,
        ):
            continue
        blade_files.append(normalized_candidate)
        for alias in repository_service.blade_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in blade_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.blade_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in blade_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or candidate_parts.intersection(library_like_parts)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in blade_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(
                library_like_parts
            )
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _vue_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    vue_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {"App.vue", "app.vue", "Main.vue", "main.vue", "Index.vue", "index.vue"}
    support_dirs = {"components", "composables", "layouts", "pages", "views"}
    library_like_parts = {"components", "composables", "layouts"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "vue":
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.vue_adapter.is_probable_vue_source(path=candidate_file, text=text):
            continue
        vue_files.append(normalized_candidate)
        for alias in repository_service.vue_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in vue_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.vue_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in vue_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or candidate_parts.intersection(library_like_parts)
        ):
            continue
        if path.name in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in vue_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(
                library_like_parts
            )
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _svelte_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    svelte_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "App.svelte",
        "app.svelte",
        "+page.svelte",
        "+layout.svelte",
        "+error.svelte",
    }
    support_dirs = {"src", "lib", "routes", "components"}
    library_like_parts = {"lib", "components"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "svelte"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.svelte_adapter.is_probable_svelte_source(
            path=candidate_file,
            text=text,
        ):
            continue
        svelte_files.append(normalized_candidate)
        for alias in repository_service.svelte_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in svelte_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.svelte_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in svelte_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or candidate_parts.intersection(library_like_parts)
        ):
            continue
        if path.name in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in svelte_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(
                library_like_parts
            )
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _astro_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    astro_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {"index.astro", "Index.astro", "404.astro"}
    support_dirs = {"src", "components", "layouts", "pages", "content"}
    library_like_parts = {"components", "layouts", "content"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if not normalized_candidate or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "astro":
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.astro_adapter.is_probable_astro_source(path=candidate_file, text=text):
            continue
        astro_files.append(normalized_candidate)
        for alias in repository_service.astro_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(str(PurePosixPath(normalized_candidate).parent))
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in astro_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.astro_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in astro_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if repository_service._is_test_path(normalized_candidate) or _is_non_operational_profile_path(normalized_candidate) or candidate_parts.intersection(library_like_parts):
            continue
        if path.name in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in astro_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(library_like_parts)
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(str(PurePosixPath(imported_file).parent))
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _robotframework_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    robot_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    support_basenames = {"resource.robot", "common.resource", "keywords.resource", "variables.resource"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if not normalized_candidate or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "robotframework":
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.robotframework_adapter.is_probable_robotframework_source(path=candidate_file, text=text):
            continue
        robot_files.append(normalized_candidate)
        for alias in repository_service.robotframework_adapter.module_aliases_for_path(root_path=repo_path, file_path=normalized_candidate, stable_identifier=repository_service._stable_identifier):
            module_index.setdefault(alias, normalized_candidate)
        parent_dir = repository_service._normalize_repository_relative_path(str(PurePosixPath(normalized_candidate).parent))
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in robot_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.robotframework_adapter.parse_dependencies_only(normalized_candidate, text, module_index, stable_identifier=repository_service._stable_identifier, normalize_repository_relative_path=repository_service._normalize_repository_relative_path, resolve_suffix_match=repository_service._resolve_suffix_match):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in robot_files:
        path = PurePosixPath(normalized_candidate)
        if path.suffix.lower() != ".robot" or normalized_candidate in imported_files or path.name.lower() in support_basenames:
            continue
        entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(path for path in robot_files if PurePosixPath(path).suffix.lower() == ".robot"))
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(str(PurePosixPath(imported_file).parent))
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _typst_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    typst_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    config_paths: set[str] = set()
    preferred_basenames = {
        "article.typ",
        "book.typ",
        "index.typ",
        "main.typ",
        "paper.typ",
        "presentation.typ",
        "report.typ",
        "slides.typ",
        "thesis.typ",
    }
    support_dirs = {
        "chapters",
        "content",
        "docs",
        "document",
        "documents",
        "figures",
        "images",
        "layouts",
        "packages",
        "shared",
        "styles",
        "templates",
        "themes",
    }
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate:
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        candidate_name = PurePosixPath(normalized_candidate).name.lower()
        if candidate_name in repository_service.typst_adapter.TYPST_CONFIG_BASENAMES:
            if repository_service.typst_adapter.is_probable_typst_config(
                path=candidate_file,
                text=text,
            ):
                config_paths.add(normalized_candidate)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(normalized_candidate).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
            continue
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "typst"
        ):
            continue
        if not repository_service.typst_adapter.is_probable_typst_source(
            path=candidate_file,
            text=text,
        ):
            continue
        typst_files.append(normalized_candidate)
        for alias in repository_service.typst_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in typst_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.typst_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in typst_files:
        path = PurePosixPath(normalized_candidate)
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(typst_files)[:12])
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _tex_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    tex_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    config_paths: set[str] = set()
    preferred_basenames = {
        "article.tex",
        "cv.tex",
        "index.tex",
        "main.tex",
        "paper.tex",
        "presentation.tex",
        "report.tex",
        "resume.tex",
        "slides.tex",
        "thesis.tex",
    }
    support_dirs = {
        "appendix",
        "appendices",
        "chapter",
        "chapters",
        "content",
        "figures",
        "images",
        "partials",
        "section",
        "sections",
        "shared",
        "style",
        "styles",
        "template",
        "templates",
    }
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate:
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        candidate_name = PurePosixPath(normalized_candidate).name.lower()
        if candidate_name in repository_service.tex_adapter.TEX_CONFIG_BASENAMES:
            if repository_service.tex_adapter.is_probable_tex_config(
                path=candidate_file,
                text=text,
            ):
                config_paths.add(normalized_candidate)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(normalized_candidate).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
            continue
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "tex"
        ):
            continue
        if not repository_service.tex_adapter.is_probable_tex_source(
            path=candidate_file,
            text=text,
        ):
            continue
        tex_files.append(normalized_candidate)
        for alias in repository_service.tex_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in tex_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.tex_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(dependency.target_file).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
    for normalized_candidate in tex_files:
        path = PurePosixPath(normalized_candidate)
        if path.suffix.lower() not in {".tex", ".ltx"}:
            continue
        candidate_parts = [part.lower() for part in path.parts[:-1]]
        if path.name.lower() in preferred_basenames:
            entrypoint_paths.add(normalized_candidate)
            continue
        if normalized_candidate not in imported_files and not any(
            part in support_dirs for part in candidate_parts
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        tex_document_files = sorted(
            normalized_candidate
            for normalized_candidate in tex_files
            if PurePosixPath(normalized_candidate).suffix.lower() in {".tex", ".ltx"}
        )
        entrypoint_paths.update(tex_document_files[:12] or sorted(tex_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _rst_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    rst_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {"contents.rst", "guide.rst", "index.rst", "readme.rst", "reference.rst"}
    support_dirs = {
        "api",
        "doc",
        "docs",
        "documentation",
        "guide",
        "guides",
        "howto",
        "includes",
        "reference",
        "references",
        "source",
        "tutorial",
        "tutorials",
    }
    library_like_parts = {"_includes", "includes", "snippets"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path_for_ecosystems(
                normalized_candidate,
                ecosystems={"rst"},
                repo_path=repo_path,
            )
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "rst"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.rst_adapter.is_probable_rst_source(path=candidate_file, text=text):
            continue
        rst_files.append(normalized_candidate)
        for alias in repository_service.rst_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(str(PurePosixPath(normalized_candidate).parent))
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in rst_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.rst_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
                parent_dir = repository_service._normalize_repository_relative_path(str(PurePosixPath(dependency.target_file).parent))
                if parent_dir:
                    support_roots.add(parent_dir)
    for normalized_candidate in rst_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if candidate_parts.intersection(library_like_parts):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        rst_document_files = sorted(
            normalized_candidate for normalized_candidate in rst_files if PurePosixPath(normalized_candidate).name.lower() not in {"conf.py"}
        )
        entrypoint_paths.update(rst_document_files[:12] or sorted(rst_files)[:12])
    documentation_roots = {
        root
        for root in support_roots
        if PurePosixPath(root).name.lower() in support_dirs
    }
    if documentation_roots:
        support_roots = {
            root
            for root in support_roots
            if not any(
                root != documentation_root
                and root.startswith(f"{documentation_root}/")
                for documentation_root in documentation_roots
            )
        }
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _asciidoc_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    asciidoc_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {
        "contents.adoc",
        "contents.asciidoc",
        "guide.adoc",
        "guide.asciidoc",
        "index.adoc",
        "index.asciidoc",
        "readme.adoc",
        "readme.asciidoc",
        "reference.adoc",
        "reference.asciidoc",
    }
    support_dirs = {
        "api",
        "doc",
        "docs",
        "documentation",
        "guide",
        "guides",
        "howto",
        "includes",
        "modules",
        "partials",
        "reference",
        "references",
        "source",
        "tutorial",
        "tutorials",
    }
    library_like_parts = {"_includes", "attachments", "examples", "includes", "partials", "snippets"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path_for_ecosystems(
                normalized_candidate,
                ecosystems={"asciidoc"},
                repo_path=repo_path,
            )
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "asciidoc"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.asciidoc_adapter.is_probable_asciidoc_source(
            path=candidate_file,
            text=text,
        ):
            continue
        asciidoc_files.append(normalized_candidate)
        for alias in repository_service.asciidoc_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    documentation_roots = {
        root for root in support_roots if PurePosixPath(root).name.lower() in support_dirs
    }
    if documentation_roots:
        support_roots = {
            root
            for root in support_roots
            if not any(
                root != documentation_root
                and root.startswith(f"{documentation_root}/")
                for documentation_root in documentation_roots
            )
        }
    for normalized_candidate in asciidoc_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.asciidoc_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(dependency.target_file).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if candidate_parts.intersection(library_like_parts):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(asciidoc_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _org_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    org_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {
        "contents.org",
        "guide.org",
        "index.org",
        "manual.org",
        "readme.org",
        "reference.org",
    }
    support_dirs = {
        "doc",
        "docs",
        "documentation",
        "guide",
        "guides",
        "includes",
        "manual",
        "manuals",
        "org",
        "reference",
        "references",
        "tutorial",
        "tutorials",
        "worg",
    }
    library_like_parts = {"_includes", "includes", "snippets", "styles"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path_for_ecosystems(
                normalized_candidate,
                ecosystems={"org"},
                repo_path=repo_path,
            )
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "org"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.org_adapter.is_probable_org_source(path=candidate_file, text=text):
            continue
        org_files.append(normalized_candidate)
        for alias in repository_service.org_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    documentation_roots = {
        root for root in support_roots if PurePosixPath(root).name.lower() in support_dirs
    }
    if documentation_roots:
        support_roots = {
            root
            for root in support_roots
            if not any(
                root != documentation_root
                and root.startswith(f"{documentation_root}/")
                for documentation_root in documentation_roots
            )
        }
    for normalized_candidate in org_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.org_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(dependency.target_file).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if candidate_parts.intersection(library_like_parts):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(org_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _gherkin_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    gherkin_files: list[str] = []
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    preferred_basenames = {
        "index.feature",
        "login.feature",
        "readme.feature",
    }
    support_dirs = {"acceptance", "bdd", "feature", "features", "spec", "specs"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path_for_ecosystems(
                normalized_candidate,
                ecosystems={"gherkin"},
                repo_path=repo_path,
            )
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "gherkin"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.gherkin_adapter.is_probable_gherkin_source(
            path=candidate_file,
            text=text,
        ):
            continue
        gherkin_files.append(normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
        if PurePosixPath(normalized_candidate).name.lower() in preferred_basenames:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(gherkin_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _antlr_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    antlr_files: list[str] = []
    module_index: dict[str, str] = {}
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    preferred_basenames = {"grammar.g4", "index.g4", "lexer.g4", "parser.g4"}
    support_dirs = {"antlr", "antlr4", "grammar", "grammars", "lexer", "lexers", "parser", "parsers", "syntax"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path_for_ecosystems(
                normalized_candidate,
                ecosystems={"antlr"},
                repo_path=repo_path,
            )
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "antlr"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.antlr_adapter.is_probable_antlr_source(path=candidate_file, text=text):
            continue
        antlr_files.append(normalized_candidate)
        for alias in repository_service.antlr_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in antlr_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.antlr_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in antlr_files:
        path = PurePosixPath(normalized_candidate)
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(antlr_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _supplement_candidate_file_paths_for_suffix_roots(
    *,
    repo_path: Path,
    candidate_file_paths: list[str],
    suffixes: set[str],
    root_names: tuple[str, ...],
    max_extra_files: int,
) -> list[str]:
    normalized_suffixes = {suffix.lower() for suffix in suffixes}
    merged_paths = list(dict.fromkeys(candidate_file_paths))
    seen_paths = set(merged_paths)
    extra_files = 0
    for root_name in root_names:
        normalized_root = repository_service._normalize_repository_relative_path(root_name)
        if not normalized_root:
            continue
        root_path = repo_path / normalized_root
        if not root_path.is_dir():
            continue
        for candidate_file in sorted(root_path.rglob("*")):
            if extra_files >= max_extra_files:
                return merged_paths
            if not candidate_file.is_file() or candidate_file.is_symlink():
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate_file.relative_to(repo_path))
            )
            if (
                not relative_path
                or relative_path in seen_paths
                or repository_service._is_test_path(relative_path)
                or _is_non_operational_profile_path(relative_path)
                or PurePosixPath(relative_path).suffix.lower() not in normalized_suffixes
            ):
                continue
            merged_paths.append(relative_path)
            seen_paths.add(relative_path)
            extra_files += 1
    return merged_paths


def _move_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    move_files: list[str] = []
    module_index: dict[str, str] = {}
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    config_paths: set[str] = set()
    preferred_basenames = {"main.move", "lib.move", "script.move"}
    support_dirs = {"contracts", "examples", "move", "script", "scripts", "source", "sources"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if not normalized_candidate or repository_service._is_test_path(normalized_candidate):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if candidate_file.name.lower() in repository_service.move_adapter.MOVE_CONFIG_BASENAMES:
            if repository_service.move_adapter.is_probable_move_config(path=candidate_file, text=text):
                config_paths.add(normalized_candidate)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(normalized_candidate).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
            continue
        if (
            _is_non_operational_profile_path_for_ecosystems(
                normalized_candidate,
                ecosystems={"move"},
                repo_path=repo_path,
            )
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "move"
            or not repository_service.move_adapter.is_probable_move_source(path=candidate_file, text=text)
        ):
            continue
        move_files.append(normalized_candidate)
        for alias in repository_service.move_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in move_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.move_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(dependency.target_file).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
    for normalized_candidate in move_files:
        path = PurePosixPath(normalized_candidate)
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(move_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _rescript_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    rescript_files: list[str] = []
    module_index: dict[str, str] = {}
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    config_paths: set[str] = set()
    preferred_basenames = {"main.res", "index.res", "app.res", "lib.res"}
    support_dirs = {"src", "lib", "examples", "scripts"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if not normalized_candidate:
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if candidate_file.name.lower() in repository_service.rescript_adapter.RESCRIPT_CONFIG_BASENAMES:
            if repository_service.rescript_adapter.is_probable_rescript_config(
                path=candidate_file,
                text=text,
            ):
                config_paths.add(normalized_candidate)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(normalized_candidate).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
            continue
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path_for_ecosystems(
                normalized_candidate,
                ecosystems={"rescript"},
                repo_path=repo_path,
            )
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "rescript"
            or not repository_service.rescript_adapter.is_probable_rescript_source(
                path=candidate_file,
                text=text,
            )
        ):
            continue
        rescript_files.append(normalized_candidate)
        for alias in repository_service.rescript_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in rescript_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.rescript_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(dependency.target_file).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
    for normalized_candidate in rescript_files:
        path = PurePosixPath(normalized_candidate)
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(rescript_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _roc_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    roc_files: list[str] = []
    module_index: dict[str, str] = {}
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    excluded_parts = {"fixture", "fixtures", "snapshot", "snapshots", "test", "tests"}
    preferred_basenames = {"app.roc", "build.roc", "main.roc"}
    support_dirs = {"app", "apps", "ci", "example", "examples", "platform", "src"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if not normalized_candidate:
            continue
        path = PurePosixPath(normalized_candidate)
        if {part.lower() for part in path.parts} & excluded_parts:
            continue
        candidate_file = repo_path / normalized_candidate
        if (
            not candidate_file.is_file()
            or candidate_file.is_symlink()
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "roc"
        ):
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.roc_adapter.is_probable_roc_source(path=candidate_file, text=text):
            continue
        roc_files.append(normalized_candidate)
        for alias in repository_service.roc_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = path.parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(str(path.parent))
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in roc_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.roc_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(dependency.target_file).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
    for normalized_candidate in roc_files:
        path = PurePosixPath(normalized_candidate)
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(roc_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _modelica_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    modelica_files: list[str] = []
    module_index: dict[str, str] = {}
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    excluded_parts = {
        "benchmark",
        "benchmarks",
        "doc",
        "docs",
        "example",
        "examples",
        "fixture",
        "fixtures",
        "sample",
        "samples",
        "snapshot",
        "snapshots",
        "test",
        "tests",
        "testsuite",
        "tutorial",
        "tutorials",
    }
    preferred_basenames = {"main.mo", "package.mo"}
    support_dirs = {"library", "libraries", "modelica", "models", "package", "packages", "src"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if not normalized_candidate:
            continue
        path = PurePosixPath(normalized_candidate)
        if {part.lower() for part in path.parts} & excluded_parts:
            continue
        candidate_file = repo_path / normalized_candidate
        if (
            not candidate_file.is_file()
            or candidate_file.is_symlink()
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "modelica"
        ):
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.modelica_adapter.is_probable_modelica_source(
            path=candidate_file,
            text=text,
        ):
            continue
        modelica_files.append(normalized_candidate)
        for alias in repository_service.modelica_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = path.parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(str(path.parent))
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in modelica_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.modelica_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(dependency.target_file).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
    for normalized_candidate in modelica_files:
        path = PurePosixPath(normalized_candidate)
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(modelica_files)[:16])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _cython_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    cython_files: list[str] = []
    pyx_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {"__init__.pyx", "core.pyx", "main.pyx"}
    library_like_parts = {"include", "includes", "lib", "libs", "tests", "vendor"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "cython"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.cython_adapter.is_probable_cython_source(
            path=candidate_file,
            text=text,
        ):
            continue
        cython_files.append(normalized_candidate)
        if PurePosixPath(normalized_candidate).suffix.lower() == ".pyx":
            pyx_files.append(normalized_candidate)
        for alias in repository_service.cython_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in cython_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.cython_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if not dependency.target_file or dependency.target_file == normalized_candidate:
                continue
            imported_files.add(dependency.target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(dependency.target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    for normalized_candidate in pyx_files:
        candidate_name = PurePosixPath(normalized_candidate).name
        candidate_parts = [part.lower() for part in PurePosixPath(normalized_candidate).parts[:-1]]
        if candidate_name in preferred_basenames:
            entrypoint_paths.add(normalized_candidate)
            continue
        if normalized_candidate not in imported_files and not any(
            part in library_like_parts for part in candidate_parts
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(pyx_files or cython_files)[:8])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _stan_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    stan_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {"main.stan", "model.stan"}
    library_like_parts = {"functions", "include", "includes", "lib", "libs", "test", "tests"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "stan"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.stan_adapter.is_probable_stan_source(
            path=candidate_file,
            text=text,
        ):
            continue
        stan_files.append(normalized_candidate)
        for alias in repository_service.stan_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in stan_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.stan_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if not dependency.target_file or dependency.target_file == normalized_candidate:
                continue
            imported_files.add(dependency.target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(dependency.target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    for normalized_candidate in stan_files:
        candidate_name = PurePosixPath(normalized_candidate).name.lower()
        candidate_parts = [part.lower() for part in PurePosixPath(normalized_candidate).parts[:-1]]
        if candidate_name in preferred_basenames:
            entrypoint_paths.add(normalized_candidate)
            continue
        if normalized_candidate not in imported_files and not any(
            part in library_like_parts for part in candidate_parts
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(stan_files)[:8])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _protobuf_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    protobuf_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    config_paths: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {"api.proto", "main.proto", "service.proto"}
    library_like_parts = {
        "buf",
        "google",
        "internal",
        "proto",
        "protos",
        "schema",
        "schemas",
        "test",
        "tests",
        "third_party",
        "vendor",
    }
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate or repository_service._is_test_path(normalized_candidate):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        candidate_name = PurePosixPath(normalized_candidate).name.lower()
        if candidate_name in repository_service.protobuf_adapter.PROTOBUF_CONFIG_BASENAMES:
            if repository_service.protobuf_adapter.is_probable_protobuf_config(
                path=candidate_file,
                text=text,
            ):
                config_paths.add(normalized_candidate)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(normalized_candidate).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
            continue
        if (
            _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "protobuf"
            or not repository_service.protobuf_adapter.is_probable_protobuf_source(
                path=candidate_file,
                text=text,
            )
        ):
            continue
        protobuf_files.append(normalized_candidate)
        for alias in repository_service.protobuf_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in protobuf_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.protobuf_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if not dependency.target_file or dependency.target_file == normalized_candidate:
                continue
            imported_files.add(dependency.target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(dependency.target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    for normalized_candidate in protobuf_files:
        candidate_name = PurePosixPath(normalized_candidate).name.lower()
        candidate_parts = [part.lower() for part in PurePosixPath(normalized_candidate).parts[:-1]]
        if candidate_name in preferred_basenames:
            entrypoint_paths.add(normalized_candidate)
            continue
        if normalized_candidate not in imported_files and not any(
            part in library_like_parts for part in candidate_parts
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(protobuf_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _qml_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    qml_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    config_paths: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {"Main.qml", "main.qml", "App.qml", "Application.qml"}
    library_like_parts = {"components", "controls", "lib", "libs", "modules", "shared", "widgets"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "qml"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.qml_adapter.is_probable_qml_source(path=candidate_file, text=text):
            continue
        qml_files.append(normalized_candidate)
        if PurePosixPath(normalized_candidate).name.lower() == "qmldir":
            config_paths.add(normalized_candidate)
        for alias in repository_service.qml_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in qml_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.qml_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if not dependency.target_file or dependency.target_file == normalized_candidate:
                continue
            imported_files.add(dependency.target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(dependency.target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    for normalized_candidate in qml_files:
        candidate_name = PurePosixPath(normalized_candidate).name
        candidate_parts = [part.lower() for part in PurePosixPath(normalized_candidate).parts[:-1]]
        if candidate_name.lower() == "qmldir":
            continue
        if candidate_name in preferred_basenames:
            entrypoint_paths.add(normalized_candidate)
            continue
        if normalized_candidate not in imported_files and not any(
            part in library_like_parts for part in candidate_parts
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            path for path in sorted(qml_files)[:8] if PurePosixPath(path).name.lower() != "qmldir"
        )
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _rego_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    config_paths: set[str] = set()
    rego_files: list[str] = []
    file_texts: dict[str, str] = {}
    module_index: dict[str, str] = {}
    preferred_basenames = {"allow.rego", "deny.rego", "library.rego", "main.rego", "policy.rego"}
    support_dir_names = {"inputs", "lib", "libs", "policies", "policy", "rules"}

    def _is_rego_test_path(path: str) -> bool:
        candidate = PurePosixPath(path)
        stem = candidate.stem.lower()
        return (
            repository_service._is_test_path(path)
            or stem.startswith("test")
            or stem.endswith("_test")
            or ".test." in path.lower()
        )

    for candidate_path in candidate_file_paths:
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _is_rego_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "rego"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rego_files.append(normalized_candidate)
        file_texts[normalized_candidate] = text
        for alias in repository_service.rego_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts]
        for index, part in enumerate(lowered_parts[:-1]):
            if part in support_dir_names:
                support_roots.add("/".join(candidate_parts[: index + 1]))

    imported_targets: set[str] = set()
    for normalized_candidate in rego_files:
        for import_target, _alias, _line in repository_service.rego_adapter.parse_import_statements(
            file_texts[normalized_candidate]
        ):
            target_file = repository_service.rego_adapter.resolve_import(
                import_target,
                module_index,
                normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
                resolve_suffix_match=repository_service._resolve_suffix_match,
            )
            if not target_file or target_file == normalized_candidate:
                continue
            imported_targets.add(target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)

    for normalized_candidate in rego_files:
        if normalized_candidate in imported_targets:
            continue
        basename = PurePosixPath(normalized_candidate).name.lower()
        if basename in preferred_basenames or len(PurePosixPath(normalized_candidate).parts) <= 2:
            entrypoint_paths.add(normalized_candidate)
            continue
        candidate_parts = [part.lower() for part in PurePosixPath(normalized_candidate).parts[:-1]]
        if not any(part in {"inputs", "lib", "libs", "rules"} for part in candidate_parts):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(rego_files)[:8])
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _yara_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    yara_files: list[str] = []
    module_index: dict[str, str] = {}
    imported_files: set[str] = set()
    support_roots: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {"index.yar", "index.yara"}

    def _is_yara_test_path(path: str) -> bool:
        pure_path = PurePosixPath(path)
        stem = pure_path.stem.lower()
        return (
            repository_service._is_test_path(path)
            or stem.startswith("test")
            or stem.endswith("_test")
            or ".test." in pure_path.name.lower()
        )

    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _is_yara_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "yara"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.yara_adapter.is_probable_yara_source(
            path=candidate_file,
            text=text,
        ):
            continue
        yara_files.append(normalized_candidate)
        for alias in repository_service.yara_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)

    for normalized_candidate in yara_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for include_target, _line in repository_service.yara_adapter.parse_include_statements(text):
            target_file = repository_service.yara_adapter.resolve_include(
                include_target,
                normalized_candidate,
                module_index,
                normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
                resolve_suffix_match=repository_service._resolve_suffix_match,
            )
            if not target_file or target_file == normalized_candidate:
                continue
            imported_files.add(target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)

    for normalized_candidate in yara_files:
        pure_path = PurePosixPath(normalized_candidate)
        if (
            pure_path.name.lower() in preferred_basenames
            or pure_path.stem.lower().endswith("_index")
        ):
            entrypoint_paths.add(normalized_candidate)
            continue
        if normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)

    if not entrypoint_paths:
        entrypoint_paths.update(sorted(yara_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _glsl_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    shader_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {"main.glsl", "main.frag", "main.vert", "index.glsl"}
    library_like_parts = {"common", "include", "includes", "lib", "libs", "shaderlib", "shaders"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "glsl"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.glsl_adapter.is_probable_glsl_source(
            path=candidate_file,
            text=text,
        ):
            continue
        shader_files.append(normalized_candidate)
        for alias in repository_service.glsl_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)

    for normalized_candidate in shader_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.glsl_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if not dependency.target_file or dependency.target_file == normalized_candidate:
                continue
            imported_files.add(dependency.target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(dependency.target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)

    for normalized_candidate in shader_files:
        pure_path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in pure_path.parts[:-1]}
        if pure_path.name.lower() in preferred_basenames:
            entrypoint_paths.add(normalized_candidate)
            continue
        if normalized_candidate not in imported_files and not candidate_parts.intersection(
            library_like_parts
        ):
            entrypoint_paths.add(normalized_candidate)

    if not entrypoint_paths:
        entrypoint_paths.update(sorted(shader_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _hlsl_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    shader_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {
        "main.hlsl",
        "main.fx",
        "main.compute",
        "main.cs.hlsl",
        "index.hlsl",
    }
    library_like_parts = {"common", "include", "includes", "inc", "lib", "libs", "shaderlib"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "hlsl"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.hlsl_adapter.is_probable_hlsl_source(
            path=candidate_file,
            text=text,
        ):
            continue
        shader_files.append(normalized_candidate)
        for alias in repository_service.hlsl_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)

    for normalized_candidate in shader_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.hlsl_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if not dependency.target_file or dependency.target_file == normalized_candidate:
                continue
            imported_files.add(dependency.target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(dependency.target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)

    for normalized_candidate in shader_files:
        pure_path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in pure_path.parts[:-1]}
        if pure_path.name.lower() in preferred_basenames:
            entrypoint_paths.add(normalized_candidate)
            continue
        if normalized_candidate not in imported_files and not candidate_parts.intersection(
            library_like_parts
        ):
            entrypoint_paths.add(normalized_candidate)

    if not entrypoint_paths:
        entrypoint_paths.update(sorted(shader_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _wgsl_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    shader_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {"main.wgsl", "index.wgsl", "shader.wgsl"}
    library_like_parts = {"common", "include", "includes", "lib", "libs", "shaderlib", "shaders"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "wgsl"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.wgsl_adapter.is_probable_wgsl_source(
            path=candidate_file,
            text=text,
        ):
            continue
        shader_files.append(normalized_candidate)
        for alias in repository_service.wgsl_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)

    for normalized_candidate in shader_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.wgsl_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if not dependency.target_file or dependency.target_file == normalized_candidate:
                continue
            imported_files.add(dependency.target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(dependency.target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)

    for normalized_candidate in shader_files:
        pure_path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in pure_path.parts[:-1]}
        if pure_path.name.lower() in preferred_basenames:
            entrypoint_paths.add(normalized_candidate)
            continue
        if normalized_candidate not in imported_files and not candidate_parts.intersection(
            library_like_parts
        ):
            entrypoint_paths.add(normalized_candidate)

    if not entrypoint_paths:
        entrypoint_paths.update(sorted(shader_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _shaderlab_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    shader_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {"main.shader"}
    library_like_parts = {"editor", "sample", "samples", "test", "tests"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "shaderlab"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.shaderlab_adapter.is_probable_shaderlab_source(
            path=candidate_file,
            text=text,
        ):
            continue
        shader_files.append(normalized_candidate)
        for alias in repository_service.shaderlab_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in shader_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.shaderlab_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if not dependency.target_file or dependency.target_file == normalized_candidate:
                continue
            imported_files.add(dependency.target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(dependency.target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    for normalized_candidate in shader_files:
        pure_path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in pure_path.parts[:-1]}
        if pure_path.name.lower() in preferred_basenames:
            entrypoint_paths.add(normalized_candidate)
            continue
        if normalized_candidate not in imported_files and not candidate_parts.intersection(
            library_like_parts
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(shader_files)[:8])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _bitbake_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    bitbake_files: list[str] = []
    bitbake_file_text: dict[str, str] = {}
    config_paths: set[str] = set()
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    support_like_parts = {"classes", "classes-recipe", "conf", "include", "files"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate:
            continue
        pure_path = PurePosixPath(normalized_candidate)
        basename = pure_path.name.lower()
        suffix = pure_path.suffix.lower()
        if basename in repository_service.bitbake_adapter.BITBAKE_CONFIG_BASENAMES:
            config_paths.add(normalized_candidate)
        if not repository_service.bitbake_adapter.has_bitbake_path_hints(pure_path):
            continue
        language = (
            "bitbake"
            if suffix in {".bb", ".bbappend", ".bbclass"}
            or basename in repository_service.bitbake_adapter.BITBAKE_CONFIG_BASENAMES
            else _probe_language_for_path(normalized_candidate, repo_path=repo_path)
        )
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or language != "bitbake"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.bitbake_adapter.is_probable_bitbake_source(
            path=candidate_file,
            text=text,
        ):
            continue
        bitbake_files.append(normalized_candidate)
        bitbake_file_text[normalized_candidate] = text
        for alias in repository_service.bitbake_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
            text=text,
        ):
            module_index.setdefault(alias, normalized_candidate)
    for normalized_candidate in bitbake_files:
        text = bitbake_file_text.get(normalized_candidate)
        if text is None:
            continue
        for dependency in repository_service.bitbake_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if not dependency.target_file or dependency.target_file == normalized_candidate:
                continue
            imported_files.add(dependency.target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(dependency.target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    for normalized_candidate in bitbake_files:
        pure_path = PurePosixPath(normalized_candidate)
        lowered_parts = {part.lower() for part in pure_path.parts[:-1]}
        if pure_path.suffix.lower() != ".bb":
            parent_dir = repository_service._normalize_repository_relative_path(
                str(pure_path.parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
            continue
        if normalized_candidate not in imported_files and not lowered_parts.intersection(
            support_like_parts
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            path for path in bitbake_files if PurePosixPath(path).suffix.lower() == ".bb"
        )
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _bitbake_profile_candidate_paths(
    *,
    repo_path: Path,
    focus_paths: list[str],
    config_paths: list[str],
    max_files: int,
) -> list[str]:
    excluded_parts = set(repository_service._DEFAULT_EXCLUDED_PATH_PARTS)
    normalized_focus_paths = [
        normalized_path
        for path in focus_paths
        if (
            normalized_path := repository_service._normalize_repository_relative_path(path)
        )
    ]
    layer_roots: list[str] = []
    seen_layer_roots: set[str] = set()
    for config_path in config_paths:
        normalized_config = repository_service._normalize_repository_relative_path(config_path)
        if not normalized_config:
            continue
        config_pure = PurePosixPath(normalized_config)
        if (
            config_pure.name.lower()
            not in repository_service.bitbake_adapter.BITBAKE_CONFIG_BASENAMES
        ):
            continue
        if config_pure.parent.name.lower() == "conf":
            raw_layer_root = str(config_pure.parent.parent)
        else:
            raw_layer_root = str(config_pure.parent)
        normalized_layer_root = repository_service._normalize_repository_relative_path(
            raw_layer_root
        )
        if normalized_layer_root is None:
            normalized_layer_root = ""
        if normalized_layer_root in seen_layer_roots:
            continue
        seen_layer_roots.add(normalized_layer_root)
        layer_roots.append(normalized_layer_root)
    if not layer_roots:
        return []

    def _is_within_layer_root(relative_path: str) -> bool:
        return any(
            not layer_root
            or relative_path == layer_root
            or relative_path.startswith(f"{layer_root}/")
            for layer_root in layer_roots
        )

    def _matches_requested_focus(relative_path: str) -> bool:
        if not normalized_focus_paths:
            return True
        return any(
            relative_path == focus_root or relative_path.startswith(f"{focus_root}/")
            for focus_root in normalized_focus_paths
        )

    def _bitbake_candidate_rank(relative_path: str) -> tuple[int, int, int, int, str]:
        normalized_path = (
            repository_service._normalize_repository_relative_path(relative_path) or ""
        )
        pure_path = PurePosixPath(normalized_path)
        basename = pure_path.name.lower()
        suffix = pure_path.suffix.lower()
        support_like_parts = {"classes", "classes-recipe", "conf", "files", "include"}
        suffix_rank = {
            ".bb": 0,
            ".bbclass": 1,
            ".inc": 2,
            ".bbappend": 3,
        }.get(suffix, 4)
        support_rank = int(
            bool({part.lower() for part in pure_path.parts[:-1]}.intersection(support_like_parts))
        )
        return (
            0 if basename in repository_service.bitbake_adapter.BITBAKE_CONFIG_BASENAMES else 1,
            suffix_rank,
            support_rank if suffix == ".bb" else 0,
            1 if repository_service._is_test_path(normalized_path) else 0,
            normalized_path,
        )

    candidate_paths: list[str] = []
    git_relative_files = _git_repo_relative_files(repo_path)
    if git_relative_files is not None:
        for relative_path in git_relative_files:
            if any(part in excluded_parts for part in PurePosixPath(relative_path).parts[:-1]):
                continue
            if (
                not _is_within_layer_root(relative_path)
                or not _matches_requested_focus(relative_path)
            ):
                continue
            pure_path = PurePosixPath(relative_path)
            if not repository_service.bitbake_adapter.has_bitbake_path_hints(pure_path):
                continue
            candidate = repo_path / relative_path
            if not candidate.exists() or not candidate.is_file() or candidate.is_symlink():
                continue
            candidate_paths.append(relative_path)
    else:
        seen_paths: set[str] = set()
        for layer_root in layer_roots:
            root = repo_path / layer_root if layer_root else repo_path
            if not root.exists():
                continue
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [name for name in dirnames if name not in excluded_parts]
                for filename in filenames:
                    candidate = Path(dirpath) / filename
                    if not candidate.is_file() or candidate.is_symlink():
                        continue
                    relative_path = str(candidate.relative_to(repo_path)).replace("\\", "/")
                    if relative_path in seen_paths or not _matches_requested_focus(relative_path):
                        continue
                    seen_paths.add(relative_path)
                    if repository_service.bitbake_adapter.has_bitbake_path_hints(
                        PurePosixPath(relative_path)
                    ):
                        candidate_paths.append(relative_path)
    ordered_candidate_paths = sorted(candidate_paths, key=_bitbake_candidate_rank)
    return ordered_candidate_paths[: min(max_files, 512)]


def _hcl_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    hcl_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {"main.tf", "main.hcl", "terragrunt.hcl", "versions.tf"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "hcl"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.hcl_adapter.is_probable_hcl_source(
            path=candidate_file,
            text=text,
        ):
            continue
        hcl_files.append(normalized_candidate)
        for alias in repository_service.hcl_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
    for normalized_candidate in hcl_files:
        try:
            text = (repo_path / normalized_candidate).read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            continue
        for block in repository_service.hcl_adapter.iter_block_entries(text):
            source_statements = (
                repository_service.hcl_adapter.iter_module_source_statements(block)
            )
            for source_target, _line in source_statements:
                target_file = repository_service.hcl_adapter.resolve_module_source(
                    source_target,
                    normalized_candidate,
                    module_index,
                    normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
                    resolve_suffix_match=repository_service._resolve_suffix_match,
                )
                if not target_file or target_file == normalized_candidate:
                    continue
                imported_files.add(target_file)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(target_file).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
    for normalized_candidate in hcl_files:
        pure_path = PurePosixPath(normalized_candidate)
        if (
            pure_path.name.lower() in preferred_basenames
            or normalized_candidate not in imported_files
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(hcl_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _bicep_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    bicep_files: list[str] = []
    config_paths: set[str] = set()
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {"main.bicep"}

    def _is_bicep_test_path(path: str) -> bool:
        lowered = path.lower()
        return (
            lowered.endswith(".test.bicep")
            or "/test/" in lowered
            or "/tests/" in lowered
            or "/e2e/" in lowered
        )

    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate:
            continue
        if PurePosixPath(normalized_candidate).name.lower() == "bicepconfig.json":
            config_paths.add(normalized_candidate)
        if (
            _is_bicep_test_path(normalized_candidate)
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "bicep"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.bicep_adapter.is_probable_bicep_source(
            path=candidate_file,
            text=text,
        ):
            continue
        bicep_files.append(normalized_candidate)
        for alias in repository_service.bicep_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
    for normalized_candidate in bicep_files:
        try:
            text = (repo_path / normalized_candidate).read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            continue
        module_statements = repository_service.bicep_adapter.parse_module_statements(text)
        for _module_name, source_target, _line in module_statements:
            target_file = repository_service.bicep_adapter.resolve_module_source(
                source_target,
                normalized_candidate,
                module_index,
                normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
                resolve_suffix_match=repository_service._resolve_suffix_match,
            )
            if not target_file or target_file == normalized_candidate:
                continue
            imported_files.add(target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    for normalized_candidate in bicep_files:
        pure_path = PurePosixPath(normalized_candidate)
        if (
            pure_path.name.lower() in preferred_basenames
            or normalized_candidate not in imported_files
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(bicep_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _tlaplus_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    tla_files: list[str] = []
    config_paths: set[str] = set()
    cfg_stems: set[str] = set()
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate:
            continue
        if PurePosixPath(normalized_candidate).suffix.lower() == ".cfg":
            config_paths.add(normalized_candidate)
            cfg_stems.add(PurePosixPath(normalized_candidate).stem)
            continue
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "tlaplus"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.tlaplus_adapter.is_probable_tlaplus_source(
            path=candidate_file,
            text=text,
        ):
            continue
        tla_files.append(normalized_candidate)
        for alias in repository_service.tlaplus_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
    for normalized_candidate in tla_files:
        try:
            text = (repo_path / normalized_candidate).read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            continue
        for module_name, _line in repository_service.tlaplus_adapter.parse_extended_modules(text):
            target_file = repository_service.tlaplus_adapter.resolve_module_source(
                module_name,
                module_index,
                resolve_suffix_match=repository_service._resolve_suffix_match,
            )
            if not target_file or target_file == normalized_candidate:
                continue
            imported_files.add(target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
        for _alias, module_name, _line in (
            repository_service.tlaplus_adapter.parse_instance_statements(text)
        ):
            target_file = repository_service.tlaplus_adapter.resolve_module_source(
                module_name,
                module_index,
                resolve_suffix_match=repository_service._resolve_suffix_match,
            )
            if not target_file or target_file == normalized_candidate:
                continue
            imported_files.add(target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    for normalized_candidate in tla_files:
        stem = PurePosixPath(normalized_candidate).stem
        if (
            stem.startswith(("MC", "AP"))
            or stem in cfg_stems
            or normalized_candidate not in imported_files
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(tla_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _chapel_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    payload = _safe_load_toml_dict(repo_path / normalized_path) or {}
    brick = payload.get("brick") if isinstance(payload.get("brick"), dict) else {}
    package_name = str(brick.get("name") or "").strip()
    project_dir = PurePosixPath(normalized_path).parent
    support_roots: set[str] = set()
    for candidate_root in (project_dir / "src", project_dir / "examples", project_dir / "example"):
        normalized_root = repository_service._normalize_repository_relative_path(
            str(candidate_root)
        )
        if (
            normalized_root
            and not _is_non_operational_profile_path(normalized_root)
            and (repo_path / normalized_root).exists()
        ):
            support_roots.add(normalized_root)
    candidate_file_paths: list[str] = []
    search_root = repo_path / project_dir
    if search_root.exists():
        for candidate_file in sorted(search_root.rglob("*.chpl")):
            if not candidate_file.is_file() or candidate_file.is_symlink():
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate_file.relative_to(repo_path))
            )
            if relative_path:
                candidate_file_paths.append(relative_path)
    entrypoints, inferred_roots, _ = _chapel_profile_hints_from_candidates(
        repo_path,
        candidate_file_paths,
    )
    support_roots.update(inferred_roots)
    named_candidates = [
        str(project_dir / "src" / f"{package_name}.chpl") if package_name else "",
        str(project_dir / f"{package_name}.chpl") if package_name else "",
        str(project_dir / "src" / "main.chpl"),
        str(project_dir / "main.chpl"),
    ]
    for candidate in named_candidates:
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate)
        if (
            normalized_candidate
            and _is_operational_profile_entrypoint_candidate(
                normalized_candidate,
                repo_path=repo_path,
            )
            and (repo_path / normalized_candidate).exists()
        ):
            entrypoints.add(normalized_candidate)
    return entrypoints, {root for root in support_roots if root}, config_paths


def _resolve_eiffel_config_target(
    *,
    manifest_path: str,
    raw_target: str,
    variables: dict[str, str],
) -> str | None:
    candidate_value = str(raw_target or "").strip()
    if not candidate_value or "://" in candidate_value:
        return None
    for _ in range(4):
        updated_value = re.sub(
            r"\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)\}",
            lambda match: variables.get(str(match.group("name") or "").strip(), match.group(0)),
            candidate_value,
        )
        if updated_value == candidate_value:
            break
        candidate_value = updated_value
    return repository_service._normalize_repository_relative_path(
        str(PurePosixPath(manifest_path).parent / candidate_value)
    )


def _eiffel_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    manifest_file = repo_path / normalized_path
    try:
        text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set(), set(), config_paths
    if not repository_service.eiffel_adapter.is_probable_eiffel_source(
        path=Path(normalized_path),
        text=text,
    ):
        return set(), set(), config_paths
    project_dir = PurePosixPath(normalized_path).parent
    variables = repository_service.eiffel_adapter.parse_config_variables(text)
    root_class_names = repository_service.eiffel_adapter.parse_root_class_names(text)
    support_roots = {
        root
        for root in (
            repository_service._normalize_repository_relative_path(str(project_dir)),
        )
        if root not in {"", "."}
    }
    search_roots = [project_dir]
    for raw_target in repository_service.eiffel_adapter.parse_config_location_targets(text):
        resolved_target = _resolve_eiffel_config_target(
            manifest_path=normalized_path,
            raw_target=raw_target,
            variables=variables,
        )
        if not resolved_target:
            continue
        candidate = repo_path / resolved_target
        if candidate.is_file():
            config_paths.add(resolved_target)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(resolved_target).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
                search_roots.append(PurePosixPath(parent_dir))
            continue
        if candidate.is_dir():
            support_roots.add(resolved_target)
            search_roots.append(PurePosixPath(resolved_target))
    candidate_file_paths: list[str] = []
    seen_candidates: set[str] = set()
    for search_root in search_roots:
        search_path = repo_path / search_root
        if not search_path.is_dir():
            continue
        for candidate_file in sorted(search_path.rglob("*.e")):
            if not candidate_file.is_file() or candidate_file.is_symlink():
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate_file.relative_to(repo_path))
            )
            if not relative_path or relative_path in seen_candidates:
                continue
            seen_candidates.add(relative_path)
            candidate_file_paths.append(relative_path)
    entrypoints, inferred_roots, _ = _eiffel_profile_hints_from_candidates(
        repo_path,
        candidate_file_paths,
        preferred_root_class_names=root_class_names,
    )
    support_roots.update(inferred_roots)
    return entrypoints, {root for root in support_roots if root}, config_paths


def _eiffel_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
    *,
    preferred_root_class_names: tuple[str, ...] = (),
) -> tuple[set[str], set[str], set[str]]:
    eiffel_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {"application.e", "main.e"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "eiffel"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if (
            not candidate_file.is_file()
            or candidate_file.is_symlink()
            or candidate_file.suffix.lower() != ".e"
        ):
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.eiffel_adapter.is_probable_eiffel_source(
            path=Path(normalized_candidate),
            text=text,
        ):
            continue
        eiffel_files.append(normalized_candidate)
        for alias in repository_service.eiffel_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
    for root_class_name in preferred_root_class_names:
        target_file = module_index.get(root_class_name) or repository_service._resolve_suffix_match(
            module_index=module_index,
            suffixes=(root_class_name, f"{root_class_name}.e", f"{root_class_name.lower()}.e"),
        )
        if target_file:
            entrypoint_paths.add(target_file)
    for normalized_candidate in eiffel_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency_target in repository_service.eiffel_adapter.parse_dependency_targets(
            text,
            file_path=normalized_candidate,
        ):
            target_file = module_index.get(
                dependency_target
            ) or repository_service._resolve_suffix_match(
                module_index=module_index,
                suffixes=(
                    dependency_target,
                    f"{dependency_target}.e",
                    f"{dependency_target.lower()}.e",
                ),
            )
            if not target_file or target_file == normalized_candidate:
                continue
            imported_files.add(target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    for normalized_candidate in eiffel_files:
        basename = PurePosixPath(normalized_candidate).name.lower()
        if basename in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(eiffel_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _chapel_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    chapel_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {"main.chpl"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "chapel"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.chapel_adapter.is_probable_chapel_source(
            path=candidate_file,
            text=text,
        ):
            continue
        chapel_files.append(normalized_candidate)
        for alias in repository_service.chapel_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
    for normalized_candidate in chapel_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for _kind, import_target, _alias, _line_no in (
            repository_service.chapel_adapter.parse_use_import_statements(text)
        ):
            target_file = repository_service.chapel_adapter.resolve_import(
                import_target,
                module_index,
                resolve_suffix_match=repository_service._resolve_suffix_match,
            )
            if not target_file or target_file == normalized_candidate:
                continue
            imported_files.add(target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    for normalized_candidate in chapel_files:
        basename = PurePosixPath(normalized_candidate).name.lower()
        if basename in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(chapel_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _odin_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    manifest_file = repo_path / normalized_path
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set(), set(), config_paths
    if not repository_service.odin_adapter.is_probable_odin_source(
        path=Path(normalized_path),
        text=manifest_text,
    ):
        return set(), set(), config_paths
    project_dir = PurePosixPath(normalized_path).parent
    support_roots: set[str] = set()
    search_roots: list[PurePosixPath] = [project_dir]
    for raw_target in (
        *repository_service.odin_adapter.parse_ols_checker_paths(manifest_text),
        *repository_service.odin_adapter.parse_ols_collections(manifest_text),
    ):
        normalized_target = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_target)
        )
        if not normalized_target:
            continue
        candidate = repo_path / normalized_target
        if candidate.is_dir():
            support_roots.add(normalized_target)
            search_roots.append(PurePosixPath(normalized_target))
        elif candidate.is_file():
            config_paths.add(normalized_target)
    candidate_file_paths: list[str] = []
    seen_candidates: set[str] = set()
    for search_root in search_roots:
        search_path = repo_path / search_root
        if not search_path.is_dir():
            continue
        for candidate_file in sorted(search_path.rglob("*.odin")):
            if not candidate_file.is_file() or candidate_file.is_symlink():
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate_file.relative_to(repo_path))
            )
            if not relative_path or relative_path in seen_candidates:
                continue
            seen_candidates.add(relative_path)
            candidate_file_paths.append(relative_path)
    entrypoints, inferred_roots, _ = _odin_profile_hints_from_candidates(
        repo_path,
        candidate_file_paths,
    )
    support_roots.update(inferred_roots)
    for candidate in (
        str(project_dir / "main.odin"),
        str(project_dir / "src" / "main.odin"),
    ):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate)
        if (
            normalized_candidate
            and _is_operational_profile_entrypoint_candidate(
                normalized_candidate,
                repo_path=repo_path,
            )
            and (repo_path / normalized_candidate).exists()
        ):
            entrypoints.add(normalized_candidate)
    return entrypoints, {root for root in support_roots if root}, config_paths


def _odin_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    odin_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {"main.odin", "app.odin"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "odin"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if (
            not candidate_file.is_file()
            or candidate_file.is_symlink()
            or candidate_file.suffix.lower() != ".odin"
        ):
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.odin_adapter.is_probable_odin_source(
            path=candidate_file,
            text=text,
        ):
            continue
        odin_files.append(normalized_candidate)
        for alias in repository_service.odin_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
    for normalized_candidate in odin_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for import_target, _alias, _line_number in (
            repository_service.odin_adapter.parse_import_statements(text)
        ):
            target_file = repository_service.odin_adapter.resolve_import(
                import_target,
                module_index,
                resolve_suffix_match=repository_service._resolve_suffix_match,
            )
            if not target_file or target_file == normalized_candidate:
                continue
            imported_files.add(target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    for normalized_candidate in odin_files:
        basename = PurePosixPath(normalized_candidate).name.lower()
        if basename in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(odin_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _factor_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    factor_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {"main.factor", "app.factor", "run.factor"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "factor"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if (
            not candidate_file.is_file()
            or candidate_file.is_symlink()
            or candidate_file.suffix.lower() != ".factor"
        ):
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.factor_adapter.is_probable_factor_source(
            path=candidate_file,
            text=text,
        ):
            continue
        factor_files.append(normalized_candidate)
        for alias in repository_service.factor_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
    for normalized_candidate in factor_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for import_statement in repository_service.factor_adapter.parse_import_statements(text):
            target_file = repository_service.factor_adapter.resolve_import(
                import_statement.target,
                module_index,
                resolve_suffix_match=repository_service._resolve_suffix_match,
            )
            if not target_file or target_file == normalized_candidate:
                continue
            imported_files.add(target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    for normalized_candidate in factor_files:
        path = PurePosixPath(normalized_candidate)
        basename = path.name.lower()
        if (
            basename in preferred_basenames
            or path.parent.name.lower() == path.stem.lower()
            or normalized_candidate not in imported_files
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(factor_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _cue_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
    *,
    manifest_path: str | None = None,
) -> tuple[set[str], set[str], set[str]]:
    cue_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    config_paths: set[str] = {manifest_path} if manifest_path else set()
    preferred_basenames = {"main.cue", "schema.cue", "tool.cue"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "cue"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if (
            not candidate_file.is_file()
            or candidate_file.is_symlink()
            or candidate_file.suffix.lower() != ".cue"
        ):
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.cue_adapter.is_probable_cue_source(
            path=candidate_file,
            text=text,
        ):
            continue
        cue_files.append(normalized_candidate)
        for alias in repository_service.cue_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        if "/cue.mod/" in normalized_candidate.replace("\\", "/"):
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(normalized_candidate).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    for normalized_candidate in cue_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for import_statement in repository_service.cue_adapter.parse_import_statements(text):
            target_file = repository_service.cue_adapter.resolve_import(
                file_path=normalized_candidate,
                import_target=import_statement.target,
                module_index=module_index,
                normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
                resolve_suffix_match=repository_service._resolve_suffix_match,
                root_path=repo_path,
            )
            if not target_file or target_file == normalized_candidate:
                continue
            imported_files.add(target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    for normalized_candidate in cue_files:
        lowered_path = normalized_candidate.lower().replace("\\", "/")
        basename = PurePosixPath(normalized_candidate).name.lower()
        if "/cue.mod/" in lowered_path:
            continue
        if basename in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in sorted(cue_files)[:8]
            if "/cue.mod/" not in normalized_candidate.lower().replace("\\", "/")
        )
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _logtalk_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    logtalk_files: list[str] = []
    config_paths: set[str] = set()
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {"loader.lgt", "loader.logtalk", "main.lgt", "main.logtalk"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "logtalk"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.logtalk_adapter.is_probable_logtalk_source(
            path=candidate_file,
            text=text,
        ):
            continue
        logtalk_files.append(normalized_candidate)
        for alias in repository_service.logtalk_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
    for normalized_candidate in logtalk_files:
        try:
            text = (repo_path / normalized_candidate).read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            continue
        for target_name, _imports, _line_no in (
            repository_service.logtalk_adapter.parse_uses_statements(text)
        ):
            target_file = repository_service.logtalk_adapter.resolve_import(
                normalized_candidate,
                target_name,
                module_index,
                resolve_suffix_match=repository_service._resolve_suffix_match,
            )
            if target_file and target_file != normalized_candidate:
                imported_files.add(target_file)
        for target_name, _line_no in repository_service.logtalk_adapter.parse_load_statements(
            text
        ):
            target_file = repository_service.logtalk_adapter.resolve_import(
                normalized_candidate,
                target_name,
                module_index,
                resolve_suffix_match=repository_service._resolve_suffix_match,
            )
            if target_file and target_file != normalized_candidate:
                imported_files.add(target_file)
        for target_name, _line_no in repository_service.logtalk_adapter.parse_relation_statements(
            text
        ):
            target_file = repository_service.logtalk_adapter.resolve_import(
                normalized_candidate,
                target_name,
                module_index,
                resolve_suffix_match=repository_service._resolve_suffix_match,
            )
            if target_file and target_file != normalized_candidate:
                imported_files.add(target_file)
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in logtalk_files:
        if (
            PurePosixPath(normalized_candidate).name.lower() in preferred_basenames
            or normalized_candidate not in imported_files
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(logtalk_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _smalltalk_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    project_dir = PurePosixPath(normalized_path).parent
    search_roots: list[Path] = []
    support_roots: set[str] = set()
    for source_root in ("src", "repository", "packages", "tonel"):
        candidate_root = repo_path / project_dir / source_root
        if not candidate_root.is_dir():
            continue
        search_roots.append(candidate_root)
        normalized_root = repository_service._normalize_repository_relative_path(
            str(candidate_root.relative_to(repo_path))
        )
        if normalized_root:
            support_roots.add(normalized_root)
    if not search_roots:
        search_root = repo_path / project_dir
        if search_root.is_dir():
            search_roots.append(search_root)
            normalized_root = repository_service._normalize_repository_relative_path(
                str(search_root.relative_to(repo_path))
            )
            if normalized_root:
                support_roots.add(normalized_root)
    entrypoint_paths: set[str] = set()
    fallback_paths: list[str] = []
    seen_paths: set[str] = set()
    for search_root in search_roots:
        for candidate in sorted(search_root.rglob("*.st")):
            if not candidate.is_file() or candidate.is_symlink():
                continue
            normalized_candidate = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                not normalized_candidate
                or normalized_candidate in seen_paths
                or _probe_language_for_path(normalized_candidate, repo_path=repo_path)
                != "smalltalk"
                or not _is_operational_profile_entrypoint_candidate(
                    normalized_candidate,
                    repo_path=repo_path,
                )
            ):
                continue
            seen_paths.add(normalized_candidate)
            basename = PurePosixPath(normalized_candidate).name
            if basename.startswith("BaselineOf") and basename.endswith(".class.st"):
                entrypoint_paths.add(normalized_candidate)
                continue
            if basename != "package.st":
                fallback_paths.append(normalized_candidate)
    if not entrypoint_paths and fallback_paths:
        entrypoint_paths.update(fallback_paths[:8])
    return entrypoint_paths, support_roots, config_paths


def _coffeescript_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    manifest_file = repo_path / normalized_path
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set(), set(), config_paths
    if not repository_service.coffeescript_adapter.is_probable_coffeescript_source(
        path=Path(normalized_path),
        text=manifest_text,
    ):
        return set(), set(), config_paths
    project_dir = PurePosixPath(normalized_path).parent
    root_candidates = (
        project_dir,
        project_dir / "src",
        project_dir / "lib",
        project_dir / "app",
        project_dir / "scripts",
    )
    support_roots: set[str] = set()
    search_roots: list[Path] = []
    seen_search_roots: set[Path] = set()
    for candidate_root in root_candidates:
        normalized_root = repository_service._normalize_repository_relative_path(
            str(candidate_root)
        )
        if normalized_root and (repo_path / normalized_root).exists():
            support_roots.add(normalized_root)
        search_root = repo_path / candidate_root
        resolved_search_root = search_root.resolve()
        if not search_root.exists() or resolved_search_root in seen_search_roots:
            continue
        seen_search_roots.add(resolved_search_root)
        search_roots.append(search_root)

    entrypoint_paths: set[str] = set()
    if _is_operational_profile_entrypoint_candidate(normalized_path, repo_path=repo_path):
        entrypoint_paths.add(normalized_path)
    for search_root in search_roots:
        if not search_root.is_dir():
            continue
        for suffix in ("*.coffee", "*.litcoffee"):
            for candidate in sorted(search_root.rglob(suffix)):
                relative_path = repository_service._normalize_repository_relative_path(
                    str(candidate.relative_to(repo_path))
                )
                if (
                    not relative_path
                    or repository_service._is_test_path(relative_path)
                    or _is_non_operational_profile_path(relative_path)
                    or _probe_language_for_path(relative_path, repo_path=repo_path)
                    != "coffeescript"
                ):
                    continue
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(relative_path).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
                if _is_operational_profile_entrypoint_candidate(
                    relative_path,
                    repo_path=repo_path,
                ):
                    entrypoint_paths.add(relative_path)
    return entrypoint_paths, support_roots, config_paths


def _haxe_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    manifest_file = repo_path / normalized_path
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set(), set(), config_paths
    if not repository_service.haxe_adapter.is_probable_haxe_source(
        path=Path(normalized_path),
        text=manifest_text,
    ):
        return set(), set(), config_paths
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    source_roots: set[str] = set()
    support_roots: set[str] = {root_prefix.rstrip("/")}
    entrypoint_modules: set[str] = set()
    if normalized_path.lower().endswith(".hxml"):
        for raw_line in manifest_text.splitlines():
            stripped_line = raw_line.strip()
            if not stripped_line or stripped_line.startswith("#"):
                continue
            if stripped_line.startswith(("-cp ", "--class-path ")):
                class_path = stripped_line.split(maxsplit=1)[1].strip().strip("\"'")
                normalized_root = repository_service._normalize_repository_relative_path(
                    str(project_dir / class_path)
                )
                if normalized_root and (repo_path / normalized_root).exists():
                    source_roots.add(normalized_root)
                    support_roots.add(normalized_root)
            elif stripped_line.startswith(("-main ", "--main ")):
                module_name = stripped_line.split(maxsplit=1)[1].strip().strip("\"'")
                if module_name:
                    entrypoint_modules.add(module_name)
    else:
        source_path_re = re.compile(
            r'<source\b[^>]*path=["\'](?P<path>[^"\']+)["\']',
            re.IGNORECASE,
        )
        main_re = re.compile(
            r'<app\b[^>]*main=["\'](?P<main>[^"\']+)["\']',
            re.IGNORECASE,
        )
        for match in source_path_re.finditer(manifest_text):
            normalized_root = repository_service._normalize_repository_relative_path(
                str(project_dir / str(match.group("path") or "").strip())
            )
            if normalized_root and (repo_path / normalized_root).exists():
                source_roots.add(normalized_root)
                support_roots.add(normalized_root)
        for match in main_re.finditer(manifest_text):
            module_name = str(match.group("main") or "").strip()
            if module_name:
                entrypoint_modules.add(module_name)
    if not source_roots:
        for relative_root in ("src", "source", "sources", "haxe"):
            normalized_root = repository_service._normalize_repository_relative_path(
                str(project_dir / relative_root)
            )
            if normalized_root and (repo_path / normalized_root).exists():
                source_roots.add(normalized_root)
                support_roots.add(normalized_root)
    entrypoint_paths: set[str] = set()
    fallback_paths: list[str] = []
    seen_paths: set[str] = set()

    def _consider_candidate(candidate_path: str, *, prefer: bool) -> None:
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or normalized_candidate in seen_paths
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "haxe"
            or not _is_operational_profile_entrypoint_candidate(
                normalized_candidate,
                repo_path=repo_path,
            )
        ):
            return
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            return
        seen_paths.add(normalized_candidate)
        if prefer:
            entrypoint_paths.add(normalized_candidate)
        else:
            fallback_paths.append(normalized_candidate)

    for module_name in sorted(entrypoint_modules):
        module_relative_path = module_name.replace(".", "/") + ".hx"
        for source_root in sorted(source_roots):
            _consider_candidate(f"{source_root}/{module_relative_path}", prefer=True)
    for source_root in sorted(source_roots):
        source_dir = repo_path / source_root
        if not source_dir.is_dir():
            continue
        for candidate in sorted(source_dir.rglob("*.hx")):
            _consider_candidate(str(candidate.relative_to(repo_path)), prefer=False)
    if not entrypoint_paths:
        for fallback_path in fallback_paths:
            if PurePosixPath(fallback_path).name == "Main.hx":
                entrypoint_paths.add(fallback_path)
        if not entrypoint_paths:
            entrypoint_paths.update(fallback_paths[:8])
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _mql5_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    manifest_file = repo_path / normalized_path
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        manifest_text = ""
    project_dir = PurePosixPath(normalized_path).parent
    support_roots: set[str] = set()
    search_roots: list[Path] = []
    seen_search_roots: set[Path] = set()
    for candidate_root in (
        project_dir,
        project_dir / "Experts",
        project_dir / "Indicators",
        project_dir / "Scripts",
        project_dir / "Services",
        project_dir / "Include",
        project_dir / "Libraries",
        project_dir / "MQL5",
        project_dir / "MQL5" / "Include",
    ):
        normalized_root = repository_service._normalize_repository_relative_path(
            str(candidate_root)
        )
        if normalized_root and (repo_path / normalized_root).exists():
            support_roots.add(normalized_root)
        search_root = repo_path / candidate_root
        resolved_search_root = search_root.resolve()
        if not search_root.exists() or resolved_search_root in seen_search_roots:
            continue
        seen_search_roots.add(resolved_search_root)
        search_roots.append(search_root)
    discovered_paths: set[str] = set()

    def _register_path(candidate_path: str) -> None:
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate:
            return
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            return
        discovered_paths.add(normalized_candidate)
        parent_path = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_path:
            support_roots.add(parent_path)

    for entry in repository_service.mql5_adapter.project_file_entries(manifest_text):
        _register_path(str(project_dir / entry))
    for search_root in search_roots:
        if not search_root.is_dir():
            continue
        for suffix in ("*.mq5", "*.mqh"):
            for candidate in sorted(search_root.rglob(suffix)):
                if not candidate.is_file() or candidate.is_symlink():
                    continue
                resolved_path = repository_service._normalize_repository_relative_path(
                    str(candidate.relative_to(repo_path))
                )
                if not resolved_path or _probe_language_for_path(
                    resolved_path,
                    repo_path=repo_path,
                ) != "mql5":
                    continue
                _register_path(resolved_path)
    entrypoint_paths = {
        candidate_path
        for candidate_path in discovered_paths
        if PurePosixPath(candidate_path).suffix.lower() == ".mq5"
        and _is_operational_profile_entrypoint_candidate(candidate_path, repo_path=repo_path)
    }
    return entrypoint_paths, support_roots, config_paths


def _gams_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    if (
        not manifest_file.is_file()
        or manifest_file.is_symlink()
        or _probe_language_for_path(normalized_path, repo_path=repo_path) != "gams"
    ):
        return set(), set(), set()
    config_paths = {normalized_path}
    support_roots: set[str] = set()
    entrypoint_paths: set[str] = set()
    parent_parts = {part.lower() for part in PurePosixPath(normalized_path).parts[:-1]}
    parent_path = repository_service._normalize_repository_relative_path(
        str(PurePosixPath(normalized_path).parent)
    )
    if parent_path:
        support_roots.add(parent_path)
    if PurePosixPath(normalized_path).suffix.lower() == ".gms" and (
        not parent_parts.intersection({"include", "includes"})
    ) and (
        _is_operational_profile_entrypoint_candidate(normalized_path, repo_path=repo_path)
    ):
        entrypoint_paths.add(normalized_path)
    search_root = repo_path
    if search_root.is_dir():
        for candidate in sorted(search_root.rglob("*.inc")):
            if not candidate.is_file() or candidate.is_symlink():
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                not relative_path
                or _probe_language_for_path(relative_path, repo_path=repo_path) != "gams"
            ):
                continue
            candidate_parent = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(relative_path).parent)
            )
            if candidate_parent:
                support_roots.add(candidate_parent)
    return entrypoint_paths, support_roots, config_paths


def _openscad_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    if (
        not manifest_file.is_file()
        or manifest_file.is_symlink()
        or _probe_language_for_path(normalized_path, repo_path=repo_path) != "openscad"
    ):
        return set(), set(), set()
    config_paths = {normalized_path}
    support_roots: set[str] = set()
    entrypoint_paths: set[str] = set()
    parent_path = repository_service._normalize_repository_relative_path(
        str(PurePosixPath(normalized_path).parent)
    )
    if parent_path:
        support_roots.add(parent_path)
    parent_parts = {part.lower() for part in PurePosixPath(normalized_path).parts[:-1]}
    include_like_parts = {
        "include",
        "includes",
        "lib",
        "libs",
        "library",
        "libraries",
    }
    if not parent_parts.intersection(include_like_parts):
        if _is_operational_profile_entrypoint_candidate(normalized_path, repo_path=repo_path):
            entrypoint_paths.add(normalized_path)
    if repo_path.is_dir():
        for candidate in sorted(repo_path.rglob("*.scad")):
            if not candidate.is_file() or candidate.is_symlink():
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                not relative_path
                or _probe_language_for_path(relative_path, repo_path=repo_path) != "openscad"
            ):
                continue
            candidate_parent = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(relative_path).parent)
            )
            if candidate_parent:
                support_roots.add(candidate_parent)
            candidate_parts = {
                part.lower() for part in PurePosixPath(relative_path).parts[:-1]
            }
            if candidate_parts.intersection(
                {"include", "includes", "lib", "libs", "library", "libraries"}
            ):
                continue
            if _is_operational_profile_entrypoint_candidate(relative_path, repo_path=repo_path):
                entrypoint_paths.add(relative_path)
    if not entrypoint_paths and _is_operational_profile_entrypoint_candidate(
        normalized_path,
        repo_path=repo_path,
    ):
        entrypoint_paths.add(normalized_path)
    return entrypoint_paths, support_roots, config_paths


def _nix_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    if (
        not manifest_file.is_file()
        or manifest_file.is_symlink()
        or _probe_language_for_path(normalized_path, repo_path=repo_path) != "nix"
    ):
        return set(), set(), set()
    manifest_parent = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(manifest_parent) in {"", "."} else f"{manifest_parent}/"
    config_paths = {normalized_path}
    entrypoint_paths: set[str] = set()
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}nix",
        f"{root_prefix}modules",
        f"{root_prefix}overlays",
        f"{root_prefix}pkgs",
        f"{root_prefix}lib",
        f"{root_prefix}homeModules",
        f"{root_prefix}nixosModules",
    }
    for sibling_name in ("flake.nix", "default.nix", "shell.nix"):
        sibling_path = repository_service._normalize_repository_relative_path(
            str(manifest_parent / sibling_name)
        )
        if sibling_path and (repo_path / sibling_path).is_file():
            config_paths.add(sibling_path)
            if _is_operational_profile_entrypoint_candidate(
                sibling_path,
                repo_path=repo_path,
            ):
                entrypoint_paths.add(sibling_path)
    try:
        text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    for import_target in repository_service.nix_adapter.import_targets_for_text(text):
        resolved_path = repository_service._normalize_repository_relative_path(
            str(manifest_parent / import_target)
        )
        if (
            not resolved_path
            or not (repo_path / resolved_path).is_file()
            or _probe_language_for_path(resolved_path, repo_path=repo_path) != "nix"
        ):
            continue
        support_root = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if support_root:
            support_roots.add(support_root)
        if _is_operational_profile_entrypoint_candidate(resolved_path, repo_path=repo_path):
            entrypoint_paths.add(resolved_path)
    return entrypoint_paths, support_roots, config_paths


def _starlark_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    if (
        not manifest_file.is_file()
        or manifest_file.is_symlink()
        or _probe_language_for_path(normalized_path, repo_path=repo_path) != "starlark"
    ):
        return set(), set(), set()
    manifest_parent = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(manifest_parent) in {"", "."} else f"{manifest_parent}/"
    config_paths = {normalized_path}
    entrypoint_paths: set[str] = set()
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}bazel",
        f"{root_prefix}bzl",
        f"{root_prefix}defs",
        f"{root_prefix}extensions",
        f"{root_prefix}lib",
        f"{root_prefix}private",
        f"{root_prefix}rules",
        f"{root_prefix}toolchains",
    }
    if _is_operational_profile_entrypoint_candidate(normalized_path, repo_path=repo_path):
        entrypoint_paths.add(normalized_path)
    for sibling_name in (
        "BUILD",
        "BUILD.bazel",
        "MODULE.bazel",
        "WORKSPACE",
        "WORKSPACE.bazel",
    ):
        sibling_path = repository_service._normalize_repository_relative_path(
            str(manifest_parent / sibling_name)
        )
        if not sibling_path or not (repo_path / sibling_path).is_file():
            continue
        config_paths.add(sibling_path)
        if _is_operational_profile_entrypoint_candidate(sibling_path, repo_path=repo_path):
            entrypoint_paths.add(sibling_path)
    try:
        text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    starlark_module_index: dict[str, str] = {}
    for pattern in (
        "*.bzl",
        "*.star",
        "BUILD",
        "BUILD.bazel",
        "MODULE.bazel",
        "WORKSPACE",
        "WORKSPACE.bazel",
    ):
        for candidate in sorted(repo_path.rglob(pattern)):
            if not candidate.is_file() or candidate.is_symlink():
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if relative_path:
                starlark_module_index[relative_path] = relative_path
    include_like_parts = {"bzl", "defs", "extensions", "include", "lib", "private", "rules"}
    for load_target, _body, _line in repository_service.starlark_adapter.iter_load_statements(text):
        resolved_path = repository_service.starlark_adapter.resolve_load_target(
            current_file=normalized_path,
            import_target=load_target,
            module_index=starlark_module_index,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        )
        if (
            not resolved_path
            or not (repo_path / resolved_path).is_file()
            or _probe_language_for_path(resolved_path, repo_path=repo_path) != "starlark"
        ):
            continue
        support_root = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if support_root:
            support_roots.add(support_root)
        if _is_operational_profile_entrypoint_candidate(
            resolved_path,
            repo_path=repo_path,
        ):
            entrypoint_paths.add(resolved_path)
    for candidate in sorted((repo_path / manifest_parent).rglob("*.bzl")):
        if not candidate.is_file() or candidate.is_symlink():
            continue
        relative_path = repository_service._normalize_repository_relative_path(
            str(candidate.relative_to(repo_path))
        )
        if (
            not relative_path
            or _probe_language_for_path(relative_path, repo_path=repo_path) != "starlark"
        ):
            continue
        support_root = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(relative_path).parent)
        )
        if support_root:
            support_roots.add(support_root)
        parent_parts = {part.lower() for part in PurePosixPath(relative_path).parts[:-1]}
        if parent_parts.intersection(include_like_parts):
            continue
        if _is_operational_profile_entrypoint_candidate(relative_path, repo_path=repo_path):
            entrypoint_paths.add(relative_path)
        if len(entrypoint_paths) >= 8:
            break
    return entrypoint_paths, support_roots, config_paths


def _purescript_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    project_dir = PurePosixPath(normalized_path).parent
    support_roots: set[str] = set()
    search_roots: list[Path] = []
    seen_search_roots: set[Path] = set()
    for candidate_root in (
        project_dir / "src",
        project_dir / "app",
        project_dir / "test",
        project_dir / "tests",
        project_dir / "examples",
        project_dir,
    ):
        normalized_root = repository_service._normalize_repository_relative_path(
            str(candidate_root)
        )
        if normalized_root and (repo_path / normalized_root).exists():
            support_roots.add(normalized_root)
        search_root = repo_path / candidate_root
        resolved_search_root = search_root.resolve()
        if not search_root.exists() or resolved_search_root in seen_search_roots:
            continue
        seen_search_roots.add(resolved_search_root)
        search_roots.append(search_root)

    entrypoint_paths: set[str] = set()
    fallback_paths: set[str] = set()
    for search_root in search_roots:
        if not search_root.is_dir():
            continue
        for candidate in sorted(search_root.rglob("*.purs")):
            if not candidate.is_file() or candidate.is_symlink():
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                not relative_path
                or _probe_language_for_path(relative_path, repo_path=repo_path) != "purescript"
            ):
                continue
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(relative_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
            if (
                repository_service._is_test_path(relative_path)
                or _is_non_operational_profile_path(relative_path)
            ):
                continue
            fallback_paths.add(relative_path)
            if _is_operational_profile_entrypoint_candidate(relative_path, repo_path=repo_path):
                entrypoint_paths.add(relative_path)
    if not entrypoint_paths and fallback_paths:
        entrypoint_paths.update(sorted(fallback_paths)[:8])
    return entrypoint_paths, support_roots, config_paths


def _rescript_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    if not manifest_file.is_file() or manifest_file.is_symlink():
        return set(), set(), set()
    try:
        manifest_payload = json.loads(manifest_file.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        manifest_payload = {}
    project_dir = PurePosixPath(normalized_path).parent
    source_roots: list[PurePosixPath] = []
    raw_sources = manifest_payload.get("sources")
    if isinstance(raw_sources, list):
        for raw_source in raw_sources:
            if isinstance(raw_source, str):
                source_roots.append(project_dir / raw_source)
                continue
            if not isinstance(raw_source, dict):
                continue
            raw_dir = raw_source.get("dir")
            if isinstance(raw_dir, str) and raw_dir.strip():
                source_roots.append(project_dir / raw_dir.strip())
    if not source_roots:
        source_roots = [
            project_dir / "src",
            project_dir / "lib",
            project_dir / "test",
            project_dir / "tests",
            project_dir / "examples",
            project_dir / "scripts",
            project_dir,
        ]

    config_paths = {normalized_path}
    support_roots: set[str] = set()
    entrypoint_paths: set[str] = set()
    fallback_paths: set[str] = set()
    seen_search_roots: set[Path] = set()
    for candidate_root in source_roots:
        normalized_root = repository_service._normalize_repository_relative_path(
            str(candidate_root)
        )
        search_root = repo_path / candidate_root
        resolved_search_root = search_root.resolve()
        if normalized_root and search_root.exists():
            support_roots.add(normalized_root)
        if not search_root.exists() or resolved_search_root in seen_search_roots:
            continue
        seen_search_roots.add(resolved_search_root)
        if not search_root.is_dir():
            continue
        for candidate in sorted(search_root.rglob("*")):
            if (
                not candidate.is_file()
                or candidate.is_symlink()
                or candidate.suffix.lower()
                not in repository_service.rescript_adapter.RESCRIPT_SUFFIXES
            ):
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                not relative_path
                or _probe_language_for_path(relative_path, repo_path=repo_path) != "rescript"
            ):
                continue
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(relative_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
            if (
                repository_service._is_test_path(relative_path)
                or _is_non_operational_profile_path(relative_path)
            ):
                continue
            fallback_paths.add(relative_path)
            if _is_operational_profile_entrypoint_candidate(relative_path, repo_path=repo_path):
                entrypoint_paths.add(relative_path)
    if not entrypoint_paths and fallback_paths:
        entrypoint_paths.update(sorted(fallback_paths)[:8])
    return entrypoint_paths, support_roots, config_paths


def _moonbit_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
    *,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_manifest_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_manifest_path:
        return set(), set(), set()
    manifest_parent = PurePosixPath(normalized_manifest_path).parent
    root_prefix = "" if str(manifest_parent) in {"", "."} else f"{manifest_parent}/"
    moonbit_files: list[str] = []
    config_paths: set[str] = {normalized_manifest_path}
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    entrypoint_paths: set[str] = set()
    fallback_paths: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {"pkg.generated.mbti"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or (root_prefix and not normalized_candidate.startswith(root_prefix))
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        basename = PurePosixPath(normalized_candidate).name.lower()
        if basename in repository_service.moonbit_adapter.MOONBIT_CONFIG_BASENAMES:
            if repository_service.moonbit_adapter.is_probable_moonbit_config(
                path=Path(normalized_candidate),
                text=text,
            ):
                config_paths.add(normalized_candidate)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(normalized_candidate).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
            continue
        if (
            _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "moonbit"
            or not repository_service.moonbit_adapter.is_probable_moonbit_source(
                path=Path(normalized_candidate),
                text=text,
            )
        ):
            continue
        moonbit_files.append(normalized_candidate)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
        for alias in repository_service.moonbit_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
    for config_path in sorted(config_paths):
        try:
            text = (repo_path / config_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.moonbit_adapter.parse_dependencies_only(
            config_path,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file:
                imported_files.add(dependency.target_file)
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in moonbit_files:
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
        ):
            continue
        fallback_paths.add(normalized_candidate)
        basename = PurePosixPath(normalized_candidate).name.lower()
        package_alias = PurePosixPath(normalized_candidate).parent.name.lower()
        if _is_operational_profile_entrypoint_candidate(
            normalized_candidate,
            repo_path=repo_path,
        ) and (
            basename == f"{package_alias}.mbt"
            or basename in preferred_basenames
            or normalized_candidate not in imported_files
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths and fallback_paths:
        entrypoint_paths.update(sorted(fallback_paths)[:12])
    return entrypoint_paths, support_roots, config_paths


def _gleam_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    if not manifest_file.is_file() or manifest_file.is_symlink():
        return set(), set(), set()
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        manifest_text = ""
    project_dir = PurePosixPath(normalized_path).parent
    package_name = ""
    if tomllib is not None:
        try:
            manifest_payload = tomllib.loads(manifest_text)
        except (tomllib.TOMLDecodeError, TypeError, ValueError):
            manifest_payload = {}
        raw_package_name = manifest_payload.get("name")
        if isinstance(raw_package_name, str):
            package_name = raw_package_name.strip()
    config_paths = {normalized_path}
    support_roots: set[str] = set()
    search_roots: list[Path] = []
    seen_search_roots: set[Path] = set()
    for candidate_root in (
        project_dir / "src",
        project_dir / "test",
        project_dir / "tests",
        project_dir / "app",
        project_dir,
    ):
        normalized_root = repository_service._normalize_repository_relative_path(
            str(candidate_root)
        )
        if normalized_root and (repo_path / normalized_root).exists():
            support_roots.add(normalized_root)
        search_root = repo_path / candidate_root
        resolved_search_root = search_root.resolve()
        if not search_root.exists() or resolved_search_root in seen_search_roots:
            continue
        seen_search_roots.add(resolved_search_root)
        search_roots.append(search_root)
    entrypoint_paths: set[str] = set()
    fallback_paths: set[str] = set()
    preferred_names = {"main.gleam", "app.gleam"}
    if package_name:
        preferred_names.add(f"{package_name.replace('-', '_')}.gleam")
    for search_root in search_roots:
        if not search_root.is_dir():
            continue
        for candidate in sorted(search_root.rglob("*.gleam")):
            if not candidate.is_file() or candidate.is_symlink():
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                not relative_path
                or _probe_language_for_path(relative_path, repo_path=repo_path) != "gleam"
            ):
                continue
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(relative_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
            if (
                repository_service._is_test_path(relative_path)
                or _is_non_operational_profile_path(relative_path)
            ):
                continue
            fallback_paths.add(relative_path)
            if _is_operational_profile_entrypoint_candidate(relative_path, repo_path=repo_path):
                if PurePosixPath(relative_path).name in preferred_names:
                    entrypoint_paths.add(relative_path)
                elif not entrypoint_paths:
                    entrypoint_paths.add(relative_path)
    if not entrypoint_paths and fallback_paths:
        entrypoint_paths.update(sorted(fallback_paths)[:8])
    return entrypoint_paths, support_roots, config_paths


def _janet_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    if not manifest_file.is_file() or manifest_file.is_symlink():
        return set(), set(), set()
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        manifest_text = ""
    config_paths = {normalized_path}
    project_dir = PurePosixPath(normalized_path).parent
    support_roots: set[str] = set()
    entrypoint_paths: set[str] = set()
    fallback_paths: set[str] = set()

    def _record_existing_path(raw_value: str) -> None:
        normalized_candidate = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_value)
        )
        if not normalized_candidate:
            return
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.exists() or candidate_file.is_symlink():
            return
        if candidate_file.is_dir():
            support_roots.add(normalized_candidate)
            return
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
        if _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "janet":
            return
        fallback_paths.add(normalized_candidate)
        if _is_operational_profile_entrypoint_candidate(
            normalized_candidate,
            repo_path=repo_path,
        ):
            entrypoint_paths.add(normalized_candidate)

    for match in re.finditer(r':main\s+"(?P<path>[^"]+)"', manifest_text):
        _record_existing_path(str(match.group("path") or "").strip())
    for match in re.finditer(r':source\s+@?\[(?P<body>[^\]]*)\]', manifest_text, re.DOTALL):
        for source_match in re.finditer(r'"(?P<path>[^"]+)"', str(match.group("body") or "")):
            _record_existing_path(str(source_match.group("path") or "").strip())
    for relative_root in ("src", "lib", "bin", "test", "tests", "examples", "tools"):
        normalized_root = repository_service._normalize_repository_relative_path(
            str(project_dir / relative_root)
        )
        if normalized_root and (repo_path / normalized_root).exists():
            support_roots.add(normalized_root)
    if not entrypoint_paths:
        preferred_basenames = {"init.janet", "main.janet"}
        for candidate_path in sorted(fallback_paths):
            if PurePosixPath(candidate_path).name.lower() in preferred_basenames:
                entrypoint_paths.add(candidate_path)
        if not entrypoint_paths and fallback_paths:
            entrypoint_paths.update(sorted(fallback_paths)[:8])
    return entrypoint_paths, support_roots, config_paths


def _nextflow_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
    *,
    manifest_path: str | None = None,
) -> tuple[set[str], set[str], set[str]]:
    normalized_manifest_path = repository_service._normalize_repository_relative_path(
        manifest_path or ""
    )
    manifest_parent = PurePosixPath(normalized_manifest_path).parent if normalized_manifest_path else PurePosixPath(".")
    root_prefix = "" if str(manifest_parent) in {"", "."} else f"{manifest_parent}/"
    nextflow_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    fallback_paths: set[str] = set()
    config_paths: set[str] = {normalized_manifest_path} if normalized_manifest_path else set()
    preferred_basenames = {"main.nf", "workflow.nf"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate or (root_prefix and not normalized_candidate.startswith(root_prefix)):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        candidate_name = PurePosixPath(normalized_candidate).name.lower()
        if candidate_name in repository_service.nextflow_adapter.NEXTFLOW_CONFIG_BASENAMES:
            if repository_service.nextflow_adapter.is_probable_nextflow_source(
                path=candidate_file,
                text=text,
            ):
                config_paths.add(normalized_candidate)
            continue
        if (
            _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "nextflow"
            or not repository_service.nextflow_adapter.is_probable_nextflow_source(
                path=candidate_file,
                text=text,
            )
        ):
            continue
        nextflow_files.append(normalized_candidate)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
        for alias in repository_service.nextflow_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
    for normalized_candidate in nextflow_files:
        try:
            text = (repo_path / normalized_candidate).read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            continue
        for dependency in repository_service.nextflow_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file:
                imported_files.add(dependency.target_file)
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for relative_root in ("modules", "subworkflows", "conf", "bin", "lib"):
        normalized_root = repository_service._normalize_repository_relative_path(
            str(manifest_parent / relative_root)
        )
        if normalized_root and (repo_path / normalized_root).exists():
            support_roots.add(normalized_root)
    for normalized_candidate in nextflow_files:
        fallback_paths.add(normalized_candidate)
        if (
            _is_operational_profile_entrypoint_candidate(
                normalized_candidate,
                repo_path=repo_path,
            )
            and PurePosixPath(normalized_candidate).name.lower() in preferred_basenames
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        for normalized_candidate in nextflow_files:
            if _is_operational_profile_entrypoint_candidate(
                normalized_candidate,
                repo_path=repo_path,
            ):
                entrypoint_paths.add(normalized_candidate)
        if not entrypoint_paths and fallback_paths:
            entrypoint_paths.update(sorted(fallback_paths)[:12])
    return entrypoint_paths, support_roots, config_paths


def _dhall_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
    *,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_manifest_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_manifest_path:
        return set(), set(), set()
    manifest_parent = PurePosixPath(normalized_manifest_path).parent
    root_prefix = "" if str(manifest_parent) in {"", "."} else f"{manifest_parent}/"
    dhall_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    fallback_paths: set[str] = set()
    preferred_basenames = {"package.dhall", "default.dhall", "defaults.dhall", "main.dhall"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or (root_prefix and not normalized_candidate.startswith(root_prefix))
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "dhall"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.dhall_adapter.is_probable_dhall_source(
            path=candidate_file,
            text=text,
        ):
            continue
        dhall_files.append(normalized_candidate)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
        for alias in repository_service.dhall_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
    for normalized_candidate in dhall_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fallback_paths.add(normalized_candidate)
        if (
            PurePosixPath(normalized_candidate).name.lower() in preferred_basenames
            and _is_operational_profile_entrypoint_candidate(
                normalized_candidate,
                repo_path=repo_path,
            )
        ):
            entrypoint_paths.add(normalized_candidate)
        for import_target, _line_number in repository_service.dhall_adapter.parse_import_statements(
            text
        ):
            target_file = repository_service.dhall_adapter.resolve_import(
                file_path=normalized_candidate,
                import_target=import_target,
                module_index=module_index,
                normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
                resolve_suffix_match=repository_service._resolve_suffix_match,
            )
            if not target_file or target_file == normalized_candidate:
                continue
            imported_files.add(target_file)
            imported_parent = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(target_file).parent)
            )
            if imported_parent:
                support_roots.add(imported_parent)
    if normalized_manifest_path not in entrypoint_paths:
        entrypoint_paths.add(normalized_manifest_path)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(fallback_paths)[:8])
    support_roots.update(
        repository_service._normalize_repository_relative_path(str(PurePosixPath(path).parent))
        for path in imported_files
    )
    return entrypoint_paths, {root for root in support_roots if root}, {normalized_manifest_path}


def _agda_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    if not manifest_file.is_file() or manifest_file.is_symlink():
        return set(), set(), set()
    config_paths = {normalized_path}
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots: set[str] = set()
    entrypoint_paths: set[str] = set()
    fallback_paths: set[str] = set()
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        manifest_text = ""

    def _record_existing_path(raw_value: str) -> None:
        normalized_candidate = repository_service._normalize_repository_relative_path(
            f"{root_prefix}{raw_value}"
        )
        if not normalized_candidate:
            return
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.exists() or candidate_file.is_symlink():
            return
        if candidate_file.is_dir():
            support_roots.add(normalized_candidate)
            return
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
        if _probe_language_for_path(normalized_candidate, repo_path=repo_path) == "agda":
            fallback_paths.add(normalized_candidate)

    for match in re.finditer(r"^\s*include\s*:\s*(?P<body>.+)$", manifest_text, re.MULTILINE):
        for raw_path in str(match.group("body") or "").split():
            _record_existing_path(raw_path.strip())
    for relative_root in ("src", "lib", "test", "tests", "examples"):
        normalized_root = repository_service._normalize_repository_relative_path(
            f"{root_prefix}{relative_root}"
        )
        if normalized_root and (repo_path / normalized_root).exists():
            support_roots.add(normalized_root)
    preferred_basenames = {"Main.agda", "README.agda", "Everything.agda"}
    for support_root in sorted(support_roots):
        search_root = repo_path / support_root
        if not search_root.is_dir():
            continue
        for pattern in (
            "*.agda",
            "*.lagda",
            "*.lagda.md",
            "*.lagda.rst",
            "*.lagda.tex",
            "*.lagda.org",
        ):
            for candidate in sorted(search_root.glob(pattern)):
                if candidate.is_symlink() or not candidate.is_file():
                    continue
                relative_path = repository_service._normalize_repository_relative_path(
                    str(candidate.relative_to(repo_path))
                )
                if _probe_language_for_path(relative_path, repo_path=repo_path) != "agda":
                    continue
                fallback_paths.add(relative_path)
                if PurePosixPath(relative_path).name in preferred_basenames and (
                    _is_operational_profile_entrypoint_candidate(relative_path, repo_path=repo_path)
                ):
                    entrypoint_paths.add(relative_path)
    if not entrypoint_paths and fallback_paths:
        entrypoint_paths.update(sorted(fallback_paths)[:8])
    return entrypoint_paths, support_roots, config_paths


def _coq_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    if not manifest_file.is_file() or manifest_file.is_symlink():
        return set(), set(), set()
    config_paths = {normalized_path}
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots: set[str] = set()
    entrypoint_paths: set[str] = set()
    fallback_paths: set[str] = set()
    imported_files: set[str] = set()
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        manifest_text = ""

    def _record_existing_path(raw_value: str) -> None:
        normalized_candidate = repository_service._normalize_repository_relative_path(
            f"{root_prefix}{raw_value}"
        )
        if not normalized_candidate:
            return
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.exists() or candidate_file.is_symlink():
            return
        if candidate_file.is_dir():
            support_roots.add(normalized_candidate)
            return
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
        if _probe_language_for_path(normalized_candidate, repo_path=repo_path) == "coq":
            fallback_paths.add(normalized_candidate)
            if _is_operational_profile_entrypoint_candidate(
                normalized_candidate,
                repo_path=repo_path,
            ):
                entrypoint_paths.add(normalized_candidate)

    for relative_root in repository_service.coq_adapter.parse_project_roots(manifest_text):
        _record_existing_path(relative_root)
    for relative_source in repository_service.coq_adapter.parse_project_sources(manifest_text):
        _record_existing_path(relative_source)
    for relative_root in ("theories", "src", "lib", "plugins", "examples", "test", "tests"):
        _record_existing_path(relative_root)

    coq_files: list[str] = []
    module_index: dict[str, str] = {}
    for support_root in sorted(support_roots):
        search_root = repo_path / support_root
        if not search_root.is_dir():
            continue
        for candidate in sorted(search_root.rglob("*.v")):
            if candidate.is_symlink() or not candidate.is_file():
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                not relative_path
                or repository_service._is_test_path(relative_path)
                or _is_non_operational_profile_path(relative_path)
            ):
                continue
            try:
                text = candidate.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if not repository_service.coq_adapter.is_probable_coq_source(
                path=Path(relative_path),
                text=text,
            ):
                continue
            coq_files.append(relative_path)
            fallback_paths.add(relative_path)
            for alias in repository_service.coq_adapter.module_aliases_for_path(
                root_path=repo_path,
                file_path=relative_path,
                stable_identifier=repository_service._stable_identifier,
            ):
                module_index.setdefault(alias, relative_path)
    for relative_path in coq_files:
        try:
            text = (repo_path / relative_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for import_target, _line_number in repository_service.coq_adapter.parse_require_modules(
            text
        ):
            target_file = repository_service.coq_adapter.resolve_require_target(
                import_target,
                module_index,
                resolve_suffix_match=repository_service._resolve_suffix_match,
            )
            if not target_file or target_file == relative_path:
                continue
            imported_files.add(target_file)
            imported_parent = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(target_file).parent)
            )
            if imported_parent:
                support_roots.add(imported_parent)
    if not entrypoint_paths:
        preferred_basenames = {"Main.v", "Prelude.v", "Basics.v"}
        for candidate_path in sorted(fallback_paths):
            basename = PurePosixPath(candidate_path).name
            if basename in preferred_basenames or candidate_path not in imported_files:
                if _is_operational_profile_entrypoint_candidate(
                    candidate_path,
                    repo_path=repo_path,
                ):
                    entrypoint_paths.add(candidate_path)
        if not entrypoint_paths and fallback_paths:
            entrypoint_paths.update(sorted(fallback_paths)[:8])
    return entrypoint_paths, support_roots, config_paths


def _lean_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    if not manifest_file.is_file() or manifest_file.is_symlink():
        return set(), set(), set()
    config_paths = {normalized_path}
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots: set[str] = set()
    entrypoint_paths: set[str] = set()
    fallback_paths: set[str] = set()
    imported_files: set[str] = set()
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        manifest_text = ""

    def _package_variants(raw_name: str) -> tuple[str, ...]:
        normalized_name = str(raw_name or "").strip()
        if not normalized_name:
            return ()
        compact = normalized_name.replace("-", "").replace("_", "")
        camel = "".join(
            segment[:1].upper() + segment[1:]
            for segment in re.split(r"[-_]+", normalized_name)
            if segment
        )
        return tuple(
            value
            for value in {normalized_name, compact, camel}
            if value and "/" not in value and "." not in value
        )

    def _record_existing_path(raw_value: str) -> None:
        normalized_candidate = repository_service._normalize_repository_relative_path(
            f"{root_prefix}{raw_value}"
        )
        if not normalized_candidate:
            return
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.exists() or candidate_file.is_symlink():
            return
        if candidate_file.is_dir():
            support_roots.add(normalized_candidate)
            return
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
        if _probe_language_for_path(normalized_candidate, repo_path=repo_path) == "lean":
            fallback_paths.add(normalized_candidate)
            if _is_operational_profile_entrypoint_candidate(
                normalized_candidate,
                repo_path=repo_path,
            ):
                entrypoint_paths.add(normalized_candidate)

    for package_name in repository_service.lean_adapter.parse_package_names(manifest_text):
        for candidate_name in _package_variants(package_name):
            _record_existing_path(candidate_name)
            _record_existing_path(f"{candidate_name}.lean")
    for relative_root in (
        "Lean",
        "Mathlib",
        "Batteries",
        "Std",
        "src",
        "Source",
        "source",
        "library",
        "lib",
        "examples",
        "Examples",
        "test",
        "tests",
    ):
        _record_existing_path(relative_root)

    lean_files: list[str] = []
    module_index: dict[str, str] = {}
    for support_root in sorted(support_roots):
        search_root = repo_path / support_root
        if not search_root.is_dir():
            continue
        for candidate in sorted(search_root.rglob("*.lean")):
            if candidate.is_symlink() or not candidate.is_file():
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                not relative_path
                or repository_service._is_test_path(relative_path)
                or _is_non_operational_profile_path(relative_path)
            ):
                continue
            try:
                text = candidate.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if not repository_service.lean_adapter.is_probable_lean_source(
                path=Path(relative_path),
                text=text,
            ):
                continue
            lean_files.append(relative_path)
            fallback_paths.add(relative_path)
            for alias in repository_service.lean_adapter.module_aliases_for_path(
                root_path=repo_path,
                file_path=relative_path,
                stable_identifier=repository_service._stable_identifier,
            ):
                module_index.setdefault(alias, relative_path)
    for relative_path in lean_files:
        try:
            text = (repo_path / relative_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for import_target, _line_number in repository_service.lean_adapter.parse_import_modules(
            text
        ):
            target_file = repository_service.lean_adapter.resolve_import_target(
                import_target,
                module_index,
                resolve_suffix_match=repository_service._resolve_suffix_match,
            )
            if not target_file or target_file == relative_path:
                continue
            imported_files.add(target_file)
            imported_parent = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(target_file).parent)
            )
            if imported_parent:
                support_roots.add(imported_parent)
    if not entrypoint_paths:
        preferred_basenames = {
            "Main.lean",
            "Lean.lean",
            "Mathlib.lean",
            "Batteries.lean",
            "Std.lean",
        }
        for candidate_path in sorted(fallback_paths):
            basename = PurePosixPath(candidate_path).name
            if basename in preferred_basenames or candidate_path not in imported_files:
                if _is_operational_profile_entrypoint_candidate(
                    candidate_path,
                    repo_path=repo_path,
                ):
                    entrypoint_paths.add(candidate_path)
        if not entrypoint_paths and fallback_paths:
            entrypoint_paths.update(sorted(fallback_paths)[:8])
    return entrypoint_paths, support_roots, config_paths


def _idris_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    if (
        not manifest_file.is_file()
        or manifest_file.is_symlink()
        or _probe_language_for_path(normalized_path, repo_path=repo_path) != "idris"
    ):
        return set(), set(), set()
    config_paths = {normalized_path}
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots: set[str] = set()
    entrypoint_paths: set[str] = set()
    fallback_paths: set[str] = set()
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        manifest_text = ""
    source_dirs: list[str] = []
    module_names: list[str] = []
    main_modules: list[str] = []
    for match in repository_service.idris_adapter._IPKG_ASSIGNMENT_RE.finditer(manifest_text):
        key = str(match.group("key") or "").strip().lower().replace("-", "")
        value = str(match.group("value") or "").strip()
        if not key or not value:
            continue
        if key == "sourcedir":
            source_dir = value.split()[0].strip()
            if source_dir:
                source_dirs.append(source_dir)
        elif key == "modules":
            module_names.extend(
                candidate.strip()
                for candidate in re.split(r"[,\s]+", value)
                if candidate.strip()
            )
        elif key == "main":
            main_module = value.split()[0].strip()
            if main_module:
                main_modules.append(main_module)

    normalized_source_roots = [
        repository_service._normalize_repository_relative_path(f"{root_prefix}{raw_root}")
        for raw_root in (source_dirs or ["src", "lib", "source"])
    ]
    normalized_source_roots = [root for root in normalized_source_roots if root]
    for support_root in normalized_source_roots:
        if (repo_path / support_root).exists():
            support_roots.add(support_root)
    for relative_root in ("app", "tests", "test", "samples", "examples"):
        normalized_root = repository_service._normalize_repository_relative_path(
            f"{root_prefix}{relative_root}"
        )
        if normalized_root and (repo_path / normalized_root).exists():
            support_roots.add(normalized_root)

    def _record_module(raw_module: str, *, prefer_entrypoint: bool) -> None:
        normalized_module = str(raw_module or "").strip()
        if not normalized_module:
            return
        module_path = normalized_module.replace(".", "/")
        search_roots = normalized_source_roots or [
            repository_service._normalize_repository_relative_path(root_prefix)
        ]
        for source_root in search_roots:
            if not source_root:
                continue
            for suffix in (".idr", ".lidr"):
                normalized_candidate = repository_service._normalize_repository_relative_path(
                    f"{source_root}/{module_path}{suffix}"
                )
                if not normalized_candidate:
                    continue
                candidate_file = repo_path / normalized_candidate
                if not candidate_file.exists() or candidate_file.is_symlink():
                    continue
                support_roots.add(source_root)
                fallback_paths.add(normalized_candidate)
                if prefer_entrypoint and _is_operational_profile_entrypoint_candidate(
                    normalized_candidate,
                    repo_path=repo_path,
                ):
                    entrypoint_paths.add(normalized_candidate)
                return

    for module_name in module_names:
        _record_module(module_name, prefer_entrypoint=False)
    for module_name in main_modules:
        _record_module(module_name, prefer_entrypoint=True)
    if not entrypoint_paths:
        preferred_basenames = {"Main.idr", "Main.lidr"}
        for candidate_path in sorted(fallback_paths):
            if PurePosixPath(candidate_path).name in preferred_basenames:
                entrypoint_paths.add(candidate_path)
        if not entrypoint_paths and fallback_paths:
            entrypoint_paths.update(sorted(fallback_paths)[:8])
    return entrypoint_paths, support_roots, config_paths


def _raku_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    if not manifest_file.is_file() or manifest_file.is_symlink():
        return set(), set(), set()
    config_paths = {normalized_path}
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots: set[str] = set()
    entrypoint_paths: set[str] = set()
    fallback_paths: set[str] = set()
    try:
        manifest_payload = json.loads(manifest_file.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        manifest_payload = {}
    provides = manifest_payload.get("provides")
    if isinstance(provides, dict):
        for raw_path in provides.values():
            if not isinstance(raw_path, str) or not raw_path.strip():
                continue
            normalized_candidate = repository_service._normalize_repository_relative_path(
                f"{root_prefix}{raw_path.strip()}"
            )
            if not normalized_candidate:
                continue
            candidate_file = repo_path / normalized_candidate
            if not candidate_file.exists() or candidate_file.is_symlink():
                continue
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(normalized_candidate).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
            if _probe_language_for_path(normalized_candidate, repo_path=repo_path) == "raku":
                fallback_paths.add(normalized_candidate)
    for raw_path in manifest_payload.get("bin", ()) if isinstance(manifest_payload, dict) else ():
        if not isinstance(raw_path, str) or not raw_path.strip():
            continue
        normalized_candidate = repository_service._normalize_repository_relative_path(
            f"{root_prefix}bin/{PurePosixPath(raw_path.strip()).name}"
        )
        if not normalized_candidate:
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.exists() or candidate_file.is_symlink():
            continue
        support_roots.add("bin" if not root_prefix else f"{root_prefix}bin".rstrip("/"))
        if _probe_language_for_path(normalized_candidate, repo_path=repo_path) == "raku":
            entrypoint_paths.add(normalized_candidate)
    for relative_root in ("lib", "bin", "t", "xt", "test", "tests", "examples", "tools"):
        normalized_root = repository_service._normalize_repository_relative_path(
            f"{root_prefix}{relative_root}"
        )
        if normalized_root and (repo_path / normalized_root).exists():
            support_roots.add(normalized_root)
    if not entrypoint_paths:
        preferred_basenames = {"main.raku", "main.p6", "application.raku"}
        for candidate_path in sorted(fallback_paths):
            if PurePosixPath(candidate_path).name.lower() in preferred_basenames:
                entrypoint_paths.add(candidate_path)
        if not entrypoint_paths and fallback_paths:
            entrypoint_paths.update(sorted(fallback_paths)[:8])
    return entrypoint_paths, support_roots, config_paths


def _v_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    if (
        not manifest_file.is_file()
        or manifest_file.is_symlink()
        or _probe_language_for_path(normalized_path, repo_path=repo_path) != "v"
    ):
        return set(), set(), set()
    manifest_parent = PurePosixPath(normalized_path).parent
    config_paths = {normalized_path}
    support_roots: set[str] = set()
    discovered_paths: set[str] = set()
    for candidate_root in (
        manifest_parent,
        manifest_parent / "src",
        manifest_parent / "cmd",
        manifest_parent / "examples",
        manifest_parent / "modules",
        manifest_parent / "vlib",
    ):
        normalized_root = repository_service._normalize_repository_relative_path(
            str(candidate_root)
        )
        if normalized_root and (repo_path / normalized_root).exists():
            support_roots.add(normalized_root)
        search_root = repo_path / candidate_root
        if not search_root.is_dir():
            continue
        for candidate in sorted(search_root.rglob("*.v")):
            if not candidate.is_file() or candidate.is_symlink():
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                not relative_path
                or _probe_language_for_path(relative_path, repo_path=repo_path) != "v"
            ):
                continue
            discovered_paths.add(relative_path)
            support_root = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(relative_path).parent)
            )
            if support_root:
                support_roots.add(support_root)
    entrypoint_paths = {
        candidate_path
        for candidate_path in discovered_paths
        if PurePosixPath(candidate_path).name == "main.v"
        and _is_operational_profile_entrypoint_candidate(candidate_path, repo_path=repo_path)
    }
    if not entrypoint_paths:
        for candidate_path in sorted(discovered_paths):
            if _is_operational_profile_entrypoint_candidate(candidate_path, repo_path=repo_path):
                entrypoint_paths.add(candidate_path)
            if len(entrypoint_paths) >= 8:
                break
    return entrypoint_paths, support_roots, config_paths


def _scheme_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    manifest_file = repo_path / normalized_path
    try:
        text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set(), set(), config_paths
    if not repository_service.scheme_adapter.is_probable_scheme_source(
        path=Path(normalized_path),
        text=text,
    ):
        return set(), set(), config_paths
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}lib",
        f"{root_prefix}scheme",
        f"{root_prefix}s",
    }
    entrypoint_paths: set[str] = set()
    search_root = repo_path / project_dir
    for suffix in ("*.scm", "*.ss", "*.sld", "*.sps"):
        for candidate in sorted(search_root.rglob(suffix)):
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                not relative_path
                or repository_service._is_test_path(relative_path)
                or _is_non_operational_profile_path(relative_path)
                or _probe_language_for_path(relative_path, repo_path=repo_path) != "scheme"
            ):
                continue
            entrypoint_paths.add(relative_path)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(relative_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, support_roots, config_paths


def _racket_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    manifest_file = repo_path / normalized_path
    try:
        text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set(), set(), config_paths
    if not repository_service.racket_adapter.is_probable_racket_source(
        path=Path(normalized_path),
        text=text,
    ):
        return set(), set(), config_paths
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}private",
        f"{root_prefix}scribblings",
        f"{root_prefix}racket",
    }
    entrypoint_paths: set[str] = set()
    search_root = repo_path / project_dir
    for suffix in ("*.rkt", "*.rktl"):
        for candidate in sorted(search_root.rglob(suffix)):
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                not relative_path
                or repository_service._is_test_path(relative_path)
                or _is_non_operational_profile_path(relative_path)
                or PurePosixPath(relative_path).name.lower() == "info.rkt"
                or _probe_language_for_path(relative_path, repo_path=repo_path) != "racket"
            ):
                continue
            entrypoint_paths.add(relative_path)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(relative_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, support_roots, config_paths


def _rockspec_profile_hints(
    repo_path: Path,
    rockspec_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(rockspec_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    repo_name = re.sub(r"[^a-z0-9_]+", "_", repo_path.name.lower()).strip("_")
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}lua",
        f"{root_prefix}lib",
        f"{root_prefix}src",
    }
    entrypoint_paths = {
        f"{root_prefix}init.lua",
        f"{root_prefix}main.lua",
        f"{root_prefix}lua/{repo_name}.lua",
        f"{root_prefix}lua/{repo_name}/init.lua",
        f"{root_prefix}lib/{repo_name}.lua",
        f"{root_prefix}lib/{repo_name}/init.lua",
        f"{root_prefix}src/{repo_name}.lua",
        f"{root_prefix}src/{repo_name}/init.lua",
    }
    config_paths = {normalized_path}
    manifest_path = repo_path / normalized_path
    try:
        text = manifest_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return entrypoint_paths, support_roots, config_paths
    package_match = _LUA_ROCKSPEC_PACKAGE_RE.search(text)
    if package_match is not None:
        package_name = re.sub(r"[^a-z0-9_]+", "_", package_match.group("name").lower()).strip("_")
        if package_name:
            entrypoint_paths.update(
                {
                    f"{root_prefix}lua/{package_name}.lua",
                    f"{root_prefix}lua/{package_name}/init.lua",
                    f"{root_prefix}lib/{package_name}.lua",
                    f"{root_prefix}lib/{package_name}/init.lua",
                    f"{root_prefix}src/{package_name}.lua",
                    f"{root_prefix}src/{package_name}/init.lua",
                }
            )
    for match in _LUA_ROCKSPEC_MODULE_RE.finditer(text):
        module_path = repository_service._normalize_repository_relative_path(
            str(project_dir / match.group("path"))
        )
        if module_path:
            entrypoint_paths.add(module_path)
    return entrypoint_paths, support_roots, config_paths


def _luau_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    manifest_file = repo_path / normalized_path
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}lib",
        f"{root_prefix}modules",
        f"{root_prefix}scripts",
        f"{root_prefix}server",
        f"{root_prefix}client",
        f"{root_prefix}shared",
    }
    entrypoint_paths: set[str] = set()
    luau_files: list[str] = []
    preferred_basenames = {"init.lua", "init.luau", "main.lua", "main.luau", "module.luau"}
    package_name: str | None = None
    try:
        text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if PurePosixPath(normalized_path).name.lower() == "default.project.json":
        for match in _LUAU_PROJECT_PATH_RE.finditer(text):
            target_path = repository_service._normalize_repository_relative_path(
                str(project_dir / match.group("path"))
            )
            if not target_path:
                continue
            target_file = repo_path / target_path
            if target_file.is_file() and target_file.suffix.lower() in {".lua", ".luau"}:
                entrypoint_paths.add(target_path)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(target_path).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
            elif target_file.is_dir():
                support_roots.add(target_path)
    elif PurePosixPath(normalized_path).name.lower() == "wally.toml":
        package_match = _LUAU_WALLY_NAME_RE.search(text)
        if package_match is not None:
            package_name = str(package_match.group("name") or "").strip().rsplit("/", 1)[-1] or None
    search_roots = [
        repo_path / project_dir / name
        for name in ("src", "lib", "modules", "scripts", "server", "client", "shared", "app")
    ]
    search_roots.append(repo_path / project_dir)
    seen_files: set[str] = set()
    for search_root in search_roots:
        if not search_root.is_dir():
            continue
        for suffix in ("*.luau", "*.lua"):
            for candidate in sorted(search_root.rglob(suffix)):
                if not candidate.is_file() or candidate.is_symlink():
                    continue
                relative_path = repository_service._normalize_repository_relative_path(
                    str(candidate.relative_to(repo_path))
                )
                if (
                    not relative_path
                    or relative_path in seen_files
                    or repository_service._is_test_path(relative_path)
                    or _is_non_operational_profile_path(relative_path)
                    or _probe_language_for_path(relative_path, repo_path=repo_path) != "luau"
                ):
                    continue
                seen_files.add(relative_path)
                luau_files.append(relative_path)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(relative_path).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
    if package_name:
        for candidate in (
            f"{root_prefix}src/{package_name}.luau",
            f"{root_prefix}src/{package_name}.lua",
            f"{root_prefix}src/init.luau",
            f"{root_prefix}src/init.lua",
        ):
            if candidate in seen_files:
                entrypoint_paths.add(candidate)
    for relative_path in luau_files:
        pure_path = PurePosixPath(relative_path)
        if pure_path.name.lower() in preferred_basenames or len(pure_path.parts) <= 2:
            entrypoint_paths.add(relative_path)
    if not entrypoint_paths:
        entrypoint_paths.update(luau_files[:8])
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _solidity_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(config_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    config_paths = {normalized_path}
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}contracts",
        f"{root_prefix}src",
        f"{root_prefix}script",
        f"{root_prefix}scripts",
        f"{root_prefix}interfaces",
        f"{root_prefix}libraries",
    }
    entrypoint_paths: set[str] = set()
    search_roots = {
        repository_service._normalize_repository_relative_path(f"{root_prefix}contracts"),
        repository_service._normalize_repository_relative_path(f"{root_prefix}src"),
        repository_service._normalize_repository_relative_path(f"{root_prefix}script"),
        repository_service._normalize_repository_relative_path(f"{root_prefix}scripts"),
    }
    manifest_path = repo_path / normalized_path
    basename = PurePosixPath(normalized_path).name.lower()
    if basename == "foundry.toml":
        try:
            text = manifest_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        for match in _FOUNDRY_STRING_FIELD_RE.finditer(text):
            raw_value = str(match.group("value") or "").strip()
            if not raw_value:
                continue
            resolved_root = repository_service._normalize_repository_relative_path(
                str(project_dir / raw_value)
            )
            if resolved_root and match.group("field").lower() != "test":
                search_roots.add(resolved_root)
                support_roots.add(resolved_root)
        for match in _FOUNDRY_LIST_FIELD_RE.finditer(text):
            for quoted_segment in _QUOTED_SEGMENT_RE.finditer(str(match.group("body") or "")):
                raw_value = str(quoted_segment.group("value") or "").strip()
                if not raw_value:
                    continue
                resolved_root = repository_service._normalize_repository_relative_path(
                    str(project_dir / raw_value)
                )
                if resolved_root:
                    support_roots.add(resolved_root)
    project_root = repo_path / project_dir
    for search_root in sorted(root for root in search_roots if root):
        search_path = repo_path / search_root
        if not search_path.is_dir():
            continue
        support_roots.add(search_root)
        for candidate in sorted(search_path.rglob("*.sol")):
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                relative_path
                and not repository_service._is_test_path(relative_path)
                and not _is_non_operational_profile_path(relative_path)
            ):
                entrypoint_paths.add(relative_path)
    if entrypoint_paths:
        return entrypoint_paths, support_roots, config_paths
    for fallback_root in ("contracts", "src"):
        candidate_root = project_root / fallback_root
        if not candidate_root.is_dir():
            continue
        relative_root = repository_service._normalize_repository_relative_path(
            str(candidate_root.relative_to(repo_path))
        )
        if relative_root:
            support_roots.add(relative_root)
        for candidate in sorted(candidate_root.rglob("*.sol")):
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                relative_path
                and not repository_service._is_test_path(relative_path)
                and not _is_non_operational_profile_path(relative_path)
            ):
                entrypoint_paths.add(relative_path)
    return entrypoint_paths, support_roots, config_paths


def _apex_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    manifest_file = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        manifest_text = ""
    try:
        manifest_payload = json.loads(manifest_text) if manifest_text.strip() else {}
    except json.JSONDecodeError:
        manifest_payload = {}

    package_roots: list[str] = []
    for raw_entry in manifest_payload.get("packageDirectories", ()):
        if not isinstance(raw_entry, dict):
            continue
        raw_path = str(raw_entry.get("path") or "").strip()
        if not raw_path:
            continue
        resolved_path = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_path)
        )
        if resolved_path and resolved_path not in package_roots:
            package_roots.append(resolved_path)
    if not package_roots:
        for fallback_path in (
            repository_service._normalize_repository_relative_path(str(project_dir / "force-app")),
            repository_service._normalize_repository_relative_path(str(project_dir / "src")),
            repository_service._normalize_repository_relative_path(str(project_dir / "classes")),
            repository_service._normalize_repository_relative_path(str(project_dir / "triggers")),
        ):
            if fallback_path and fallback_path not in package_roots:
                package_roots.append(fallback_path)

    search_roots: list[str] = []
    for package_root in package_roots:
        for candidate_root in (
            package_root,
            repository_service._normalize_repository_relative_path(
                f"{package_root}/main/default/classes"
            ),
            repository_service._normalize_repository_relative_path(
                f"{package_root}/main/default/triggers"
            ),
            repository_service._normalize_repository_relative_path(f"{package_root}/classes"),
            repository_service._normalize_repository_relative_path(f"{package_root}/triggers"),
        ):
            if not candidate_root or candidate_root in search_roots:
                continue
            if (repo_path / candidate_root).exists():
                search_roots.append(candidate_root)

    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    for search_root in search_roots:
        search_path = repo_path / search_root
        if not search_path.is_dir():
            continue
        support_roots.add(search_root)
        apex_candidates = sorted(search_path.rglob("*.cls")) + sorted(
            search_path.rglob("*.trigger")
        )
        for candidate_path in apex_candidates:
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate_path.relative_to(repo_path))
            )
            if not relative_path or _is_non_operational_profile_path(relative_path):
                continue
            try:
                text = candidate_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if not repository_service.apex_adapter.is_probable_apex_source(
                path=Path(relative_path),
                text=text,
            ):
                continue
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(relative_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
            if repository_service.apex_adapter.is_probable_test_source(
                path=Path(relative_path),
                text=text,
            ):
                continue
            entrypoint_paths.add(relative_path)
    return entrypoint_paths, support_roots, config_paths


def _wolfram_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    manifest_file = repo_path / normalized_path
    try:
        text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set(), set(), config_paths
    if not repository_service.wolfram_adapter.is_probable_wolfram_source(
        path=Path(normalized_path),
        text=text,
    ):
        return set(), set(), config_paths

    project_dir = PurePosixPath(normalized_path).parent
    search_roots: list[str] = []
    support_roots: set[str] = set()
    context_entrypoint_stems: set[str] = set()
    for entry in repository_service.wolfram_adapter.paclet_kernel_entries(
        text,
        manifest_path=normalized_path,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
    ):
        root_path = str(entry.get("root_path") or "").strip()
        if root_path and root_path not in search_roots and (repo_path / root_path).is_dir():
            search_roots.append(root_path)
            support_roots.add(root_path)
        for context_name in entry.get("contexts", ()):
            normalized_context = repository_service.wolfram_adapter.normalize_context_name(
                str(context_name or "")
            )
            if normalized_context:
                context_entrypoint_stems.add(normalized_context.rstrip("`").split("`")[-1])

    for default_root in ("Kernel", "Resources", "Packages", "Applications"):
        candidate_root = repository_service._normalize_repository_relative_path(
            str(project_dir / default_root)
        )
        if (
            candidate_root
            and candidate_root not in search_roots
            and (repo_path / candidate_root).is_dir()
        ):
            search_roots.append(candidate_root)
            support_roots.add(candidate_root)

    project_dir_name = project_dir.name
    entrypoint_paths: set[str] = set()
    if project_dir_name:
        for suffix in (".wl", ".wls", ".m"):
            candidate_path = repository_service._normalize_repository_relative_path(
                str(project_dir / f"{project_dir_name}{suffix}")
            )
            if not candidate_path or not (repo_path / candidate_path).is_file():
                continue
            try:
                candidate_text = (repo_path / candidate_path).read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError:
                continue
            if not repository_service.wolfram_adapter.is_probable_wolfram_source(
                path=Path(candidate_path),
                text=candidate_text,
            ):
                continue
            entrypoint_paths.add(candidate_path)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(candidate_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)

    for search_root in search_roots:
        search_path = repo_path / search_root
        if not search_path.is_dir():
            continue
        for suffix in ("*.wl", "*.wls", "*.m"):
            for candidate_path in sorted(search_path.rglob(suffix)):
                relative_path = repository_service._normalize_repository_relative_path(
                    str(candidate_path.relative_to(repo_path))
                )
                if (
                    not relative_path
                    or _is_non_operational_profile_path(relative_path)
                    or PurePosixPath(relative_path).name.lower()
                    in {"pacletinfo.m", "pacletinfo.wl"}
                ):
                    continue
                try:
                    candidate_text = candidate_path.read_text(
                        encoding="utf-8",
                        errors="replace",
                    )
                except OSError:
                    continue
                if not repository_service.wolfram_adapter.is_probable_wolfram_source(
                    path=Path(relative_path),
                    text=candidate_text,
                ):
                    continue
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(relative_path).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
                lowered_name = PurePosixPath(relative_path).name.lower()
                if lowered_name in {"init.m", "init.wl", "init.wls"}:
                    entrypoint_paths.add(relative_path)
                    continue
                if PurePosixPath(relative_path).stem in context_entrypoint_stems:
                    entrypoint_paths.add(relative_path)

    if entrypoint_paths:
        return entrypoint_paths, support_roots, config_paths

    fallback_entrypoints: set[str] = set()
    for search_root in search_roots:
        search_path = repo_path / search_root
        if not search_path.is_dir():
            continue
        for suffix in ("*.wl", "*.wls", "*.m"):
            for candidate_path in sorted(search_path.rglob(suffix)):
                relative_path = repository_service._normalize_repository_relative_path(
                    str(candidate_path.relative_to(repo_path))
                )
                if (
                    relative_path
                    and not _is_non_operational_profile_path(relative_path)
                    and PurePosixPath(relative_path).name.lower()
                    not in {"pacletinfo.m", "pacletinfo.wl"}
                ):
                    fallback_entrypoints.add(relative_path)
    return fallback_entrypoints, support_roots, config_paths


def _repo_profile_candidate_paths(
    *,
    repo_path: Path,
    focus_paths: list[str],
    max_files: int,
) -> list[str]:
    return _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=[],
        bridge_paths=focus_paths,
        include_patterns=DEFAULT_INCLUDE_PATTERNS,
        max_files=min(max_files, 512),
    )


def _repo_profile_config_paths(
    *,
    repo_path: Path,
    focus_paths: list[str],
) -> list[str]:
    del focus_paths

    excluded_dirnames = set(repository_service._DEFAULT_EXCLUDED_PATH_PARTS)
    git_relative_files = _git_repo_relative_files(repo_path)
    config_paths: set[str] = set()

    def _add_if_config(relative_path: str) -> None:
        normalized_path = repository_service._normalize_repository_relative_path(relative_path)
        if not normalized_path:
            return
        if any(part in excluded_dirnames for part in PurePosixPath(normalized_path).parts[:-1]):
            return
        if not (
            _is_repo_profile_manifest_name(PurePosixPath(normalized_path).name)
            or _is_xpp_descriptor_config_path(repo_path, normalized_path)
            or _is_cfml_box_config_path(repo_path, normalized_path)
            or _is_eiffel_project_config_path(repo_path, normalized_path)
            or _is_odin_ols_config_path(repo_path, normalized_path)
            or _is_cue_module_config_path(repo_path, normalized_path)
            or _is_purescript_bower_config_path(repo_path, normalized_path)
            or _is_rescript_config_path(repo_path, normalized_path)
            or _is_moonbit_config_path(repo_path, normalized_path)
            or _is_puppet_metadata_config_path(repo_path, normalized_path)
            or _is_qmake_project_config_path(repo_path, normalized_path)
        ):
            return
        candidate = repo_path / normalized_path
        if not candidate.exists() or not candidate.is_file() or candidate.is_symlink():
            return
        config_paths.add(normalized_path)

    if git_relative_files is not None:
        for relative_path in git_relative_files:
            _add_if_config(relative_path)
    else:
        seen: set[Path] = set()
        for dirpath, dirnames, filenames in os.walk(repo_path):
            dirnames[:] = [name for name in dirnames if name not in excluded_dirnames]
            for filename in filenames:
                candidate = Path(dirpath) / filename
                if candidate in seen or not candidate.is_file() or candidate.is_symlink():
                    continue
                seen.add(candidate)
                relative_path = str(candidate.relative_to(repo_path)).replace("\\", "/")
                _add_if_config(relative_path)

    ordered_config_paths = sorted(
        config_paths,
        key=lambda relative_path: _probe_collection_rank(relative_path, repo_path=repo_path),
    )
    return sorted(ordered_config_paths[:512])


def _seeded_repo_profile_candidate_paths(
    *,
    repo_path: Path,
    focus_paths: list[str],
    max_files: int,
    entrypoint_candidates: set[str],
    support_root_candidates: set[str],
    config_paths: list[str],
    detected_ecosystems: set[str],
    detected_ecosystem_scores: Counter[str] | None = None,
) -> list[str]:
    existing_entrypoints = [
        path
        for path in _candidate_existing_paths(
            repo_path,
            paths=entrypoint_candidates,
        )
        if _is_repo_profile_code_candidate(path, repo_path=repo_path)
        and not repository_service._is_test_path(path)
        and not _is_non_operational_profile_path_for_ecosystems(
            path,
            ecosystems=detected_ecosystems,
            repo_path=repo_path,
        )
    ]
    existing_support_roots = _candidate_existing_leaf_roots(
        repo_path,
        roots=support_root_candidates,
        entrypoint_paths=set(existing_entrypoints),
    )
    bridge_roots = list(existing_support_roots)
    if not bridge_roots:
        config_parent_roots = {
            normalized_parent
            for config_path in config_paths
            if (
                normalized_parent := repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(config_path).parent)
                )
            )
        }
        bridge_roots = _candidate_existing_leaf_roots(
            repo_path,
            roots=config_parent_roots,
            entrypoint_paths=set(existing_entrypoints),
        )
    if not bridge_roots and not existing_entrypoints:
        return []
    support_roots = set(existing_support_roots or bridge_roots)
    seed_paths = _balanced_profile_paths(
        paths=existing_entrypoints,
        detected_ecosystems=detected_ecosystems,
        repo_path=repo_path,
        support_roots=support_roots,
        limit=_profile_entrypoint_target_count(detected_ecosystems),
        ecosystem_scores=detected_ecosystem_scores,
    )
    if not _should_use_seeded_profile_candidate_scan(
        seed_paths=seed_paths,
        bridge_paths=bridge_roots,
    ):
        return []
    seeded_candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=seed_paths,
        bridge_paths=bridge_roots,
        include_patterns=DEFAULT_INCLUDE_PATTERNS,
        max_files=min(max_files, 512),
    )
    if seeded_candidate_paths:
        return seeded_candidate_paths
    if seed_paths:
        return list(seed_paths)
    return _repo_profile_candidate_paths(
        repo_path=repo_path,
        focus_paths=focus_paths,
        max_files=max_files,
    )


def _is_repo_profile_code_candidate(
    path: str,
    *,
    repo_path: Path | None = None,
) -> bool:
    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return False
    basename = PurePosixPath(normalized_path).name.lower()
    suffix = PurePosixPath(normalized_path).suffix.lower()
    language = _probe_language_for_path(normalized_path, repo_path=repo_path)
    if repo_path is not None and _is_xpp_descriptor_config_path(repo_path, normalized_path):
        return False
    if repo_path is not None and _is_cfml_box_config_path(repo_path, normalized_path):
        return False
    if repo_path is not None and _is_purescript_bower_config_path(repo_path, normalized_path):
        return False
    if repo_path is not None and _is_rescript_config_path(repo_path, normalized_path):
        return False
    if repo_path is not None and _is_moonbit_config_path(repo_path, normalized_path):
        return False
    if repo_path is not None and _is_delphi_project_config_path(repo_path, normalized_path):
        return False
    if repo_path is not None and _is_cue_module_config_path(repo_path, normalized_path):
        return False
    if _is_repo_profile_manifest_name(basename) and not (
        (language == "dhall" and basename == "package.dhall")
        or (language == "dockerfile" and basename in {"dockerfile", "containerfile"})
        or (language == "gams" and suffix == ".gms")
        or (language == "openscad" and suffix == ".scad")
        or (language == "nix" and suffix == ".nix")
        or (language == "v" and basename == "v.mod")
        or (language == "vbscript" and suffix == ".wsf")
        or (language == "labview" and suffix in {".lvclass", ".lvlib"})
        or (
            language == "starlark"
            and basename
            in {"build", "build.bazel", "module.bazel", "workspace", "workspace.bazel"}
        )
    ):
        return False
    return (
        suffix != ".hrl"
        and language not in repository_service._NON_CODE_GRAPH_LANGUAGES
        and language not in repository_service._ENTRYPOINT_DEMOTED_LANGUAGES
        and language not in {"unknown", "txt"}
    )


def _candidate_ecosystems_for_path(
    path: str,
    *,
    repo_path: Path | None = None,
) -> set[str]:
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
        "wgsl": {"wgsl"},
        "less": {"less"},
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


def _best_repository_path_priority(
    path: str,
    *,
    repo_path: Path | None = None,
) -> tuple[int, str]:
    matched_ecosystems = sort_repository_languages(
        _candidate_ecosystems_for_path(path, repo_path=repo_path)
    )
    if not matched_ecosystems:
        return repository_language_priority(None)
    best_match = matched_ecosystems[0]
    return repository_language_priority(best_match)


def _ordered_detected_ecosystems(
    detected_ecosystems: set[str],
) -> list[str]:
    return sort_repository_languages(detected_ecosystems)


def _ordered_operational_ecosystems(
    detected_ecosystems: set[str],
    *,
    ecosystem_scores: Counter[str] | None = None,
) -> list[str]:
    if ecosystem_scores:
        return sort_repository_languages_by_score(
            detected_ecosystems,
            scores=ecosystem_scores,
        )
    return _ordered_detected_ecosystems(detected_ecosystems)


def _profile_signal_depth_score(path: str) -> int:
    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return 0
    depth = max(0, len(PurePosixPath(normalized_path).parts) - 1)
    return max(2, 16 - min(depth, 12))


def _register_candidate_ecosystems(
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


def _candidate_ecosystem_counts(
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
        for ecosystem in _candidate_ecosystems_for_path(candidate_path, repo_path=repo_path):
            canonical = canonical_repository_language(ecosystem)
            if canonical in target_ecosystems:
                counts[canonical] += 1
    return counts


def _cuda_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    cuda_files = sorted(
        {
            normalized_path
            for candidate_path in candidate_file_paths
            if (
                normalized_path := repository_service._normalize_repository_relative_path(
                    candidate_path
                )
            )
            and PurePosixPath(normalized_path).suffix.lower() in {".cu", ".cuh"}
        }
    )
    if not cuda_files:
        return set(), set(), set()
    entrypoint_paths = {
        path
        for path in cuda_files
        if PurePosixPath(path).suffix.lower() == ".cu"
        and not repository_service._is_test_path(path)
        and not _is_non_operational_profile_path(path)
    }
    prioritized_entrypoints = {
        path
        for path in entrypoint_paths
        if PurePosixPath(path).name.lower() in {"app.cu", "example.cu", "index.cu", "main.cu", "sample.cu"}
        or "main" in PurePosixPath(path).stem.lower()
    }
    if prioritized_entrypoints:
        entrypoint_paths = prioritized_entrypoints
    if not entrypoint_paths:
        entrypoint_paths = {
            path
            for path in cuda_files
            if PurePosixPath(path).suffix.lower() == ".cu"
            and not repository_service._is_test_path(path)
        }
    support_roots = {
        repository_service._normalize_repository_relative_path(str(PurePosixPath(path).parent))
        for path in cuda_files
    }
    support_roots.update(
        repository_service._normalize_repository_relative_path(str(PurePosixPath(path).parts[0]))
        for path in cuda_files
        if PurePosixPath(path).parts
    )
    config_paths: set[str] = set()
    candidate_config_dirs: set[str] = set()
    for entrypoint_path in entrypoint_paths:
        parent = PurePosixPath(entrypoint_path).parent
        for candidate_dir in (parent, parent.parent):
            normalized_dir = repository_service._normalize_repository_relative_path(
                str(candidate_dir)
            )
            if normalized_dir:
                candidate_config_dirs.add(normalized_dir)
    for normalized_dir in sorted(candidate_config_dirs):
        directory = repo_path / normalized_dir
        if not directory.is_dir():
            continue
        try:
            child_paths = sorted(directory.iterdir(), key=lambda path: path.name.lower())
        except OSError:
            continue
        for child_path in child_paths:
            if not child_path.is_file() or child_path.is_symlink():
                continue
            child_name = child_path.name
            if not (
                _is_repo_profile_manifest_name(child_name)
                or _is_qmake_project_config_path(
                    repo_path,
                    repository_service._normalize_repository_relative_path(
                        str(child_path.relative_to(repo_path))
                    )
                    or "",
                )
            ):
                continue
            normalized_child = repository_service._normalize_repository_relative_path(
                str(child_path.relative_to(repo_path))
            )
            if normalized_child:
                config_paths.add(normalized_child)
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _accumulate_detected_ecosystem_scores(
    scores: Counter[str],
    *,
    ecosystems: set[str],
    config_path: str,
    repo_path: Path | None = None,
    entrypoints: set[str],
    roots: set[str],
    configs: set[str],
    preferred_ecosystems: set[str] | None = None,
) -> None:
    canonical_ecosystems = {
        canonical_repository_language(ecosystem)
        for ecosystem in ecosystems
        if canonical_repository_language(ecosystem)
    }
    if not canonical_ecosystems or _is_non_operational_profile_path_for_ecosystems(
        config_path,
        ecosystems=canonical_ecosystems,
        repo_path=repo_path,
    ):
        return
    operational_entrypoints = [
        path
        for path in entrypoints
        if path
        and not repository_service._is_test_path(path)
        and not _is_non_operational_profile_path_for_ecosystems(
            path,
            ecosystems=canonical_ecosystems,
            repo_path=repo_path,
        )
        and _is_operational_profile_entrypoint_candidate(path, repo_path=repo_path)
    ]
    operational_roots = [
        root
        for root in roots
        if (
            normalized_root := repository_service._normalize_repository_relative_path(root)
        )
        and not _is_non_operational_profile_path_for_ecosystems(
            normalized_root,
            ecosystems=canonical_ecosystems,
            repo_path=repo_path,
        )
    ]
    signal_score = (
        _profile_signal_depth_score(config_path) * 4
        + min(len(operational_entrypoints), 8) * 5
        + min(len(operational_roots), 8) * 3
        + min(len(configs), 4)
    )
    if signal_score <= 0:
        return
    for ecosystem in canonical_ecosystems:
        scores[ecosystem] += signal_score
    if preferred_ecosystems:
        preferred_canonical = {
            canonical_repository_language(ecosystem)
            for ecosystem in preferred_ecosystems
            if canonical_repository_language(ecosystem) in canonical_ecosystems
        }
        for ecosystem in preferred_canonical:
            scores[ecosystem] += max(1, signal_score // 4)


def _normalized_package_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _ruby_package_names_for_profile(
    *,
    repo_path: Path,
    normalized_path: str,
) -> tuple[str, ...]:
    package_names: set[str] = set()
    basename = PurePosixPath(normalized_path).name
    if basename.lower().endswith(".gemspec"):
        package_names.add(PurePosixPath(basename).stem)
    repo_name = re.sub(r"[^a-z0-9_]+", "_", repo_path.name.lower()).strip("_")
    if repo_name:
        package_names.add(repo_name)
    try:
        text = (repo_path / normalized_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if text:
        for match in re.finditer(r"""\.name\s*=\s*["'](?P<name>[^"']+)["']""", text):
            raw_name = match.group("name").strip()
            if raw_name:
                package_names.add(raw_name)
    return tuple(sorted(name for name in package_names if name.strip()))


def _ruby_package_entrypoint_paths(
    *,
    repo_path: Path,
    project_dir: PurePosixPath,
    package_names: tuple[str, ...],
) -> set[str]:
    entrypoint_paths: set[str] = set()
    if not package_names:
        return entrypoint_paths
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    normalized_package_ids = {
        _normalized_package_identifier(package_name)
        for package_name in package_names
        if package_name.strip()
    }
    for package_name in package_names:
        if not package_name.strip():
            continue
        normalized_package_name = package_name.strip().replace("-", "_")
        entrypoint_paths.update(
            {
                f"{root_prefix}bin/{normalized_package_name}",
                f"{root_prefix}exe/{normalized_package_name}",
                f"{root_prefix}lib/{normalized_package_name}.rb",
            }
        )
    lib_dir = repo_path / project_dir / "lib"
    if lib_dir.is_dir():
        try:
            ruby_candidates = sorted(lib_dir.glob("*.rb"))
        except OSError:
            ruby_candidates = []
        for candidate in ruby_candidates:
            normalized_stem = _normalized_package_identifier(candidate.stem)
            if not normalized_stem or normalized_stem not in normalized_package_ids:
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if relative_path:
                entrypoint_paths.add(relative_path)
    return entrypoint_paths


def _rank_repo_profile_seed_path(
    path: str,
    *,
    repo_path: Path | None = None,
    support_roots: set[str],
) -> tuple[int, int, int, int, int, int, int, int, int, str, str]:
    normalized_path = repository_service._normalize_repository_relative_path(path)
    path_lower = normalized_path.lower()
    basename = PurePosixPath(normalized_path).name.lower()
    parts = PurePosixPath(normalized_path).parts
    part_set = {part.lower() for part in parts}
    language = _probe_language_for_path(normalized_path, repo_path=repo_path)
    ecosystem_priority, ecosystem_name = _best_repository_path_priority(
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


def _balanced_profile_paths(
    *,
    paths: list[str],
    detected_ecosystems: set[str],
    repo_path: Path | None = None,
    support_roots: set[str],
    limit: int,
    ecosystem_scores: Counter[str] | None = None,
) -> list[str]:
    if limit <= 0:
        return []
    ranked_paths = sorted(
        dict.fromkeys(path for path in paths if path),
        key=lambda candidate_path: _rank_repo_profile_seed_path(
            candidate_path,
            repo_path=repo_path,
            support_roots=support_roots,
        ),
    )
    ranked_paths = _diversify_paths_by_support_root(
        paths=ranked_paths,
        support_roots=support_roots,
    )
    if len(ranked_paths) <= limit or len(detected_ecosystems) <= 1:
        return ranked_paths[:limit]
    bucket_order = _ordered_operational_ecosystems(
        detected_ecosystems,
        ecosystem_scores=ecosystem_scores,
    )
    buckets: dict[str, list[str]] = {ecosystem: [] for ecosystem in bucket_order}
    overflow_paths: list[str] = []
    for candidate_path in ranked_paths:
        matched_ecosystems = [
            ecosystem
            for ecosystem in bucket_order
            if ecosystem
            in _candidate_ecosystems_for_path(candidate_path, repo_path=repo_path)
        ]
        if matched_ecosystems:
            buckets[matched_ecosystems[0]].append(candidate_path)
            continue
        overflow_paths.append(candidate_path)
    for ecosystem in bucket_order:
        buckets[ecosystem] = _diversify_paths_by_support_root(
            paths=buckets[ecosystem],
            support_roots=support_roots,
        )
    selected_paths: list[str] = []
    seen_paths: set[str] = set()
    while len(selected_paths) < limit:
        progress = False
        for ecosystem in bucket_order:
            bucket = buckets[ecosystem]
            while bucket:
                candidate_path = bucket.pop(0)
                if candidate_path in seen_paths:
                    continue
                seen_paths.add(candidate_path)
                selected_paths.append(candidate_path)
                progress = True
                if len(selected_paths) >= limit:
                    return selected_paths
                break
        if not progress:
            break
    for candidate_path in overflow_paths + ranked_paths:
        if candidate_path in seen_paths:
            continue
        seen_paths.add(candidate_path)
        selected_paths.append(candidate_path)
        if len(selected_paths) >= limit:
            break
    return selected_paths[:limit]


def _leaf_support_roots(support_roots: set[str]) -> set[str]:
    normalized_roots = {
        normalized_root
        for root in support_roots
        if (normalized_root := repository_service._normalize_repository_relative_path(root))
    }
    if not normalized_roots:
        return set()
    leaf_roots = set(normalized_roots)
    for root in normalized_roots:
        if any(
            other_root != root and other_root.startswith(f"{root}/")
            for other_root in normalized_roots
        ):
            leaf_roots.discard(root)
    return leaf_roots or normalized_roots


def _best_matching_support_root(path: str, *, support_roots: set[str]) -> str | None:
    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return None
    normalized_support_roots = _normalized_scannable_support_roots(support_roots)
    matched_roots = [
        normalized_root
        for normalized_root in normalized_support_roots
        if (
            normalized_path == normalized_root
            or normalized_path.startswith(f"{normalized_root}/")
        )
    ]
    if not matched_roots:
        return None
    return max(matched_roots, key=len)


def _diversify_paths_by_support_root(
    *,
    paths: list[str],
    support_roots: set[str],
) -> list[str]:
    if not paths or not support_roots:
        return list(paths)
    root_buckets: dict[str, list[str]] = {}
    bucket_order: list[str] = []
    overflow_paths: list[str] = []
    for candidate_path in paths:
        matched_root = _best_matching_support_root(
            candidate_path,
            support_roots=support_roots,
        )
        if matched_root is None:
            overflow_paths.append(candidate_path)
            continue
        if matched_root not in root_buckets:
            root_buckets[matched_root] = []
            bucket_order.append(matched_root)
        root_buckets[matched_root].append(candidate_path)
    ordered_paths: list[str] = []
    while True:
        progress = False
        for root in bucket_order:
            bucket = root_buckets[root]
            if not bucket:
                continue
            ordered_paths.append(bucket.pop(0))
            progress = True
        if not progress:
            break
    ordered_paths.extend(overflow_paths)
    return ordered_paths


def _path_within_support_roots(path: str, *, support_roots: set[str]) -> bool:
    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return False
    for root in support_roots:
        normalized_root = repository_service._normalize_repository_relative_path(root)
        if not normalized_root:
            continue
        if normalized_path == normalized_root or normalized_path.startswith(f"{normalized_root}/"):
            return True
    return False


def _support_roots_requiring_expansion(
    *,
    candidate_file_paths: list[str],
    support_roots: list[str] | set[str],
) -> list[str]:
    normalized_support_roots = _normalized_scannable_support_roots(support_roots)
    if not normalized_support_roots:
        return []
    match_order = sorted(
        normalized_support_roots,
        key=lambda path: (-len(path), path),
    )
    covered_roots: set[str] = set()
    for candidate_path in candidate_file_paths:
        normalized_candidate_path = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate_path:
            continue
        matched_root = next(
            (
                root
                for root in match_order
                if normalized_candidate_path == root
                or normalized_candidate_path.startswith(f"{root}/")
            ),
            None,
        )
        if matched_root is None:
            continue
        covered_roots.add(matched_root)
        if len(covered_roots) == len(normalized_support_roots):
            return []
    return sorted(root for root in normalized_support_roots if root not in covered_roots)


def _support_roots_need_expansion(
    *,
    candidate_file_paths: list[str],
    support_roots: list[str] | set[str],
) -> bool:
    return bool(
        _support_roots_requiring_expansion(
            candidate_file_paths=candidate_file_paths,
            support_roots=support_roots,
        )
    )


def _scala_support_root_from_candidate_path(path: str) -> str | None:
    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return None
    if repository_service._language_for_path(Path(normalized_path)) != "scala":
        return None
    if repository_service._is_test_path(normalized_path) or _is_non_operational_profile_path(
        normalized_path
    ):
        return None
    parts = list(PurePosixPath(normalized_path).parts)
    if "src" not in parts:
        return None
    src_index = parts.index("src")
    intermediate_parts = parts[src_index + 1 : -1]
    if not intermediate_parts:
        return "/".join(parts[: src_index + 1])
    first_part = intermediate_parts[0].lower()
    if first_part in {"main", "shared"} and len(intermediate_parts) >= 2:
        second_part = intermediate_parts[1].lower()
        if second_part == "java" or second_part.startswith("scala"):
            return "/".join(parts[: src_index + 3])
    if first_part == "java" or first_part.startswith("scala"):
        return "/".join(parts[: src_index + 2])
    if first_part in {"test", "tests", "it"}:
        return None
    return "/".join(parts[: src_index + 2])


def _scala_support_roots_from_candidates(candidate_file_paths: list[str]) -> set[str]:
    support_roots: set[str] = set()
    for candidate_path in candidate_file_paths:
        derived_root = _scala_support_root_from_candidate_path(candidate_path)
        if derived_root:
            support_roots.add(derived_root)
    return support_roots


def _profile_entrypoint_target_count(detected_ecosystems: set[str]) -> int:
    if detected_ecosystems & {
        "abap",
        "assembly",
        "clojure",
        "crystal",
        "cobol",
        "d",
        "php",
        "plsql",
        "foxpro",
        "prolog",
        "sas",
        "elixir",
        "fortran",
        "ruby",
        "swift",
        "dart",
        "dotnet",
        "erlang",
        "lisp",
        "gdscript",
        "gml",
        "java",
        "lua",
        "luau",
        "ocaml",
        "scala",
        "haskell",
        "fsharp",
        "groovy",
        "matlab",
        "ml",
        "objectivec",
        "perl",
        "powershell",
        "r",
        "rpg",
        "actionscript",
        "autohotkey",
        "autoit",
        "awk",
        "cfml",
        "elm",
        "haxe",
        "vimscript",
        "scratch",
        "julia",
        "agda",
        "apex",
        "wolfram",
        "vb6",
        "vbscript",
        "solidity",
        "systemverilog",
        "vhdl",
        "xpp",
        "tcl",
        "ladder",
        "labview",
    }:
        return 8
    if detected_ecosystems & {"c", "cpp"}:
        return 8
    if detected_ecosystems & {"ada", "node", "typescript", "python", "rust", "go", "zig", "nim"}:
        return 6
    return 4


def _prefer_non_text_control_profile_candidates(
    *,
    paths: list[str],
    repo_path: Path | None = None,
) -> list[str]:
    ordered_paths = list(dict.fromkeys(path for path in paths if path))
    if not ordered_paths:
        return []
    text_control_ecosystems = {"batchfile", "makefile"}
    non_text_control_paths = [
        path
        for path in ordered_paths
        if not (
            _candidate_ecosystems_for_path(path, repo_path=repo_path)
            & text_control_ecosystems
        )
    ]
    return non_text_control_paths or ordered_paths


def _expand_profile_entrypoints(
    *,
    ranked_candidates: list[str],
    repo_path: Path,
    support_roots: list[str],
    existing_entrypoints: list[str],
    detected_ecosystems: set[str],
    ecosystem_scores: Counter[str] | None = None,
) -> list[str]:
    target_count = _profile_entrypoint_target_count(detected_ecosystems)
    normalized_support_roots = _normalized_scannable_support_roots(support_roots)
    sanitized_existing_entrypoints = [
        normalized_path
        for candidate_path in existing_entrypoints
        if (
            normalized_path := repository_service._normalize_repository_relative_path(
                candidate_path
            )
        )
        and _is_operational_profile_entrypoint_candidate(
            normalized_path,
            repo_path=repo_path,
        )
    ]
    sanitized_existing_entrypoints = _prefer_non_text_control_profile_candidates(
        paths=sanitized_existing_entrypoints,
        repo_path=repo_path,
    )
    qualifying_candidates: list[str] = []
    for candidate_path in ranked_candidates:
        normalized_candidate_path = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate_path:
            continue
        if not _is_operational_profile_entrypoint_candidate(
            normalized_candidate_path,
            repo_path=repo_path,
        ):
            continue
        if normalized_support_roots and not _path_within_support_roots(
            normalized_candidate_path,
            support_roots=normalized_support_roots,
        ):
            continue
        qualifying_candidates.append(normalized_candidate_path)
    qualifying_candidates = _prefer_non_text_control_profile_candidates(
        paths=qualifying_candidates,
        repo_path=repo_path,
    )
    balance_ecosystems = (
        {
            ecosystem
            for candidate_path in sanitized_existing_entrypoints
            for ecosystem in _candidate_ecosystems_for_path(
                candidate_path,
                repo_path=repo_path,
            )
        }
        or detected_ecosystems
    )
    selected_entrypoints = _balanced_profile_paths(
        paths=sanitized_existing_entrypoints,
        detected_ecosystems=balance_ecosystems,
        repo_path=repo_path,
        support_roots=normalized_support_roots,
        limit=target_count,
        ecosystem_scores=ecosystem_scores,
    )
    if len(selected_entrypoints) >= target_count:
        return selected_entrypoints
    selected_path_set = set(selected_entrypoints)
    filled_candidates = _balanced_profile_paths(
        paths=[
            candidate_path
            for candidate_path in qualifying_candidates
            if candidate_path not in selected_path_set
        ],
        detected_ecosystems=detected_ecosystems,
        repo_path=repo_path,
        support_roots=normalized_support_roots,
        limit=target_count - len(selected_entrypoints),
        ecosystem_scores=ecosystem_scores,
    )
    return selected_entrypoints + filled_candidates


def _derive_operational_seed_plan_without_diagnostics(
    *,
    repo_path: Path,
    focus_paths: list[str],
    max_files: int,
) -> dict[str, Any]:
    discovered_config_paths = _repo_profile_config_paths(
        repo_path=repo_path,
        focus_paths=focus_paths,
    )

    entrypoint_candidates: set[str] = set()
    support_root_candidates: set[str] = set()
    config_path_candidates: set[str] = set()
    detected_ecosystems: set[str] = set()
    detected_ecosystem_scores: Counter[str] = Counter()
    entrypoint_candidate_ecosystems: dict[str, set[str]] = {}
    support_root_candidate_ecosystems: dict[str, set[str]] = {}

    for candidate_path in sorted(discovered_config_paths):
        basename = PurePosixPath(candidate_path).name.lower()
        manifest_ecosystems: set[str]
        preferred_manifest_ecosystems: set[str] = set()
        if _is_xpp_descriptor_config_path(repo_path, candidate_path):
            manifest_ecosystems = {"xpp"}
            entrypoints, roots, configs = _xpp_profile_hints(repo_path, candidate_path)
        elif basename == "box.json" and _is_cfml_box_config_path(repo_path, candidate_path):
            manifest_ecosystems = {"cfml"}
            entrypoints, roots, configs = _cfml_profile_hints(repo_path, candidate_path)
        elif basename == "package.json":
            manifest_ecosystems = {"node"}
            entrypoints, roots, configs = _package_json_profile_hints(repo_path, candidate_path)
        elif basename in {"tsconfig.json", "jsconfig.json"} or (
            basename.startswith("tsconfig.") and basename.endswith(".json")
        ):
            manifest_ecosystems = {"typescript"}
            entrypoints, roots, configs = _tsconfig_profile_hints(repo_path, candidate_path)
        elif basename in {
            "build",
            "build.bazel",
            "module.bazel",
            "workspace",
            "workspace.bazel",
        }:
            manifest_ecosystems = {"starlark"}
            entrypoints, roots, configs = _starlark_profile_hints(repo_path, candidate_path)
        elif basename == "pyproject.toml":
            manifest_ecosystems = {"python"}
            entrypoints, roots, configs = _pyproject_profile_hints(repo_path, candidate_path)
        elif basename in {"project.clj", "deps.edn", "bb.edn", "shadow-cljs.edn"}:
            manifest_ecosystems = {"clojure"}
            entrypoints, roots, configs = _clojure_profile_hints(repo_path, candidate_path)
        elif basename == "pubspec.yaml":
            manifest_ecosystems = {"dart"}
            entrypoints, roots, configs = _pubspec_profile_hints(repo_path, candidate_path)
        elif basename == "alire.toml" or basename.endswith(".gpr"):
            manifest_ecosystems = {"ada"}
            entrypoints, roots, configs = _ada_profile_hints(repo_path, candidate_path)
        elif basename in {"dbt_project.yml", "dbt_project.yaml"}:
            manifest_ecosystems = {"sql"}
            entrypoints, roots, configs = _dbt_project_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename.endswith((".sqlproj", ".dbproj")):
            manifest_ecosystems = {"tsql"}
            entrypoints, roots, configs = _tsql_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "package.yaml":
            manifest_ecosystems = {"haskell"}
            entrypoints, roots, configs = _haskell_package_yaml_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "fpm.toml":
            manifest_ecosystems = {"fortran"}
            entrypoints, roots, configs = _fortran_fpm_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename.endswith(".dproj") and _is_delphi_project_config_path(
            repo_path,
            candidate_path,
        ):
            manifest_ecosystems = {"delphi"}
            entrypoints, roots, configs = _delphi_profile_hints(repo_path, candidate_path)
        elif basename.endswith((".ecf", ".ace")) and _is_eiffel_project_config_path(
            repo_path,
            candidate_path,
        ):
            manifest_ecosystems = {"eiffel"}
            entrypoints, roots, configs = _eiffel_profile_hints(repo_path, candidate_path)
        elif basename.endswith((".lpi", ".lpk")):
            manifest_ecosystems = {"pascal"}
            entrypoints, roots, configs = _pascal_project_profile_hints(candidate_path)
        elif basename in {"dub.json", "dub.sdl"}:
            manifest_ecosystems = {"d"}
            entrypoints, roots, configs = _dub_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "cargo.toml":
            manifest_ecosystems = {"rust"}
            entrypoints, roots, configs = _cargo_profile_hints(repo_path, candidate_path)
        elif basename == "go.mod":
            manifest_ecosystems = {"go"}
            entrypoints, roots, configs = _go_module_profile_hints(candidate_path)
        elif basename.endswith(".cabal"):
            manifest_ecosystems = {"haskell"}
            entrypoints, roots, configs = _haskell_cabal_profile_hints(repo_path, candidate_path)
        elif basename in {"stack.yaml", "cabal.project"}:
            manifest_ecosystems = {"haskell"}
            entrypoints, roots, configs = _haskell_project_profile_hints(candidate_path)
        elif basename == "pom.xml":
            manifest_ecosystems = {"java"}
            entrypoints, roots, configs = _pom_profile_hints(candidate_path)
        elif basename in {"build.gradle", "settings.gradle"}:
            manifest_ecosystems = {"groovy", "java"}
            entrypoints, roots, configs = _gradle_profile_hints(repo_path, candidate_path)
        elif basename in {"build.gradle.kts", "settings.gradle.kts"}:
            manifest_ecosystems = {"java", "kotlin"}
            entrypoints, roots, configs = _gradle_profile_hints(repo_path, candidate_path)
        elif basename in {"build.sbt", "build.sc", "build.mill"}:
            manifest_ecosystems = {"scala"}
            entrypoints, roots, configs = _scala_build_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename in {"dune", "dune-project"} or basename.endswith(".opam"):
            manifest_ecosystems = {"ocaml"}
            entrypoints, roots, configs = _ocaml_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename.endswith(".mlb") or basename.endswith(".cm"):
            entrypoints, roots, configs = _ml_profile_hints(repo_path, candidate_path)
            if not configs:
                continue
            manifest_ecosystems = {"ml"}
        elif basename == "cmakelists.txt":
            manifest_ecosystems = {
                "cmake",
                *_c_family_manifest_ecosystems(
                    repo_path=repo_path,
                    manifest_path=candidate_path,
                ),
            }
            entrypoints, roots, configs = _cmake_profile_hints(repo_path, candidate_path)
        elif _is_qmake_project_config_path(repo_path, candidate_path):
            manifest_ecosystems = {
                "qmake",
                *_c_family_manifest_ecosystems(
                    repo_path=repo_path,
                    manifest_path=candidate_path,
                ),
            }
            preferred_manifest_ecosystems = {"qmake"}
            entrypoints, roots, configs = _qmake_profile_hints(repo_path, candidate_path)
        elif basename == "composer.json":
            manifest_ecosystems = {"php"}
            entrypoints, roots, configs = _composer_profile_hints(repo_path, candidate_path)
        elif basename in {"cpanfile", "dist.ini", "makefile.pl", "build.pl"}:
            manifest_ecosystems = {"perl"}
            entrypoints, roots, configs = _perl_profile_hints(repo_path, candidate_path)
        elif basename in {"description", "namespace"}:
            manifest_ecosystems = {"r"}
            entrypoints, roots, configs = _r_profile_hints(repo_path, candidate_path)
        elif basename in {"project.toml", "manifest.toml"}:
            manifest_ecosystems = {"julia"}
            entrypoints, roots, configs = _julia_profile_hints(repo_path, candidate_path)
        elif basename == "shard.yml":
            manifest_ecosystems = {"crystal"}
            entrypoints, roots, configs = _shard_profile_hints(repo_path, candidate_path)
        elif basename == "mix.exs":
            manifest_ecosystems = {"elixir"}
            entrypoints, roots, configs = _mix_profile_hints(repo_path, candidate_path)
        elif basename in {"rebar.config", "erlang.mk"} or basename.endswith(".app.src"):
            manifest_ecosystems = {"erlang"}
            entrypoints, roots, configs = _erlang_project_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "elm.json":
            manifest_ecosystems = {"elm"}
            entrypoints, roots, configs = _elm_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename in {"spago.yaml", "spago.dhall"} or (
            basename == "bower.json"
            and _is_purescript_bower_config_path(repo_path, candidate_path)
        ):
            manifest_ecosystems = {"purescript"}
            entrypoints, roots, configs = _purescript_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename in {"rescript.json", "bsconfig.json"}:
            manifest_ecosystems = {"rescript"}
            entrypoints, roots, configs = _rescript_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename in repository_service.moonbit_adapter.MOONBIT_CONFIG_BASENAMES:
            manifest_ecosystems = {"moonbit"}
            moonbit_candidate_paths = _seeded_repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
                entrypoint_candidates=entrypoint_candidates,
                support_root_candidates=support_root_candidates,
                config_paths=discovered_config_paths,
                detected_ecosystems=detected_ecosystems,
                detected_ecosystem_scores=detected_ecosystem_scores,
            ) or _repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
            )
            entrypoints, roots, configs = _moonbit_profile_hints_from_candidates(
                repo_path,
                moonbit_candidate_paths,
                manifest_path=candidate_path,
            )
        elif basename == "gleam.toml":
            manifest_ecosystems = {"gleam"}
            entrypoints, roots, configs = _gleam_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "project.janet":
            manifest_ecosystems = {"janet"}
            entrypoints, roots, configs = _janet_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "nextflow.config":
            manifest_ecosystems = {"nextflow"}
            nextflow_candidate_paths = _seeded_repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
                entrypoint_candidates=entrypoint_candidates,
                support_root_candidates=support_root_candidates,
                config_paths=discovered_config_paths,
                detected_ecosystems=detected_ecosystems,
                detected_ecosystem_scores=detected_ecosystem_scores,
            ) or _repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
            )
            entrypoints, roots, configs = _nextflow_profile_hints_from_candidates(
                repo_path,
                nextflow_candidate_paths,
                manifest_path=candidate_path,
            )
        elif basename == "mason.toml":
            manifest_ecosystems = {"chapel"}
            entrypoints, roots, configs = _chapel_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename in repository_service.bitbake_adapter.BITBAKE_CONFIG_BASENAMES:
            manifest_ecosystems = {"bitbake"}
            bitbake_candidate_paths = _bitbake_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                config_paths=[candidate_path, *discovered_config_paths],
                max_files=max_files,
            ) or _seeded_repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
                entrypoint_candidates=entrypoint_candidates,
                support_root_candidates=support_root_candidates,
                config_paths=discovered_config_paths,
                detected_ecosystems=detected_ecosystems,
                detected_ecosystem_scores=detected_ecosystem_scores,
            ) or _repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
            )
            entrypoints, roots, configs = _bitbake_profile_hints_from_candidates(
                repo_path,
                bitbake_candidate_paths,
            )
            configs = set(configs)
            configs.add(candidate_path)
        elif basename == "bicepconfig.json":
            manifest_ecosystems = {"bicep"}
            bicep_candidate_paths = _seeded_repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
                entrypoint_candidates=entrypoint_candidates,
                support_root_candidates=support_root_candidates,
                config_paths=discovered_config_paths,
                detected_ecosystems=detected_ecosystems,
                detected_ecosystem_scores=detected_ecosystem_scores,
            ) or _repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
            )
            entrypoints, roots, configs = _bicep_profile_hints_from_candidates(
                repo_path,
                bicep_candidate_paths,
            )
            configs = set(configs)
            configs.add(candidate_path)
        elif basename == "module.cue" and _is_cue_module_config_path(repo_path, candidate_path):
            manifest_ecosystems = {"cue"}
            cue_candidate_paths = _seeded_repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
                entrypoint_candidates=entrypoint_candidates,
                support_root_candidates=support_root_candidates,
                config_paths=discovered_config_paths,
                detected_ecosystems=detected_ecosystems,
                detected_ecosystem_scores=detected_ecosystem_scores,
            ) or _repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
            )
            entrypoints, roots, configs = _cue_profile_hints_from_candidates(
                repo_path,
                cue_candidate_paths,
                manifest_path=candidate_path,
            )
        elif basename == "ols.json" and _is_odin_ols_config_path(repo_path, candidate_path):
            manifest_ecosystems = {"odin"}
            entrypoints, roots, configs = _odin_profile_hints(repo_path, candidate_path)
        elif basename in {".hhconfig", "hhvm.autoload", "hh_autoload.json"}:
            manifest_ecosystems = {"hack"}
            hack_candidate_paths = _seeded_repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
                entrypoint_candidates=entrypoint_candidates,
                support_root_candidates=support_root_candidates,
                config_paths=discovered_config_paths,
                detected_ecosystems=detected_ecosystems,
                detected_ecosystem_scores=detected_ecosystem_scores,
            ) or _repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
            )
            entrypoints, roots, configs = _hack_profile_hints_from_candidates(
                repo_path,
                hack_candidate_paths,
                manifest_path=candidate_path,
            )
        elif basename == "package.dhall":
            manifest_ecosystems = {"dhall"}
            dhall_candidate_paths = _seeded_repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
                entrypoint_candidates=entrypoint_candidates,
                support_root_candidates=support_root_candidates,
                config_paths=discovered_config_paths,
                detected_ecosystems=detected_ecosystems,
                detected_ecosystem_scores=detected_ecosystem_scores,
            ) or _repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
            )
            entrypoints, roots, configs = _dhall_profile_hints_from_candidates(
                repo_path,
                dhall_candidate_paths,
                manifest_path=candidate_path,
            )
        elif basename in {"puppetfile", "modulefile"} or (
            basename == "metadata.json"
            and _is_puppet_metadata_config_path(repo_path, candidate_path)
        ):
            manifest_ecosystems = {"puppet"}
            entrypoints, roots, configs = _puppet_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename in {"lean-toolchain", "lakefile.lean", "lakefile.toml"}:
            manifest_ecosystems = {"lean"}
            entrypoints, roots, configs = _lean_profile_hints(repo_path, candidate_path)
        elif basename in {"_coqproject", "_rocqproject"}:
            manifest_ecosystems = {"coq"}
            entrypoints, roots, configs = _coq_profile_hints(repo_path, candidate_path)
        elif basename.endswith(".agda-lib"):
            manifest_ecosystems = {"agda"}
            entrypoints, roots, configs = _agda_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename.endswith(".ipkg"):
            manifest_ecosystems = {"idris"}
            entrypoints, roots, configs = _idris_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "meta6.json":
            manifest_ecosystems = {"raku"}
            entrypoints, roots, configs = _raku_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "cask":
            manifest_ecosystems = {"emacslisp"}
            entrypoints, roots, configs = _emacslisp_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename in {
            ".smalltalk.ston",
            ".smalltalk.all.ston",
            ".smalltalk.release.ston",
        }:
            manifest_ecosystems = {"smalltalk"}
            entrypoints, roots, configs = _smalltalk_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "cakefile":
            manifest_ecosystems = {"coffeescript"}
            entrypoints, roots, configs = _coffeescript_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "project.xml" or basename.endswith(".hxml"):
            manifest_ecosystems = {"haxe"}
            entrypoints, roots, configs = _haxe_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename.endswith(".mqproj"):
            manifest_ecosystems = {"mql5"}
            entrypoints, roots, configs = _mql5_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename.endswith(".gms"):
            manifest_ecosystems = {"gams"}
            entrypoints, roots, configs = _gams_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename.endswith(".scad"):
            manifest_ecosystems = {"openscad"}
            entrypoints, roots, configs = _openscad_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename in {"flake.nix", "default.nix", "shell.nix"}:
            manifest_ecosystems = {"nix"}
            entrypoints, roots, configs = _nix_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "v.mod":
            manifest_ecosystems = {"v"}
            entrypoints, roots, configs = _v_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename.endswith(".nimble") or basename in {"config.nims", "nim.cfg"}:
            manifest_ecosystems = {"nim"}
            entrypoints, roots, configs = _nim_project_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "meson.build":
            manifest_ecosystems = {"meson", *_c_family_manifest_ecosystems(
                repo_path=repo_path,
                manifest_path=candidate_path,
            )}
            entrypoints, roots, configs = _meson_profile_hints(repo_path, candidate_path)
        elif basename == "build.zig":
            manifest_ecosystems = {"zig"}
            entrypoints, roots, configs = _zig_build_profile_hints(repo_path, candidate_path)
        elif basename == "package.swift":
            manifest_ecosystems = {"swift"}
            entrypoints, roots, configs = _swift_package_profile_hints(repo_path, candidate_path)
        elif basename.endswith(".podspec"):
            manifest_ecosystems = {"objectivec"}
            entrypoints, roots, configs = _podspec_profile_hints(repo_path, candidate_path)
        elif basename in {
            "brownie-config.yaml",
            "brownie-config.yml",
            "foundry.toml",
            "hardhat.config.cjs",
            "hardhat.config.js",
            "hardhat.config.mjs",
            "hardhat.config.ts",
            "remappings.txt",
            "truffle-config.js",
            "truffle.js",
        }:
            manifest_ecosystems = {"solidity"}
            entrypoints, roots, configs = _solidity_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename in {"bender.yml", "bender.yaml"} or basename.endswith(".core"):
            manifest_ecosystems = {"systemverilog"}
            entrypoints, roots, configs = _systemverilog_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "vhdl_ls.toml":
            manifest_ecosystems = {"vhdl"}
            entrypoints, roots, configs = _vhdl_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "project.godot":
            manifest_ecosystems = {"gdscript"}
            entrypoints, roots, configs = _gdscript_project_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename.endswith(".yyp"):
            manifest_ecosystems = {"gml"}
            entrypoints, roots, configs = _gml_profile_hints(repo_path, candidate_path)
        elif basename.endswith(".psd1"):
            manifest_ecosystems = {"powershell"}
            entrypoints, roots, configs = _powershell_profile_hints(repo_path, candidate_path)
        elif basename == "gemfile" or basename.endswith(".gemspec"):
            manifest_ecosystems = {"ruby"}
            entrypoints, roots, configs = _gemfile_profile_hints(repo_path, candidate_path)
        elif basename in {"default.project.json", "wally.toml"}:
            manifest_ecosystems = {"luau"}
            entrypoints, roots, configs = _luau_profile_hints(repo_path, candidate_path)
        elif basename in repository_service.typst_adapter.TYPST_CONFIG_BASENAMES:
            manifest_ecosystems = {"typst"}
            entrypoints = set()
            roots = {
                repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(candidate_path).parent)
                )
            }
            configs = {candidate_path}
        elif basename in repository_service.tex_adapter.TEX_CONFIG_BASENAMES:
            manifest_ecosystems = {"tex"}
            entrypoints = set()
            roots = {
                repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(candidate_path).parent)
                )
            }
            configs = {candidate_path}
        elif basename in repository_service.protobuf_adapter.PROTOBUF_CONFIG_BASENAMES:
            manifest_ecosystems = {"protobuf"}
            entrypoints, roots, configs = _protobuf_profile_hints_from_candidates(
                repo_path,
                [candidate_path],
            )
        elif basename in repository_service.dockerfile_adapter.DOCKERFILE_BASENAMES:
            manifest_ecosystems = {"dockerfile"}
            entrypoints, roots, configs = _dockerfile_profile_hints_from_candidates(
                repo_path,
                [candidate_path],
            )
        elif basename.endswith(".rockspec"):
            manifest_ecosystems = {"lua"}
            entrypoints, roots, configs = _rockspec_profile_hints(repo_path, candidate_path)
        elif basename.endswith(".fsproj"):
            manifest_ecosystems = {"dotnet", "fsharp"}
            preferred_manifest_ecosystems = {"fsharp"}
            entrypoints, roots, configs = _csproj_profile_hints(candidate_path)
        elif basename.endswith(".vbproj"):
            manifest_ecosystems = {"dotnet", "visualbasic"}
            preferred_manifest_ecosystems = {"visualbasic"}
            entrypoints, roots, configs = _csproj_profile_hints(candidate_path)
        elif basename == "sfdx-project.json":
            manifest_ecosystems = {"apex"}
            entrypoints, roots, configs = _apex_profile_hints(repo_path, candidate_path)
        elif basename.endswith((".lvproj", ".lvlib", ".lvclass")):
            manifest_ecosystems = {"labview"}
            entrypoints, roots, configs = _labview_profile_hints(repo_path, candidate_path)
        elif basename in {"pacletinfo.m", "pacletinfo.wl"}:
            manifest_ecosystems = {"wolfram"}
            entrypoints, roots, configs = _wolfram_profile_hints(repo_path, candidate_path)
        elif basename in {"iproj.json", ".ibmi.json"}:
            manifest_ecosystems = {"rpg"}
            entrypoints, roots, configs = _rpg_profile_hints(repo_path, candidate_path)
        elif basename.endswith(".vbp"):
            manifest_ecosystems = {"vb6"}
            entrypoints, roots, configs = _classic_visual_basic_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "asconfig.json":
            manifest_ecosystems = {"actionscript"}
            entrypoints, roots, configs = _actionscript_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename.endswith(".wsf"):
            manifest_ecosystems = {"vbscript"}
            entrypoints, roots, configs = _vbscript_profile_hints(repo_path, candidate_path)
        elif basename.endswith(".asd"):
            manifest_ecosystems = {"lisp"}
            entrypoints, roots, configs = _lisp_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "info.rkt":
            manifest_ecosystems = {"racket"}
            entrypoints, roots, configs = _racket_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "package.scm":
            manifest_ecosystems = {"scheme"}
            entrypoints, roots, configs = _scheme_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "pkgindex.tcl":
            manifest_ecosystems = {"tcl"}
            entrypoints, roots, configs = _tcl_profile_hints(repo_path, candidate_path)
        elif basename.endswith(".sln"):
            manifest_ecosystems = {"dotnet"}
            project_paths = _sln_project_paths(repo_path, candidate_path)
            if any(project_path.lower().endswith(".fsproj") for project_path in project_paths):
                manifest_ecosystems.add("fsharp")
                preferred_manifest_ecosystems.add("fsharp")
            if any(project_path.lower().endswith(".vbproj") for project_path in project_paths):
                manifest_ecosystems.add("visualbasic")
                preferred_manifest_ecosystems.add("visualbasic")
            entrypoints, roots, configs = _sln_profile_hints(repo_path, candidate_path)
        elif basename.endswith(".csproj"):
            manifest_ecosystems = {"dotnet"}
            entrypoints, roots, configs = _csproj_profile_hints(candidate_path)
        else:
            continue
        detected_ecosystems.update(manifest_ecosystems)
        if _is_non_operational_profile_path(candidate_path):
            entrypoints = set()
            roots = set()
        # ReScript manifests are common in JS/TS host repos, so let them seed
        # candidate collection without automatically winning operational rank.
        if manifest_ecosystems not in ({"rescript"}, {"moonbit"}):
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems=manifest_ecosystems,
                config_path=candidate_path,
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
                preferred_ecosystems=preferred_manifest_ecosystems,
            )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems=manifest_ecosystems,
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems=manifest_ecosystems,
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)

    bitbake_candidate_file_paths = []
    if "bitbake" in detected_ecosystems:
        bitbake_candidate_file_paths = _bitbake_profile_candidate_paths(
            repo_path=repo_path,
            focus_paths=focus_paths,
            config_paths=sorted(config_path_candidates or set(discovered_config_paths)),
            max_files=max_files,
        )

    candidate_file_paths = bitbake_candidate_file_paths or _seeded_repo_profile_candidate_paths(
        repo_path=repo_path,
        focus_paths=focus_paths,
        max_files=max_files,
        entrypoint_candidates=entrypoint_candidates,
        support_root_candidates=support_root_candidates,
        config_paths=discovered_config_paths,
        detected_ecosystems=detected_ecosystems,
        detected_ecosystem_scores=detected_ecosystem_scores,
    )
    if not candidate_file_paths:
        candidate_file_paths = _repo_profile_candidate_paths(
            repo_path=repo_path,
            focus_paths=focus_paths,
            max_files=max_files,
        )
    if not candidate_file_paths:
        return {
            "candidate_file_paths": [],
            "entrypoint_files": list(focus_paths),
            "support_roots": list(focus_paths),
            "config_paths": discovered_config_paths,
            "detected_ecosystems": _ordered_detected_ecosystems(
                detected_ecosystems,
            ),
            "operational_ecosystems": _ordered_operational_ecosystems(
                detected_ecosystems,
                ecosystem_scores=detected_ecosystem_scores,
            ),
        }

    if not detected_ecosystems:
        fallback_counts: Counter[str] = Counter()
        for candidate_path in candidate_file_paths:
            if repository_service._is_test_path(candidate_path):
                continue
            if _is_non_operational_profile_path(candidate_path):
                continue
            if not _is_repo_profile_code_candidate(candidate_path, repo_path=repo_path):
                continue
            fallback_counts.update(
                _candidate_ecosystems_for_path(candidate_path, repo_path=repo_path)
            )
        if fallback_counts:
            top_count = max(fallback_counts.values())
            detected_ecosystems.update(
                ecosystem
                for ecosystem, count in fallback_counts.items()
                if count == top_count and ecosystem not in {"unknown", "txt"}
            )

    if "vimscript" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _vimscript_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"vimscript"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"vimscript"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"vimscript"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "autohotkey" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _autohotkey_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"autohotkey"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"autohotkey"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"autohotkey"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "autoit" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _autoit_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"autoit"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"autoit"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"autoit"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "squirrel" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _squirrel_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"squirrel"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"squirrel"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"squirrel"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "nushell" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _nushell_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"nushell"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"nushell"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"nushell"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "fish" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _fish_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"fish"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"fish"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"fish"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "batchfile" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _batchfile_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"batchfile"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"batchfile"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"batchfile"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "makefile" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _makefile_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"makefile"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"makefile"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"makefile"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "just" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _just_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"just"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"just"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"just"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    dockerfile_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"dockerfile", "shell", "python", "node", "go", "ruby"},
    )
    if dockerfile_ecosystem_counts["dockerfile"] > 0:
        entrypoints, roots, configs = _dockerfile_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("dockerfile")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"dockerfile"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"dockerfile"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"dockerfile"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            dockerfile_count = dockerfile_ecosystem_counts["dockerfile"]
            host_count = sum(
                dockerfile_ecosystem_counts[ecosystem]
                for ecosystem in ("shell", "python", "node", "go", "ruby")
            )
            if dockerfile_count >= max(6, host_count):
                detected_ecosystem_scores["dockerfile"] += min(180, 60 + dockerfile_count * 8)
            elif dockerfile_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("shell", "python", "node", "go", "ruby"),
                    key=lambda ecosystem: dockerfile_ecosystem_counts[ecosystem],
                )
                if dockerfile_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        160,
                        32 + dockerfile_ecosystem_counts[dominant_host] * 8,
                    )
                    detected_ecosystem_scores["dockerfile"] = max(
                        0,
                        detected_ecosystem_scores["dockerfile"] - 24,
                    )

    scss_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"scss", "ruby", "javascript", "typescript", "css"},
    )
    if scss_ecosystem_counts["scss"] > 0:
        entrypoints, roots, configs = _scss_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("scss")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"scss"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"scss"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"scss"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            scss_count = scss_ecosystem_counts["scss"]
            host_count = sum(
                scss_ecosystem_counts[ecosystem]
                for ecosystem in ("ruby", "javascript", "typescript", "css")
            )
            if scss_count >= max(2, host_count):
                detected_ecosystem_scores["scss"] += min(120, 30 + scss_count * 14)

    less_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"less", "javascript", "typescript", "css", "vue"},
    )
    if less_ecosystem_counts["less"] > 0:
        entrypoints, roots, configs = _less_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("less")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"less"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"less"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"less"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            less_count = less_ecosystem_counts["less"]
            host_count = sum(
                less_ecosystem_counts[ecosystem]
                for ecosystem in ("javascript", "typescript", "css", "vue")
            )
            if less_count >= max(2, host_count):
                detected_ecosystem_scores["less"] += min(120, 30 + less_count * 14)

    stylus_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"stylus", "javascript", "typescript", "css", "vue", "node"},
    )
    if stylus_ecosystem_counts["stylus"] > 0:
        entrypoints, roots, configs = _stylus_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("stylus")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"stylus"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"stylus"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"stylus"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            stylus_count = stylus_ecosystem_counts["stylus"]
            host_count = sum(
                stylus_ecosystem_counts[ecosystem]
                for ecosystem in ("javascript", "typescript", "css", "vue", "node")
            )
            if stylus_count >= max(2, host_count):
                detected_ecosystem_scores["stylus"] += min(120, 30 + stylus_count * 14)

    jinja_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"jinja", "python", "shell", "yaml", "html", "css", "javascript", "typescript"},
    )
    if jinja_ecosystem_counts["jinja"] > 0:
        entrypoints, roots, configs = _jinja_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("jinja")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"jinja"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"jinja"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"jinja"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            jinja_count = jinja_ecosystem_counts["jinja"]
            host_count = sum(
                jinja_ecosystem_counts[ecosystem]
                for ecosystem in ("python", "shell", "yaml", "html", "css", "javascript", "typescript")
            )
            if jinja_count >= max(2, host_count):
                detected_ecosystem_scores["jinja"] += min(120, 30 + jinja_count * 14)

    liquid_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"liquid", "ruby", "markdown", "html", "css", "scss", "javascript", "typescript"},
    )
    if liquid_ecosystem_counts["liquid"] > 0:
        entrypoints, roots, configs = _liquid_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("liquid")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"liquid"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"liquid"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"liquid"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            liquid_count = liquid_ecosystem_counts["liquid"]
            host_count = sum(
                liquid_ecosystem_counts[ecosystem]
                for ecosystem in ("ruby", "markdown", "html", "css", "scss", "javascript", "typescript")
            )
            if liquid_count >= max(2, host_count):
                detected_ecosystem_scores["liquid"] += min(120, 30 + liquid_count * 14)

    handlebars_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"handlebars", "javascript", "typescript", "html", "css", "scss", "ruby"},
    )
    if handlebars_ecosystem_counts["handlebars"] > 0:
        entrypoints, roots, configs = _handlebars_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("handlebars")
            handlebars_count = handlebars_ecosystem_counts["handlebars"]
            host_count = sum(
                handlebars_ecosystem_counts[ecosystem]
                for ecosystem in ("javascript", "typescript", "html", "css", "scss", "ruby")
            )
            should_operationalize_handlebars = (
                handlebars_count >= 3
                or host_count == 0
                or handlebars_count >= host_count
            )
            if should_operationalize_handlebars:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"handlebars"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"handlebars"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"handlebars"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if handlebars_count >= max(2, host_count):
                    detected_ecosystem_scores["handlebars"] += min(120, 30 + handlebars_count * 14)

    mustache_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"mustache", "javascript", "typescript", "html", "css", "scss", "ruby", "php"},
    )
    if mustache_ecosystem_counts["mustache"] > 0:
        entrypoints, roots, configs = _mustache_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("mustache")
            mustache_count = mustache_ecosystem_counts["mustache"]
            host_count = sum(
                mustache_ecosystem_counts[ecosystem]
                for ecosystem in ("javascript", "typescript", "html", "css", "scss", "ruby", "php")
            )
            should_operationalize_mustache = (
                mustache_count >= 2
                and (
                    host_count == 0
                    or mustache_count >= host_count
                    or (mustache_count >= 4 and mustache_count * 2 >= host_count)
                )
            )
            if should_operationalize_mustache:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"mustache"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"mustache"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"mustache"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if mustache_count >= max(2, host_count):
                    detected_ecosystem_scores["mustache"] += min(140, 32 + mustache_count * 14)

    nunjucks_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"nunjucks", "javascript", "typescript", "node", "html", "css", "scss"},
    )
    if nunjucks_ecosystem_counts["nunjucks"] > 0:
        entrypoints, roots, configs = _nunjucks_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("nunjucks")
            nunjucks_count = nunjucks_ecosystem_counts["nunjucks"]
            host_count = sum(
                nunjucks_ecosystem_counts[ecosystem]
                for ecosystem in ("javascript", "typescript", "node", "html", "css", "scss")
            )
            should_operationalize_nunjucks = (
                nunjucks_count >= 2
                and (
                    host_count == 0
                    or nunjucks_count >= host_count
                    or (nunjucks_count >= 4 and nunjucks_count * 2 >= host_count)
                )
            )
            if should_operationalize_nunjucks:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"nunjucks"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"nunjucks"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"nunjucks"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if nunjucks_count >= max(2, host_count):
                    detected_ecosystem_scores["nunjucks"] += min(140, 32 + nunjucks_count * 14)

    twig_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"twig", "php", "javascript", "typescript", "node", "html", "css", "scss"},
    )
    if twig_ecosystem_counts["twig"] > 0:
        entrypoints, roots, configs = _twig_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("twig")
            twig_count = twig_ecosystem_counts["twig"]
            host_count = sum(
                twig_ecosystem_counts[ecosystem]
                for ecosystem in ("php", "javascript", "typescript", "node", "html", "css", "scss")
            )
            should_operationalize_twig = (
                twig_count >= 2
                and (
                    host_count == 0
                    or twig_count >= host_count
                    or (twig_count >= 4 and twig_count * 2 >= host_count)
                )
            )
            if should_operationalize_twig:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"twig"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"twig"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"twig"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if twig_count >= max(2, host_count):
                    detected_ecosystem_scores["twig"] += min(140, 32 + twig_count * 14)

    haml_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"haml", "ruby", "javascript", "typescript", "node", "html", "css", "scss"},
    )
    if haml_ecosystem_counts["haml"] > 0:
        entrypoints, roots, configs = _haml_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("haml")
            haml_count = haml_ecosystem_counts["haml"]
            host_count = sum(
                haml_ecosystem_counts[ecosystem]
                for ecosystem in ("ruby", "javascript", "typescript", "node", "html", "css", "scss")
            )
            should_operationalize_haml = (
                haml_count >= 2
                and (
                    host_count == 0
                    or haml_count >= host_count
                    or (haml_count >= 4 and haml_count * 2 >= host_count)
                )
            )
            if should_operationalize_haml:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"haml"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"haml"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"haml"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if haml_count >= max(2, host_count):
                    detected_ecosystem_scores["haml"] += min(140, 32 + haml_count * 14)

    slim_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"slim", "ruby", "javascript", "typescript", "node", "html", "css", "scss"},
    )
    if slim_ecosystem_counts["slim"] > 0:
        entrypoints, roots, configs = _slim_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("slim")
            slim_count = slim_ecosystem_counts["slim"]
            host_count = sum(
                slim_ecosystem_counts[ecosystem]
                for ecosystem in ("ruby", "javascript", "typescript", "node", "html", "css", "scss")
            )
            should_operationalize_slim = (
                slim_count >= 2
                and (
                    host_count == 0
                    or slim_count >= host_count
                    or (slim_count >= 4 and slim_count * 2 >= host_count)
                )
            )
            if should_operationalize_slim:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"slim"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"slim"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"slim"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if slim_count >= max(2, host_count):
                    detected_ecosystem_scores["slim"] += min(140, 32 + slim_count * 14)

    smarty_candidate_file_paths = candidate_file_paths
    smarty_ecosystem_counts = _candidate_ecosystem_counts(
        smarty_candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"smarty", "php", "javascript", "typescript", "node", "html", "css", "scss"},
    )
    if smarty_ecosystem_counts["smarty"] == 0:
        supplemented_smarty_candidate_file_paths = _supplement_candidate_file_paths_for_suffix_roots(
            repo_path=repo_path,
            candidate_file_paths=smarty_candidate_file_paths,
            suffixes={".tpl"},
            root_names=("templates", "views", "mails", "modules", "themes"),
            max_extra_files=max(32, min(256, max_files)),
        )
        if len(supplemented_smarty_candidate_file_paths) > len(smarty_candidate_file_paths):
            smarty_candidate_file_paths = supplemented_smarty_candidate_file_paths
            smarty_ecosystem_counts = _candidate_ecosystem_counts(
                smarty_candidate_file_paths,
                repo_path=repo_path,
                ecosystems={
                    "smarty",
                    "php",
                    "javascript",
                    "typescript",
                    "node",
                    "html",
                    "css",
                    "scss",
                },
            )
    if smarty_ecosystem_counts["smarty"] > 0:
        entrypoints, roots, configs = _smarty_profile_hints_from_candidates(
            repo_path,
            smarty_candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("smarty")
            smarty_count = smarty_ecosystem_counts["smarty"]
            host_count = sum(
                smarty_ecosystem_counts[ecosystem]
                for ecosystem in ("php", "javascript", "typescript", "node", "html", "css", "scss")
            )
            should_operationalize_smarty = (
                smarty_count >= 2
                and (
                    host_count == 0
                    or smarty_count >= host_count
                    or (smarty_count >= 6 and smarty_count * 2 >= host_count)
                )
            )
            if should_operationalize_smarty:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"smarty"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"smarty"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"smarty"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if smarty_count >= max(2, host_count):
                    detected_ecosystem_scores["smarty"] += min(140, 32 + smarty_count * 14)
            candidate_file_paths = list(dict.fromkeys(smarty_candidate_file_paths))

    erb_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"erb", "ruby", "javascript", "typescript", "node", "html", "css", "scss"},
    )
    if erb_ecosystem_counts["erb"] > 0:
        entrypoints, roots, configs = _erb_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("erb")
            erb_count = erb_ecosystem_counts["erb"]
            host_count = sum(
                erb_ecosystem_counts[ecosystem]
                for ecosystem in ("ruby", "javascript", "typescript", "node", "html", "css", "scss")
            )
            should_operationalize_erb = (
                erb_count >= 2
                and (
                    host_count == 0
                    or erb_count >= host_count
                    or (erb_count >= 4 and erb_count * 2 >= host_count)
                )
            )
            if should_operationalize_erb:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"erb"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"erb"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"erb"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if erb_count >= max(2, host_count):
                    detected_ecosystem_scores["erb"] += min(140, 32 + erb_count * 14)

    pug_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"pug", "javascript", "typescript", "node", "html", "css", "scss"},
    )
    if pug_ecosystem_counts["pug"] > 0:
        entrypoints, roots, configs = _pug_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("pug")
            pug_count = pug_ecosystem_counts["pug"]
            host_count = sum(
                pug_ecosystem_counts[ecosystem]
                for ecosystem in ("javascript", "typescript", "node", "html", "css", "scss")
            )
            should_operationalize_pug = (
                pug_count >= 2 and (host_count == 0 or pug_count >= host_count or (pug_count >= 4 and pug_count * 2 >= host_count))
            )
            if should_operationalize_pug:
                _register_candidate_ecosystems(entrypoint_candidate_ecosystems, values=entrypoints, ecosystems={"pug"})
                _register_candidate_ecosystems(support_root_candidate_ecosystems, values=roots, ecosystems={"pug"})
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"pug"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if pug_count >= max(2, host_count):
                    detected_ecosystem_scores["pug"] += min(140, 32 + pug_count * 14)

    ejs_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"ejs", "javascript", "typescript", "node", "html", "css", "scss"},
    )
    if ejs_ecosystem_counts["ejs"] > 0:
        entrypoints, roots, configs = _ejs_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("ejs")
            ejs_count = ejs_ecosystem_counts["ejs"]
            host_count = sum(
                ejs_ecosystem_counts[ecosystem]
                for ecosystem in ("javascript", "typescript", "node", "html", "css", "scss")
            )
            should_operationalize_ejs = (
                ejs_count >= 2
                and (
                    host_count == 0
                    or ejs_count >= host_count
                    or (ejs_count >= 4 and ejs_count * 2 >= host_count)
                )
            )
            if should_operationalize_ejs:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"ejs"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"ejs"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"ejs"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if ejs_count >= max(2, host_count):
                    detected_ecosystem_scores["ejs"] += min(140, 32 + ejs_count * 14)

    blade_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"blade", "php", "javascript", "typescript", "node", "html", "css", "scss"},
    )
    if blade_ecosystem_counts["blade"] > 0:
        entrypoints, roots, configs = _blade_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("blade")
            blade_count = blade_ecosystem_counts["blade"]
            host_count = sum(
                blade_ecosystem_counts[ecosystem]
                for ecosystem in ("php", "javascript", "typescript", "node", "html", "css", "scss")
            )
            should_operationalize_blade = (
                blade_count >= 2
                and (
                    host_count == 0
                    or blade_count >= host_count
                    or (blade_count >= 4 and blade_count * 2 >= host_count)
                )
            )
            if should_operationalize_blade:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"blade"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"blade"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"blade"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if blade_count >= max(2, host_count):
                    detected_ecosystem_scores["blade"] += min(140, 32 + blade_count * 14)

    vue_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"vue", "typescript", "javascript", "node", "html", "css", "scss"},
    )
    if vue_ecosystem_counts["vue"] > 0:
        entrypoints, roots, configs = _vue_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("vue")
            vue_count = vue_ecosystem_counts["vue"]
            host_count = sum(
                vue_ecosystem_counts[ecosystem]
                for ecosystem in ("typescript", "javascript", "node", "html", "css", "scss")
            )
            should_operationalize_vue = (
                vue_count >= 2 and (host_count == 0 or vue_count >= host_count or (vue_count >= 4 and vue_count * 2 >= host_count))
            )
            if should_operationalize_vue:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"vue"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"vue"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"vue"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if vue_count >= max(2, host_count):
                    detected_ecosystem_scores["vue"] += min(140, 32 + vue_count * 14)

    svelte_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"svelte", "typescript", "javascript", "node", "html", "css", "scss"},
    )
    if svelte_ecosystem_counts["svelte"] > 0:
        entrypoints, roots, configs = _svelte_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("svelte")
            svelte_count = svelte_ecosystem_counts["svelte"]
            host_count = sum(
                svelte_ecosystem_counts[ecosystem]
                for ecosystem in ("typescript", "javascript", "node", "html", "css", "scss")
            )
            should_operationalize_svelte = (
                svelte_count >= 2
                and (
                    host_count == 0
                    or svelte_count >= host_count
                    or (svelte_count >= 4 and svelte_count * 2 >= host_count)
                )
            )
            if should_operationalize_svelte:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"svelte"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"svelte"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"svelte"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if svelte_count >= max(2, host_count):
                    detected_ecosystem_scores["svelte"] += min(140, 32 + svelte_count * 14)

    astro_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"astro", "typescript", "javascript", "node", "html", "css", "scss"},
    )
    if astro_ecosystem_counts["astro"] > 0:
        entrypoints, roots, configs = _astro_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("astro")
            astro_count = astro_ecosystem_counts["astro"]
            host_count = sum(
                astro_ecosystem_counts[ecosystem]
                for ecosystem in ("typescript", "javascript", "node", "html", "css", "scss")
            )
            should_operationalize_astro = (
                astro_count >= 2
                and (
                    host_count == 0
                    or astro_count >= host_count
                    or (astro_count >= 4 and astro_count * 2 >= host_count)
                )
            )
            if should_operationalize_astro:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"astro"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"astro"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"astro"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if astro_count >= max(2, host_count):
                    detected_ecosystem_scores["astro"] += min(140, 32 + astro_count * 14)

    nextflow_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"nextflow", "groovy", "python", "shell", "dockerfile", "javascript", "node"},
    )
    if nextflow_ecosystem_counts["nextflow"] > 0:
        nextflow_manifest_path = next(
            (
                path
                for path in candidate_file_paths
                if PurePosixPath(path).name.lower() == "nextflow.config"
            ),
            None,
        )
        entrypoints, roots, configs = _nextflow_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
            manifest_path=nextflow_manifest_path,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("nextflow")
            nextflow_count = nextflow_ecosystem_counts["nextflow"]
            host_count = sum(
                nextflow_ecosystem_counts[ecosystem]
                for ecosystem in ("groovy", "python", "shell", "dockerfile", "javascript", "node")
            )
            should_operationalize_nextflow = (
                nextflow_count >= 2
                and (
                    host_count == 0
                    or nextflow_count >= host_count
                    or (nextflow_count >= 4 and nextflow_count * 2 >= host_count)
                )
            )
            if should_operationalize_nextflow:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"nextflow"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"nextflow"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"nextflow"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if nextflow_count >= max(2, host_count):
                    detected_ecosystem_scores["nextflow"] += min(140, 32 + nextflow_count * 14)

    robotframework_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"robotframework", "python", "html", "javascript"},
    )
    if robotframework_ecosystem_counts["robotframework"] > 0:
        entrypoints, roots, configs = _robotframework_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("robotframework")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"robotframework"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"robotframework"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"robotframework"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            robot_count = robotframework_ecosystem_counts["robotframework"]
            host_count = sum(
                robotframework_ecosystem_counts[ecosystem]
                for ecosystem in ("python", "html", "javascript")
            )
            if robot_count >= max(2, host_count):
                detected_ecosystem_scores["robotframework"] += min(120, 30 + robot_count * 14)

    gherkin_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"gherkin", "python", "javascript", "typescript", "java", "ruby", "go", "rust"},
    )
    if gherkin_ecosystem_counts["gherkin"] > 0:
        entrypoints, roots, configs = _gherkin_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("gherkin")
            gherkin_count = gherkin_ecosystem_counts["gherkin"]
            host_count = sum(
                gherkin_ecosystem_counts[ecosystem]
                for ecosystem in ("python", "javascript", "typescript", "java", "ruby", "go", "rust")
            )
            should_operationalize_gherkin = (
                gherkin_count >= 2
                and (
                    host_count == 0
                    or gherkin_count >= host_count
                    or (gherkin_count >= 4 and gherkin_count * 2 >= host_count)
                )
            )
            if should_operationalize_gherkin:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"gherkin"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"gherkin"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"gherkin"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if gherkin_count >= max(2, host_count):
                    detected_ecosystem_scores["gherkin"] += min(140, 32 + gherkin_count * 14)

    antlr_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"antlr", "java", "python", "javascript", "typescript", "csharp", "cpp", "go", "swift", "dart", "shell"},
    )
    if antlr_ecosystem_counts["antlr"] > 0:
        entrypoints, roots, configs = _antlr_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("antlr")
            antlr_count = antlr_ecosystem_counts["antlr"]
            host_count = sum(
                antlr_ecosystem_counts[ecosystem]
                for ecosystem in ("java", "python", "javascript", "typescript", "csharp", "cpp", "go", "swift", "dart", "shell")
            )
            should_operationalize_antlr = (
                antlr_count >= 2
                and (
                    host_count == 0
                    or antlr_count >= host_count
                    or (antlr_count >= 4 and antlr_count * 2 >= host_count)
                )
            )
            if should_operationalize_antlr:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"antlr"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"antlr"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"antlr"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if antlr_count >= max(2, host_count):
                    detected_ecosystem_scores["antlr"] += min(140, 32 + antlr_count * 14)

    graphviz_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"graphviz", "rust", "python", "javascript", "typescript", "java", "shell"},
    )
    if graphviz_ecosystem_counts["graphviz"] > 0:
        entrypoints, roots, configs = _graphviz_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("graphviz")
            graphviz_count = graphviz_ecosystem_counts["graphviz"]
            host_count = max(
                graphviz_ecosystem_counts[ecosystem]
                for ecosystem in ("rust", "python", "javascript", "typescript", "java", "shell")
            )
            if graphviz_count >= max(2, host_count):
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"graphviz"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"graphviz"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"graphviz"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                detected_ecosystem_scores["graphviz"] += min(140, 32 + graphviz_count * 14)

    mermaid_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"mermaid", "typescript", "javascript", "node", "python", "shell", "rust"},
    )
    if mermaid_ecosystem_counts["mermaid"] > 0:
        entrypoints, roots, configs = _mermaid_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("mermaid")
            mermaid_count = mermaid_ecosystem_counts["mermaid"]
            host_count = max(
                mermaid_ecosystem_counts[ecosystem]
                for ecosystem in ("typescript", "javascript", "node", "python", "shell", "rust")
            )
            if mermaid_count >= max(2, host_count):
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"mermaid"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"mermaid"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"mermaid"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                detected_ecosystem_scores["mermaid"] += min(140, 32 + mermaid_count * 14)

    plantuml_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"plantuml", "java", "kotlin", "typescript", "javascript", "node", "shell"},
    )
    if plantuml_ecosystem_counts["plantuml"] > 0:
        entrypoints, roots, configs = _plantuml_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("plantuml")
            plantuml_count = plantuml_ecosystem_counts["plantuml"]
            host_count = max(
                plantuml_ecosystem_counts[ecosystem]
                for ecosystem in ("java", "kotlin", "typescript", "javascript", "node", "shell")
            )
            if plantuml_count >= max(2, host_count):
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"plantuml"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"plantuml"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"plantuml"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                detected_ecosystem_scores["plantuml"] += min(140, 32 + plantuml_count * 14)

    openqasm_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"openqasm", "python", "cpp", "c", "rust", "javascript", "node"},
    )
    if openqasm_ecosystem_counts["openqasm"] > 0:
        entrypoints, roots, configs = _openqasm_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("openqasm")
            openqasm_count = openqasm_ecosystem_counts["openqasm"]
            host_count = max(
                openqasm_ecosystem_counts[ecosystem]
                for ecosystem in ("python", "cpp", "c", "rust", "javascript", "node")
            )
            if openqasm_count >= max(2, host_count):
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"openqasm"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"openqasm"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"openqasm"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                detected_ecosystem_scores["openqasm"] += min(140, 32 + openqasm_count * 14)

    move_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"move", "rust", "typescript", "javascript", "python", "shell"},
    )
    if move_ecosystem_counts["move"] > 0:
        entrypoints, roots, configs = _move_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("move")
            move_count = move_ecosystem_counts["move"]
            host_count = sum(
                move_ecosystem_counts[ecosystem]
                for ecosystem in ("rust", "typescript", "javascript", "python", "shell")
            )
            should_operationalize_move = (
                move_count >= 2
                and (
                    host_count == 0
                    or move_count >= host_count
                    or move_count * 3 >= host_count
                )
            )
            if should_operationalize_move:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"move"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"move"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"move"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if move_count >= max(2, host_count):
                    detected_ecosystem_scores["move"] += min(140, 32 + move_count * 14)

    modelica_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"modelica", "c", "cpp", "python", "shell", "makefile", "cmake"},
    )
    if modelica_ecosystem_counts["modelica"] > 0:
        entrypoints, roots, configs = _modelica_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("modelica")
            modelica_count = len(entrypoints)
            host_count = sum(
                modelica_ecosystem_counts[ecosystem]
                for ecosystem in ("c", "cpp", "python", "shell", "makefile", "cmake")
            )
            should_operationalize_modelica = modelica_count >= max(6, host_count * 2)
            if should_operationalize_modelica:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"modelica"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"modelica"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"modelica"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                detected_ecosystem_scores["modelica"] += min(140, 28 + modelica_count * 14)
            elif modelica_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("c", "cpp", "python", "shell", "makefile", "cmake"),
                    key=lambda ecosystem: modelica_ecosystem_counts[ecosystem],
                )
                if modelica_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        140,
                        24 + modelica_ecosystem_counts[dominant_host] * 6,
                    )
                    detected_ecosystem_scores["modelica"] = max(
                        0,
                        detected_ecosystem_scores["modelica"] - 48,
                    )

    rescript_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"rescript", "typescript", "javascript", "node", "shell"},
    )
    if rescript_ecosystem_counts["rescript"] > 0:
        entrypoints, roots, configs = _rescript_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("rescript")
            rescript_count = rescript_ecosystem_counts["rescript"]
            host_count = sum(
                rescript_ecosystem_counts[ecosystem]
                for ecosystem in ("typescript", "javascript", "node", "shell")
            )
            should_operationalize_rescript = (
                rescript_count >= 2
                and (
                    host_count == 0
                    or rescript_count >= host_count
                    or rescript_count * 3 >= host_count
                )
            )
            if should_operationalize_rescript:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"rescript"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"rescript"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"rescript"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if rescript_count >= max(2, host_count):
                    detected_ecosystem_scores["rescript"] += min(140, 32 + rescript_count * 14)
            elif rescript_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("typescript", "javascript", "node", "shell"),
                    key=lambda ecosystem: rescript_ecosystem_counts[ecosystem],
                )
                if rescript_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        140,
                        24 + rescript_ecosystem_counts[dominant_host] * 6,
                    )
                    detected_ecosystem_scores["rescript"] = max(
                        0,
                        detected_ecosystem_scores["rescript"] - 48,
                    )

    moonbit_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"moonbit", "rust", "python", "shell", "dockerfile", "javascript", "node"},
    )
    if moonbit_ecosystem_counts["moonbit"] > 0:
        moonbit_config_paths = sorted(config_path_candidates or set(discovered_config_paths))
        moonbit_manifest_path = next(
            (
                path
                for path in moonbit_config_paths
                if PurePosixPath(path).name.lower() == "moon.mod"
            ),
            None,
        ) or next(
            (
                path
                for path in moonbit_config_paths
                if PurePosixPath(path).name.lower() == "moon.pkg"
            ),
            None,
        )
        entrypoints, roots, configs = _moonbit_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
            manifest_path=moonbit_manifest_path or "",
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("moonbit")
            moonbit_count = len(entrypoints)
            host_count = sum(
                moonbit_ecosystem_counts[ecosystem]
                for ecosystem in ("rust", "python", "shell", "dockerfile", "javascript", "node")
            )
            should_operationalize_moonbit = (
                moonbit_count >= 2
                and (
                    host_count == 0
                    or moonbit_count >= host_count
                    or (moonbit_count >= 4 and moonbit_count * 2 >= host_count)
                )
            )
            if should_operationalize_moonbit:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"moonbit"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"moonbit"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"moonbit"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                if moonbit_count >= max(2, host_count):
                    detected_ecosystem_scores["moonbit"] += min(140, 32 + moonbit_count * 14)
            elif moonbit_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("rust", "python", "shell", "dockerfile", "javascript", "node"),
                    key=lambda ecosystem: moonbit_ecosystem_counts[ecosystem],
                )
                if moonbit_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        140,
                        24 + moonbit_ecosystem_counts[dominant_host] * 6,
                    )
                    detected_ecosystem_scores["moonbit"] = max(
                        0,
                        detected_ecosystem_scores["moonbit"] - 48,
                    )

    roc_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"roc", "rust", "zig", "nix", "shell", "python", "javascript", "node"},
    )
    if roc_ecosystem_counts["roc"] > 0:
        entrypoints, roots, configs = _roc_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("roc")
            roc_count = len(entrypoints)
            host_count = sum(
                roc_ecosystem_counts[ecosystem]
                for ecosystem in ("rust", "zig", "nix", "shell", "python", "javascript", "node")
            )
            should_operationalize_roc = roc_count >= max(6, host_count * 2)
            if should_operationalize_roc:
                _register_candidate_ecosystems(
                    entrypoint_candidate_ecosystems,
                    values=entrypoints,
                    ecosystems={"roc"},
                )
                _register_candidate_ecosystems(
                    support_root_candidate_ecosystems,
                    values=roots,
                    ecosystems={"roc"},
                )
                entrypoint_candidates.update(entrypoints)
                support_root_candidates.update(roots)
                config_path_candidates.update(configs)
                _accumulate_detected_ecosystem_scores(
                    detected_ecosystem_scores,
                    ecosystems={"roc"},
                    config_path=sorted(configs or entrypoints or roots or {""})[0],
                    repo_path=repo_path,
                    entrypoints=entrypoints,
                    roots=roots,
                    configs=configs,
                )
                detected_ecosystem_scores["roc"] += min(140, 28 + roc_count * 14)
            elif roc_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("rust", "zig", "nix", "shell", "python", "javascript", "node"),
                    key=lambda ecosystem: roc_ecosystem_counts[ecosystem],
                )
                if roc_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        140,
                        24 + roc_ecosystem_counts[dominant_host] * 6,
                    )
                    detected_ecosystem_scores["roc"] = max(
                        0,
                        detected_ecosystem_scores["roc"] - 48,
                    )

    typst_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"typst", "rust", "python", "javascript", "typescript", "go", "ruby"},
    )
    if typst_ecosystem_counts["typst"] > 0:
        entrypoints, roots, configs = _typst_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("typst")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"typst"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"typst"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"typst"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            typst_count = typst_ecosystem_counts["typst"]
            host_count = sum(
                typst_ecosystem_counts[ecosystem]
                for ecosystem in ("rust", "python", "javascript", "typescript", "go", "ruby")
            )
            if typst_count >= max(3, host_count):
                detected_ecosystem_scores["typst"] += min(140, 28 + typst_count * 12)
            elif typst_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("rust", "python", "javascript", "typescript", "go", "ruby"),
                    key=lambda ecosystem: typst_ecosystem_counts[ecosystem],
                )
                if typst_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        120,
                        24 + typst_ecosystem_counts[dominant_host] * 8,
                    )
                    detected_ecosystem_scores["typst"] = max(
                        0,
                        detected_ecosystem_scores["typst"] - 24,
                    )

    tex_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"tex", "c", "cpp", "go", "haskell", "javascript", "python", "ruby", "rust", "shell", "typescript"},
    )
    if tex_ecosystem_counts["tex"] > 0:
        entrypoints, roots, configs = _tex_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("tex")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"tex"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"tex"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"tex"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            tex_count = tex_ecosystem_counts["tex"]
            host_count = sum(
                tex_ecosystem_counts[ecosystem]
                for ecosystem in ("c", "cpp", "go", "haskell", "javascript", "python", "ruby", "rust", "shell", "typescript")
            )
            if tex_count >= max(4, host_count):
                detected_ecosystem_scores["tex"] += min(160, 36 + tex_count * 12)
            elif tex_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("c", "cpp", "go", "haskell", "javascript", "python", "ruby", "rust", "shell", "typescript"),
                    key=lambda ecosystem: tex_ecosystem_counts[ecosystem],
                )
                if tex_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        140,
                        24 + tex_ecosystem_counts[dominant_host] * 8,
                    )
                    detected_ecosystem_scores["tex"] = max(
                        0,
                        detected_ecosystem_scores["tex"] - 24,
                    )

    rst_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"rst", "python", "javascript", "typescript", "go", "ruby", "rust", "shell"},
    )
    if rst_ecosystem_counts["rst"] > 0:
        entrypoints, roots, configs = _rst_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("rst")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"rst"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"rst"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"rst"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            rst_count = rst_ecosystem_counts["rst"]
            host_count = sum(
                rst_ecosystem_counts[ecosystem]
                for ecosystem in ("python", "javascript", "typescript", "go", "ruby", "rust", "shell")
            )
            if rst_count >= max(4, host_count):
                detected_ecosystem_scores["rst"] += min(160, 36 + rst_count * 12)
            elif rst_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("python", "javascript", "typescript", "go", "ruby", "rust", "shell"),
                    key=lambda ecosystem: rst_ecosystem_counts[ecosystem],
                )
                if rst_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        140,
                        24 + rst_ecosystem_counts[dominant_host] * 8,
                    )
                    detected_ecosystem_scores["rst"] = max(
                        0,
                        detected_ecosystem_scores["rst"] - 24,
                    )

    asciidoc_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"asciidoc", "python", "javascript", "typescript", "go", "ruby", "rust", "shell"},
    )
    if asciidoc_ecosystem_counts["asciidoc"] > 0:
        entrypoints, roots, configs = _asciidoc_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("asciidoc")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"asciidoc"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"asciidoc"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"asciidoc"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            asciidoc_count = asciidoc_ecosystem_counts["asciidoc"]
            host_count = sum(
                asciidoc_ecosystem_counts[ecosystem]
                for ecosystem in ("python", "javascript", "typescript", "go", "ruby", "rust", "shell")
            )
            if asciidoc_count >= max(4, host_count):
                detected_ecosystem_scores["asciidoc"] += min(160, 36 + asciidoc_count * 12)
            elif asciidoc_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("python", "javascript", "typescript", "go", "ruby", "rust", "shell"),
                    key=lambda ecosystem: asciidoc_ecosystem_counts[ecosystem],
                )
                if asciidoc_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        140,
                        24 + asciidoc_ecosystem_counts[dominant_host] * 8,
                    )
                    detected_ecosystem_scores["asciidoc"] = max(
                        0,
                        detected_ecosystem_scores["asciidoc"] - 24,
                    )

    org_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"org", "emacslisp", "python", "javascript", "typescript", "go", "ruby", "rust", "shell"},
    )
    if org_ecosystem_counts["org"] > 0:
        entrypoints, roots, configs = _org_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("org")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"org"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"org"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"org"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            org_count = org_ecosystem_counts["org"]
            host_count = sum(
                org_ecosystem_counts[ecosystem]
                for ecosystem in ("emacslisp", "python", "javascript", "typescript", "go", "ruby", "rust", "shell")
            )
            if org_count >= max(4, host_count):
                detected_ecosystem_scores["org"] += min(160, 36 + org_count * 12)
            elif org_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("emacslisp", "python", "javascript", "typescript", "go", "ruby", "rust", "shell"),
                    key=lambda ecosystem: org_ecosystem_counts[ecosystem],
                )
                if org_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] += min(
                        140,
                        24 + org_ecosystem_counts[dominant_host] * 8,
                    )
                    detected_ecosystem_scores["org"] = max(
                        0,
                        detected_ecosystem_scores["org"] - 24,
                    )

    cython_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"cython", "python", "c", "cpp"},
    )
    if cython_ecosystem_counts["cython"] > 0:
        entrypoints, roots, configs = _cython_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"cython"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"cython"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"cython"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            cython_count = cython_ecosystem_counts["cython"]
            host_count = sum(
                cython_ecosystem_counts[ecosystem] for ecosystem in ("python", "c", "cpp")
            )
            if cython_count >= max(2, host_count):
                detected_ecosystem_scores["cython"] += min(120, 30 + cython_count * 14)

    cuda_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"cuda", "c", "cpp", "python", "cmake"},
    )
    if cuda_ecosystem_counts["cuda"] > 0:
        entrypoints, roots, configs = _cuda_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("cuda")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"cuda"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"cuda"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"cuda"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            cuda_count = cuda_ecosystem_counts["cuda"]
            host_count = sum(
                cuda_ecosystem_counts[ecosystem] for ecosystem in ("c", "cpp", "python", "cmake")
            )
            cuda_entrypoint_root_count = len(
                {
                    normalized_root
                    for path in entrypoints
                    if (
                        normalized_root := repository_service._normalize_repository_relative_path(
                            str(PurePosixPath(path).parent)
                        )
                    )
                }
            )
            cuda_neighbor_config_count = len(configs)
            if (
                cuda_count >= 24
                and cuda_neighbor_config_count >= 8
                and cuda_entrypoint_root_count >= 8
            ):
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
            elif cuda_count >= 24 and cuda_count * 2 >= max(1, host_count):
                detected_ecosystem_scores["cuda"] += min(240, 80 + cuda_count // 2)

    stan_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"stan", "r", "python", "c", "cpp", "julia", "matlab"},
    )
    if stan_ecosystem_counts["stan"] > 0:
        entrypoints, roots, configs = _stan_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"stan"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"stan"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"stan"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            stan_count = stan_ecosystem_counts["stan"]
            host_count = sum(
                stan_ecosystem_counts[ecosystem]
                for ecosystem in ("r", "python", "c", "cpp", "julia", "matlab")
            )
            if stan_count >= 8 and stan_count * 2 >= max(1, host_count):
                detected_ecosystem_scores["stan"] += min(240, 80 + stan_count // 2)

    protobuf_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"protobuf", "cpp", "c", "go", "java", "python", "ruby", "rust", "typescript", "starlark", "dockerfile"},
    )
    if protobuf_ecosystem_counts["protobuf"] > 0:
        entrypoints, roots, configs = _protobuf_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            detected_ecosystems.add("protobuf")
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"protobuf"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"protobuf"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"protobuf"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            protobuf_count = protobuf_ecosystem_counts["protobuf"]
            host_count = sum(
                protobuf_ecosystem_counts[ecosystem]
                for ecosystem in ("cpp", "c", "go", "java", "python", "ruby", "rust", "typescript", "starlark", "dockerfile")
            )
            if protobuf_count >= max(8, host_count * 2):
                non_protobuf_max_score = max(
                    (
                        score
                        for ecosystem, score in detected_ecosystem_scores.items()
                        if ecosystem != "protobuf"
                    ),
                    default=0,
                )
                detected_ecosystem_scores["protobuf"] = max(
                    detected_ecosystem_scores["protobuf"],
                    non_protobuf_max_score + 32,
                )
            if protobuf_count >= max(8, host_count):
                detected_ecosystem_scores["protobuf"] += min(220, 60 + protobuf_count * 6)
            elif protobuf_count * 2 <= max(1, host_count):
                dominant_host = max(
                    ("cpp", "c", "go", "java", "python", "ruby", "rust", "typescript"),
                    key=lambda ecosystem: protobuf_ecosystem_counts[ecosystem],
                )
                if protobuf_ecosystem_counts[dominant_host] > 0:
                    detected_ecosystem_scores[dominant_host] = max(
                        detected_ecosystem_scores.get(dominant_host, 0),
                        28 + protobuf_ecosystem_counts[dominant_host] * 8,
                    )
                detected_ecosystem_scores["protobuf"] = max(
                    0,
                    detected_ecosystem_scores["protobuf"] - 24,
                )

    qml_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"qml", "qmake", "cmake", "c", "cpp", "objectivec", "java", "groovy"},
    )
    if qml_ecosystem_counts["qml"] > 0:
        entrypoints, roots, configs = _qml_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"qml"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"qml"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"qml"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            qml_count = qml_ecosystem_counts["qml"]
            host_count = sum(
                qml_ecosystem_counts[ecosystem]
                for ecosystem in ("qmake", "cmake", "c", "cpp", "objectivec", "java", "groovy")
            )
            if qml_count >= max(2, host_count):
                detected_ecosystem_scores["qml"] += min(120, 30 + qml_count * 14)

    shaderlab_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"shaderlab", "hlsl", "glsl", "cs", "javascript"},
    )
    if shaderlab_ecosystem_counts["shaderlab"] > 0:
        entrypoints, roots, configs = _shaderlab_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"shaderlab"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"shaderlab"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"shaderlab"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            shaderlab_count = shaderlab_ecosystem_counts["shaderlab"]
            host_count = sum(
                shaderlab_ecosystem_counts[ecosystem]
                for ecosystem in ("hlsl", "glsl", "cs", "javascript")
            )
            if shaderlab_count >= max(2, host_count):
                detected_ecosystem_scores["shaderlab"] += min(120, 30 + shaderlab_count * 14)

    wgsl_ecosystem_counts = _candidate_ecosystem_counts(
        candidate_file_paths,
        repo_path=repo_path,
        ecosystems={"wgsl", "typescript", "javascript", "node", "rust", "cpp", "hlsl", "glsl"},
    )
    if wgsl_ecosystem_counts["wgsl"] > 0:
        entrypoints, roots, configs = _wgsl_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        if entrypoints or roots or configs:
            _register_candidate_ecosystems(
                entrypoint_candidate_ecosystems,
                values=entrypoints,
                ecosystems={"wgsl"},
            )
            _register_candidate_ecosystems(
                support_root_candidate_ecosystems,
                values=roots,
                ecosystems={"wgsl"},
            )
            entrypoint_candidates.update(entrypoints)
            support_root_candidates.update(roots)
            config_path_candidates.update(configs)
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems={"wgsl"},
                config_path=sorted(configs or entrypoints or roots or {""})[0],
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
            )
            wgsl_count = wgsl_ecosystem_counts["wgsl"]
            host_count = sum(
                wgsl_ecosystem_counts[ecosystem]
                for ecosystem in ("typescript", "javascript", "node", "rust", "cpp", "hlsl", "glsl")
            )
            if wgsl_count >= max(2, host_count):
                detected_ecosystem_scores["wgsl"] += min(120, 30 + wgsl_count * 14)

    if "glsl" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _glsl_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"glsl"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"glsl"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"glsl"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "hlsl" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _hlsl_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"hlsl"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"hlsl"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"hlsl"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "hcl" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _hcl_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"hcl"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"hcl"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"hcl"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "bicep" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _bicep_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"bicep"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"bicep"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"bicep"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "tlaplus" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _tlaplus_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"tlaplus"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"tlaplus"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"tlaplus"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "logtalk" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _logtalk_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"logtalk"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"logtalk"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"logtalk"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "chapel" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _chapel_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"chapel"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"chapel"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"chapel"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "odin" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _odin_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"odin"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"odin"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"odin"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "factor" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _factor_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"factor"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"factor"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"factor"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )
    if "cue" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _cue_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"cue"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"cue"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"cue"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "eiffel" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _eiffel_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"eiffel"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"eiffel"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"eiffel"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "rego" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _rego_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"rego"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"rego"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"rego"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if "yara" in detected_ecosystems and not (
        entrypoint_candidates or support_root_candidates or config_path_candidates
    ):
        entrypoints, roots, configs = _yara_profile_hints_from_candidates(
            repo_path,
            candidate_file_paths,
        )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems={"yara"},
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems={"yara"},
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
        _accumulate_detected_ecosystem_scores(
            detected_ecosystem_scores,
            ecosystems={"yara"},
            config_path=sorted(configs or entrypoints or roots or {""})[0],
            repo_path=repo_path,
            entrypoints=entrypoints,
            roots=roots,
            configs=configs,
        )

    if support_root_candidates:
        existing_entrypoint_paths = set(
            _candidate_existing_paths(
                repo_path,
                paths=entrypoint_candidates,
            )
        )
        support_scan_roots = _support_roots_requiring_expansion(
            candidate_file_paths=candidate_file_paths,
            support_roots=_candidate_existing_leaf_roots(
                repo_path,
                roots=support_root_candidates,
                entrypoint_paths=existing_entrypoint_paths,
            ),
        )
        if support_scan_roots:
            support_scan_seed_paths = [
                path
                for path in _candidate_existing_paths(
                    repo_path,
                    paths=entrypoint_candidates,
                )
                if _is_repo_profile_code_candidate(path, repo_path=repo_path)
                and not repository_service._is_test_path(path)
                and not _is_non_operational_profile_path(path)
            ]
            support_scan_seed_paths = _balanced_profile_paths(
                paths=support_scan_seed_paths,
                detected_ecosystems=detected_ecosystems,
                repo_path=repo_path,
                support_roots=support_root_candidates,
                limit=_profile_entrypoint_target_count(detected_ecosystems),
                ecosystem_scores=detected_ecosystem_scores,
            )
            support_candidate_paths = _candidate_repository_file_paths(
                repo_path=repo_path,
                seed_paths=support_scan_seed_paths,
                bridge_paths=support_scan_roots,
                include_patterns=DEFAULT_INCLUDE_PATTERNS,
                max_files=min(max_files, 512),
            )
            if "bitbake" in detected_ecosystems:
                support_candidate_paths = [
                    path
                    for path in support_candidate_paths
                    if repository_service.bitbake_adapter.has_bitbake_path_hints(
                        PurePosixPath(path)
                    )
                ]
            candidate_file_paths = list(
                dict.fromkeys(candidate_file_paths + support_candidate_paths)
            )

    if "scala" in detected_ecosystems:
        support_root_candidates.update(_scala_support_roots_from_candidates(candidate_file_paths))

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
        matched_ecosystems = _candidate_ecosystems_for_path(
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
    cuda_count = _candidate_ecosystem_counts(
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
        key=lambda path: _rank_repo_profile_seed_path(
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
        or _candidate_ecosystems_for_path(path, repo_path=repo_path) & detected_ecosystems
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
        "detected_ecosystems": _ordered_detected_ecosystems(
            detected_ecosystems,
        ),
        "operational_ecosystems": _ordered_operational_ecosystems(
            detected_ecosystems,
            ecosystem_scores=detected_ecosystem_scores,
        ),
    }


def _derive_operational_seed_paths_without_diagnostics(
    *,
    repo_path: Path,
    focus_paths: list[str],
    max_files: int,
) -> list[str]:
    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=focus_paths,
        max_files=max_files,
    )
    return list(seed_plan["entrypoint_files"])


def _build_connected_dependency_map(
    *,
    repo_path: Path,
    seed_paths: list[str],
    bridge_paths: list[str],
    candidate_file_paths: list[str] | None = None,
    candidate_scope_paths: list[str] | None = None,
    enable_reverse_bridging: bool = True,
    include_patterns: list[str],
    max_files: int,
    max_file_size_bytes: int,
    max_dependency_depth: int,
    max_connected_files: int,
) -> dict[str, Any]:
    concrete_seed_count = len(
        {
            repository_service._normalize_repository_relative_path(seed_path)
            for seed_path in seed_paths
            if _looks_like_concrete_file_seed(seed_path)
        }
    )
    seed_includes_tests = any(
        repository_service._is_test_path(
            repository_service._normalize_repository_relative_path(seed_path)
        )
        for seed_path in seed_paths
    )
    candidate_file_limit = _connected_map_candidate_file_limit(
        max_files=max_files,
        max_connected_files=max_connected_files,
        concrete_seed_count=concrete_seed_count,
    )
    if candidate_file_paths is not None:
        candidate_file_paths = _normalized_candidate_file_paths(
            repo_path=repo_path,
            candidate_file_paths=candidate_file_paths,
            include_patterns=include_patterns,
            max_files=candidate_file_limit,
        )
    else:
        candidate_file_paths = _candidate_repository_file_paths(
            repo_path=repo_path,
            seed_paths=seed_paths,
            bridge_paths=list(candidate_scope_paths or bridge_paths),
            include_patterns=include_patterns,
            max_files=candidate_file_limit,
        )
    module_index = repository_service._build_module_index(
        candidate_file_paths,
        root_path=repo_path,
    )
    workspace_package_index = repository_service._build_workspace_package_index(repo_path)
    workspace_go_module_index = repository_service._build_workspace_go_module_index(repo_path)
    analysis_context_hash = repository_service._file_analysis_context_hash(
        module_index=module_index,
        workspace_package_index=workspace_package_index,
        workspace_go_module_index=workspace_go_module_index,
        max_file_size_bytes=max_file_size_bytes,
        engine_revision=repository_service._REPOSITORY_INTELLIGENCE_ENGINE_REVISION,
    )
    git_content_hashes = (
        repository_service._git_tracked_content_hashes(
            repo_path,
            candidate_paths=candidate_file_paths,
        )
        if repository_service._is_git_repository(repo_path)
        else None
    )
    seed_files = _seed_dependency_files(
        candidate_file_paths=candidate_file_paths,
        seed_paths=seed_paths,
        max_connected_files=max_connected_files,
    )
    if not seed_files:
        return {
            "seed_files": [],
            "connected_files": [],
            "candidate_file_limit": candidate_file_limit,
            "candidate_file_count": len(candidate_file_paths),
            "connected_file_count": 0,
            "concrete_seed_count": concrete_seed_count,
            "resolved_dependency_edges": 0,
            "unresolved_dependency_count": 0,
            "max_dependency_depth": max_dependency_depth,
            "top_hubs": [],
        }

    queue: deque[tuple[str, int]] = deque((file_path, 0) for file_path in seed_files)
    visited: set[str] = set()
    dependency_cache: dict[str, tuple[repository_service._Dependency, ...]] = {}
    edges: list[tuple[str, str]] = []
    unresolved_dependencies: Counter[str] = Counter()
    inbound_counts: Counter[str] = Counter()
    outbound_counts: Counter[str] = Counter()

    def _load_dependencies(file_path: str) -> tuple[repository_service._Dependency, ...]:
        candidate = repo_path / file_path
        if not candidate.is_file():
            return ()
        dependencies = dependency_cache.get(file_path)
        if dependencies is None:
            dependencies = repository_service._analyze_file_dependencies_cached(
                root_path=repo_path,
                path=candidate,
                module_index=module_index,
                workspace_package_index=workspace_package_index,
                workspace_go_module_index=workspace_go_module_index,
                max_file_size_bytes=max_file_size_bytes,
                analysis_context_hash=analysis_context_hash,
                git_content_hashes=git_content_hashes,
            )
            dependency_cache[file_path] = dependencies
        return dependencies

    while queue and len(visited) < max_connected_files:
        file_path, depth = queue.popleft()
        if file_path in visited:
            continue
        visited.add(file_path)
        dependencies = _load_dependencies(file_path)
        for dependency in dependencies:
            target_file = dependency.target_file
            if target_file and (repo_path / target_file).is_file():
                edges.append((dependency.source_file, target_file))
                outbound_counts[dependency.source_file] += 1
                inbound_counts[target_file] += 1
                if (
                    target_file not in visited
                    and depth < max_dependency_depth
                    and len(visited) + len(queue) < max_connected_files
                ):
                    queue.append((target_file, depth + 1))
                continue
            unresolved_dependencies[dependency.target_symbol or "<unknown>"] += 1

    bridged_importers: list[str] = []
    if enable_reverse_bridging and bridge_paths:
        bridge_files = _seed_dependency_files(
            candidate_file_paths=candidate_file_paths,
            seed_paths=bridge_paths,
            max_connected_files=max_files,
        )
        bridge_files = [
            file_path
            for file_path in bridge_files
            if seed_includes_tests or not repository_service._is_test_path(file_path)
        ]
        connected_targets = set(visited)
        for bridge_file in bridge_files:
            if len(visited) >= max_connected_files:
                break
            if bridge_file in visited:
                continue
            dependencies = _load_dependencies(bridge_file)
            if not any(
                dependency.target_file and dependency.target_file in connected_targets
                for dependency in dependencies
            ):
                continue
            bridged_importers.append(bridge_file)
            queue.append((bridge_file, 1))

    while queue and len(visited) < max_connected_files:
        file_path, depth = queue.popleft()
        if file_path in visited:
            continue
        visited.add(file_path)
        dependencies = _load_dependencies(file_path)
        for dependency in dependencies:
            target_file = dependency.target_file
            if target_file and (repo_path / target_file).is_file():
                edges.append((dependency.source_file, target_file))
                outbound_counts[dependency.source_file] += 1
                inbound_counts[target_file] += 1
                if (
                    target_file not in visited
                    and depth < max_dependency_depth
                    and len(visited) + len(queue) < max_connected_files
                ):
                    queue.append((target_file, depth + 1))
                continue
            unresolved_dependencies[dependency.target_symbol or "<unknown>"] += 1

    top_hubs = []
    for file_path in sorted(visited):
        total_degree = inbound_counts[file_path] + outbound_counts[file_path]
        if total_degree == 0:
            continue
        top_hubs.append(
            {
                "file_path": file_path,
                "incoming_dependency_count": inbound_counts[file_path],
                "outgoing_dependency_count": outbound_counts[file_path],
                "total_dependency_degree": total_degree,
            }
        )
    top_hubs.sort(
        key=lambda entry: (
            -int(entry["incoming_dependency_count"]),
            -int(entry["outgoing_dependency_count"]),
            str(entry["file_path"]),
        )
    )

    return {
        "seed_files": seed_files,
        "candidate_file_limit": candidate_file_limit,
        "connected_files": sorted(visited),
        "candidate_file_count": len(candidate_file_paths),
        "connected_file_count": len(visited),
        "concrete_seed_count": concrete_seed_count,
        "bridged_importer_count": len(bridged_importers),
        "bridged_importers": sorted(bridged_importers)[:32],
        "resolved_dependency_edges": len(edges),
        "unresolved_dependency_count": sum(unresolved_dependencies.values()),
        "unresolved_dependency_samples": [
            {"target": target, "count": count}
            for target, count in unresolved_dependencies.most_common(12)
        ],
        "max_dependency_depth": max_dependency_depth,
        "top_hubs": top_hubs[:12],
    }


def _load_snapshot_graph_summary(
    *,
    repository_graph_path: str,
    dependency_graph_path: str,
    symbol_graph_path: str,
    seed_files: list[str],
) -> dict[str, Any]:
    from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    symbol_kind_weights = {
        "async_function": 12,
        "async_function_expression": 12,
        "async_method": 12,
        "arrow_function": 11,
        "class_field_arrow": 11,
        "function": 10,
        "function_expression": 10,
        "method": 10,
        "get_method": 9,
        "set_method": 9,
        "constructor": 9,
        "class": 8,
        "class_expression": 8,
        "const": 4,
        "symbol": 3,
        "type": 1,
        "interface": 1,
    }
    operational_symbol_kinds = {
        "async_function",
        "async_function_expression",
        "async_method",
        "arrow_function",
        "class",
        "class_expression",
        "class_field_arrow",
        "constructor",
        "function",
        "function_expression",
        "get_method",
        "method",
        "set_method",
    }

    repository_graph_rows = pq.read_table(repository_graph_path).to_pylist()
    dependency_rows = pq.read_table(dependency_graph_path).to_pylist()
    symbol_rows = pq.read_table(symbol_graph_path).to_pylist()

    inbound_counts: Counter[str] = Counter()
    outbound_counts: Counter[str] = Counter()
    unresolved_dependency_targets: Counter[str] = Counter()
    cross_boundary_edges = 0
    for row in dependency_rows:
        source_file = str(row.get("source_file") or "")
        target_file = row.get("target_file")
        if target_file:
            target_file = str(target_file)
            outbound_counts[source_file] += 1
            inbound_counts[target_file] += 1
            source_scope = Path(source_file).parts[:1]
            target_scope = Path(target_file).parts[:1]
            if source_scope and target_scope and source_scope != target_scope:
                cross_boundary_edges += 1
            continue
        unresolved_dependency_targets[str(row.get("target_symbol") or "<unknown>")] += 1

    symbol_counts: Counter[str] = Counter()
    nested_symbol_counts: Counter[str] = Counter()
    top_level_symbols: dict[str, list[str]] = {}
    symbol_names_by_id: dict[str, str] = {}
    symbol_rows_by_id: dict[str, dict[str, Any]] = {}
    nested_symbol_examples: dict[str, list[dict[str, str]]] = {}
    for row in symbol_rows:
        symbol_id = str(row.get("symbol_id") or "")
        if symbol_id:
            symbol_names_by_id[symbol_id] = str(row.get("symbol_name") or "")
            symbol_rows_by_id[symbol_id] = row
    for row in symbol_rows:
        file_path = str(row.get("file_path") or "")
        symbol_counts[file_path] += 1
        if row.get("parent_symbol_id"):
            nested_symbol_counts[file_path] += 1
            nested_symbol_examples.setdefault(file_path, [])
            if len(nested_symbol_examples[file_path]) < 8:
                parent_symbol_id = str(row.get("parent_symbol_id") or "")
                nested_symbol_examples[file_path].append(
                    {
                        "parent_symbol": symbol_names_by_id.get(parent_symbol_id, parent_symbol_id),
                        "child_symbol": str(row.get("symbol_name") or ""),
                        "child_kind": str(row.get("symbol_kind") or ""),
                    }
                )
            continue
        top_level_symbols.setdefault(file_path, [])
        if len(top_level_symbols[file_path]) < 8:
            top_level_symbols[file_path].append(str(row.get("symbol_name") or ""))

    risk_rows = []
    for file_path in sorted(set(symbol_counts) | set(inbound_counts) | set(outbound_counts)):
        risk_rows.append(
            {
                "file_path": file_path,
                "incoming_dependency_count": inbound_counts[file_path],
                "outgoing_dependency_count": outbound_counts[file_path],
                "symbol_count": symbol_counts[file_path],
                "nested_symbol_count": nested_symbol_counts[file_path],
                "top_level_symbols": top_level_symbols.get(file_path, []),
                "nested_symbol_examples": nested_symbol_examples.get(file_path, []),
                "seed_related": file_path in seed_files,
            }
        )
    risk_rows.sort(
        key=lambda row: (
            -int(row["incoming_dependency_count"]),
            -int(row["outgoing_dependency_count"]),
            -int(row["symbol_count"]),
            str(row["file_path"]),
        )
    )

    symbol_child_counts: Counter[str] = Counter()
    symbol_reference_inbound_counts: Counter[str] = Counter()
    symbol_reference_outbound_counts: Counter[str] = Counter()
    raw_symbol_reference_edges: list[tuple[str, str]] = []
    for row in repository_graph_rows:
        edge_type = str(row.get("edge_type") or "")
        source_node = str(row.get("source_node") or "")
        target_node = str(row.get("target_node") or "")
        if edge_type == "contains_symbol":
            if not source_node.startswith("symbol:"):
                continue
            parent_symbol_id = source_node.removeprefix("symbol:")
            if parent_symbol_id:
                symbol_child_counts[parent_symbol_id] += 1
            continue
        if (
            edge_type == "references_symbol"
            and source_node.startswith("symbol:")
            and target_node.startswith("symbol:")
        ):
            source_symbol_id = source_node.removeprefix("symbol:")
            target_symbol_id = target_node.removeprefix("symbol:")
            if not source_symbol_id or not target_symbol_id:
                continue
            symbol_reference_outbound_counts[source_symbol_id] += 1
            symbol_reference_inbound_counts[target_symbol_id] += 1
            raw_symbol_reference_edges.append((source_symbol_id, target_symbol_id))

    symbol_risk_rows = []
    symbol_risk_rows_by_id: dict[str, dict[str, Any]] = {}
    for symbol_id, row in symbol_rows_by_id.items():
        file_path = str(row.get("file_path") or "")
        symbol_name = str(row.get("symbol_name") or "")
        symbol_kind = str(row.get("symbol_kind") or "")
        parent_symbol_id = str(row.get("parent_symbol_id") or "")
        depth = 0
        current_parent = parent_symbol_id
        while current_parent:
            depth += 1
            parent_row = symbol_rows_by_id.get(current_parent)
            if parent_row is None:
                break
            current_parent = str(parent_row.get("parent_symbol_id") or "")
        kind_weight = symbol_kind_weights.get(symbol_kind, 2)
        risk_score = (
            symbol_reference_inbound_counts[symbol_id] * 20
            + symbol_reference_outbound_counts[symbol_id] * 8
            + inbound_counts[file_path] * 5
            + outbound_counts[file_path] * 2
            + symbol_child_counts[symbol_id] * 4
            + depth * 2
            + kind_weight * 3
        )
        symbol_risk_rows.append(
            {
                "symbol_id": symbol_id,
                "file_path": file_path,
                "symbol_name": symbol_name,
                "symbol_kind": symbol_kind,
                "parent_symbol": symbol_names_by_id.get(parent_symbol_id, parent_symbol_id)
                if parent_symbol_id
                else None,
                "child_symbol_count": symbol_child_counts[symbol_id],
                "depth": depth,
                "incoming_symbol_reference_count": symbol_reference_inbound_counts[symbol_id],
                "outgoing_symbol_reference_count": symbol_reference_outbound_counts[symbol_id],
                "incoming_dependency_count": inbound_counts[file_path],
                "outgoing_dependency_count": outbound_counts[file_path],
                "kind_weight": kind_weight,
                "risk_score": risk_score,
            }
        )
        symbol_risk_rows_by_id[symbol_id] = symbol_risk_rows[-1]
    symbol_risk_rows.sort(
        key=lambda row: (
            -int(row["risk_score"]),
            -int(row["child_symbol_count"]),
            -int(row["kind_weight"]),
            -int(row["incoming_dependency_count"]),
            str(row["file_path"]),
            str(row["symbol_name"]),
        )
    )

    def _limit_symbol_rows(
        rows: list[dict[str, Any]],
        *,
        limit: int,
        max_per_file: int,
    ) -> list[dict[str, Any]]:
        per_file_counts: Counter[str] = Counter()
        selected_rows: list[dict[str, Any]] = []
        for row in rows:
            file_path = str(row.get("file_path") or "")
            if per_file_counts[file_path] >= max_per_file:
                continue
            selected_rows.append(row)
            per_file_counts[file_path] += 1
            if len(selected_rows) >= limit:
                break
        return selected_rows

    operational_symbol_risk_rows = [
        row
        for row in symbol_risk_rows
        if str(row.get("symbol_kind") or "") in operational_symbol_kinds
    ]
    symbol_reference_edges = []
    for source_symbol_id, target_symbol_id in raw_symbol_reference_edges:
        source_row = symbol_risk_rows_by_id.get(source_symbol_id)
        target_row = symbol_risk_rows_by_id.get(target_symbol_id)
        if source_row is None or target_row is None:
            continue
        cross_file = str(source_row["file_path"]) != str(target_row["file_path"])
        combined_risk_score = (
            int(source_row["risk_score"])
            + int(target_row["risk_score"])
            + (20 if cross_file else 0)
        )
        symbol_reference_edges.append(
            {
                "source_file": str(source_row["file_path"]),
                "source_symbol": str(source_row["symbol_name"]),
                "source_kind": str(source_row["symbol_kind"]),
                "source_risk_score": int(source_row["risk_score"]),
                "target_file": str(target_row["file_path"]),
                "target_symbol": str(target_row["symbol_name"]),
                "target_kind": str(target_row["symbol_kind"]),
                "target_risk_score": int(target_row["risk_score"]),
                "cross_file": cross_file,
                "combined_risk_score": combined_risk_score,
            }
        )
    symbol_reference_edges.sort(
        key=lambda row: (
            -int(row["combined_risk_score"]),
            -int(row["target_risk_score"]),
            0 if bool(row["cross_file"]) else 1,
            str(row["source_file"]),
            str(row["source_symbol"]),
            str(row["target_file"]),
            str(row["target_symbol"]),
        )
    )
    operational_reference_edges = [
        row
        for row in symbol_reference_edges
        if row["target_kind"] in operational_symbol_kinds
    ]
    operational_reference_edges.sort(
        key=lambda row: (
            -int(row["combined_risk_score"]),
            0 if bool(row["cross_file"]) else 1,
            -int(row["target_risk_score"]),
            str(row["source_file"]),
            str(row["source_symbol"]),
            str(row["target_file"]),
            str(row["target_symbol"]),
        )
    )

    return {
        "resolved_dependency_edge_count": sum(outbound_counts.values()),
        "unresolved_dependency_count": sum(unresolved_dependency_targets.values()),
        "cross_boundary_edge_count": cross_boundary_edges,
        "symbol_count": len(symbol_rows),
        "parent_child_symbol_count": sum(nested_symbol_counts.values()),
        "symbol_reference_edge_count": sum(symbol_reference_outbound_counts.values()),
        "highest_change_risk_files": risk_rows[:16],
        "highest_change_risk_symbols": _limit_symbol_rows(
            symbol_risk_rows,
            limit=24,
            max_per_file=3,
        ),
        "highest_change_risk_operational_symbols": _limit_symbol_rows(
            operational_symbol_risk_rows,
            limit=24,
            max_per_file=2,
        ),
        "top_symbol_reference_edges": symbol_reference_edges[:24],
        "highest_change_risk_operational_edges": operational_reference_edges[:24],
        "unresolved_dependency_samples": [
            {"target": target, "count": count}
            for target, count in unresolved_dependency_targets.most_common(16)
        ],
    }


def _candidate_solutions(diagnostics: list[RepositoryDiagnostic]) -> list[dict[str, Any]]:
    if not diagnostics:
        return []
    ts6059 = [entry for entry in diagnostics if entry.code == "TS6059"]
    if ts6059:
        impacted_paths = sorted({entry.path for entry in ts6059 if entry.path})
        return [
            {
                "problem_class": "typescript_rootdir_drift",
                "diagnostic_count": len(ts6059),
                "summary": (
                    "TypeScript compilation includes files outside the configured rootDir. "
                    "This usually indicates a monorepo boundary mismatch between the service "
                    "tsconfig and imported workspace packages or testing helpers."
                ),
                "candidate_actions": [
                    "Broaden rootDir or switch to project references for imported "
                    "workspace packages.",
                    "Move test-only includes into a tsconfig that intentionally "
                    "spans the testing subtree.",
                    "Replace deep relative imports that cross workspace boundaries "
                    "with compiled package entrypoints.",
                ],
                "impacted_paths": impacted_paths[:20],
            }
        ]
    grouped = Counter(entry.code or "unclassified" for entry in diagnostics)
    return [
        {
            "problem_class": "generic_compiler_diagnostics",
            "diagnostic_count": len(diagnostics),
            "summary": (
                "Compiler diagnostics were parsed successfully, but no specialized "
                "solution rule matched."
            ),
            "candidate_actions": [
                "Review the top diagnostic clusters and snapshot only the implicated paths.",
                "Feed the bounded evidence bundle into a provider-backed repository "
                "planner when available.",
            ],
            "diagnostic_groups": dict(grouped),
        }
    ]


def _probe_repo_state(repo_path: Path) -> dict[str, Any]:
    if not repository_service._is_git_repository(repo_path):  # type: ignore[attr-defined]
        return {
            "cache_enabled": False,
            "cache_mode": "disabled",
            "reason": "non_git_repository",
            "resolved_revision": None,
            "state_id": None,
            "dirty": None,
            "status_entry_count": None,
            "status_hash": None,
        }
    try:
        resolved_revision = str(
            repository_service._git_command(  # type: ignore[attr-defined]
                ["git", "-C", str(repo_path), "rev-parse", "HEAD"]
            )
        ).strip()
        status_text = str(
            repository_service._git_command(  # type: ignore[attr-defined]
                [
                    "git",
                    "-C",
                    str(repo_path),
                    "status",
                    "--porcelain=v1",
                    "--untracked-files=all",
                    "--ignored=no",
                ],
                timeout=60.0,
            )
        )
    except Exception:  # noqa: BLE001
        return {
            "cache_enabled": False,
            "cache_mode": "disabled",
            "reason": "git_state_unavailable",
            "resolved_revision": None,
            "state_id": None,
            "dirty": None,
            "status_entry_count": None,
            "status_hash": None,
        }
    status_lines = [line.rstrip("\n") for line in status_text.splitlines() if line.strip()]
    return {
        "cache_enabled": True,
        "cache_mode": "git",
        "reason": None,
        "resolved_revision": resolved_revision,
        "state_id": repository_service._hash_payload(  # type: ignore[attr-defined]
            {"resolved_revision": resolved_revision, "status_lines": status_lines}
        ),
        "dirty": bool(status_lines),
        "status_entry_count": len(status_lines),
        "status_hash": repository_service._hash_payload(status_lines),  # type: ignore[attr-defined]
    }


def _probe_prepass_cache_key(
    *,
    repo_state: dict[str, Any],
    focus_paths: list[str],
    diagnostic_command: str | None,
    diagnostic_base_path: str | None,
    include_patterns: list[str],
    exclude_patterns: list[str],
    max_files: int,
    max_file_size_bytes: int,
    max_dependency_depth: int,
    max_connected_files: int,
) -> str | None:
    state_id = repo_state.get("state_id")
    if not state_id:
        return None
    return repository_service._hash_payload(  # type: ignore[attr-defined]
        {
            "schema_version": _PREPASS_CACHE_SCHEMA_VERSION,
            "repo_state_id": state_id,
            "focus_paths": list(focus_paths),
            "diagnostic_command": diagnostic_command,
            "diagnostic_base_path": diagnostic_base_path,
            "include_patterns": list(include_patterns),
            "exclude_patterns": list(exclude_patterns),
            "max_files": max_files,
            "max_file_size_bytes": max_file_size_bytes,
            "max_dependency_depth": max_dependency_depth,
            "max_connected_files": max_connected_files,
        }
    )


def _probe_prepass_cache_path(repository_runtime_root: Path, cache_key: str | None) -> Path | None:
    if not cache_key:
        return None
    return repository_runtime_root / "probe_prepass" / f"{cache_key}.json"


def _load_probe_prepass_cache(cache_path: Path | None) -> dict[str, Any] | None:
    if cache_path is None or not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("schema_version") != _PREPASS_CACHE_SCHEMA_VERSION:
        return None
    return payload


def _store_probe_prepass_cache(cache_path: Path | None, payload: dict[str, Any]) -> None:
    if cache_path is None:
        return
    serialized_payload = json.dumps(payload, indent=2, sort_keys=True)
    temp_path = cache_path.with_suffix(f"{cache_path.suffix}.tmp")
    for _attempt in range(2):
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(serialized_payload, encoding="utf-8")
        try:
            temp_path.replace(cache_path)
            return
        except FileNotFoundError:
            continue


def _compute_probe_prepass(
    *,
    repo_path: Path,
    focus_paths: list[str],
    diagnostic_command: str | None,
    diagnostic_base_path: str | None,
    repository_runtime_root: Path,
    max_files: int,
    max_file_size_bytes: int,
    max_dependency_depth: int,
    max_connected_files: int,
) -> dict[str, Any]:
    started = time.perf_counter_ns()
    repo_state = _probe_repo_state(repo_path)
    cache_key = _probe_prepass_cache_key(
        repo_state=repo_state,
        focus_paths=focus_paths,
        diagnostic_command=diagnostic_command,
        diagnostic_base_path=diagnostic_base_path,
        include_patterns=DEFAULT_INCLUDE_PATTERNS,
        exclude_patterns=DEFAULT_EXCLUDE_PATTERNS,
        max_files=max_files,
        max_file_size_bytes=max_file_size_bytes,
        max_dependency_depth=max_dependency_depth,
        max_connected_files=max_connected_files,
    )
    cache_path = _probe_prepass_cache_path(repository_runtime_root, cache_key)
    cached_payload = _load_probe_prepass_cache(cache_path)
    if cached_payload is not None:
        diagnostics = [
            RepositoryDiagnostic.model_validate(item)
            for item in cached_payload.get("diagnostics", [])
        ]
        return {
            "elapsed_ms": round((time.perf_counter_ns() - started) / 1_000_000.0, 2),
            "cache_status": "hit",
            "cache_enabled": bool(repo_state.get("cache_enabled")),
            "cache_reason": repo_state.get("reason"),
            "cache_key": cache_key,
            "cache_path": str(cache_path) if cache_path else None,
            "repo_state": repo_state,
            "resolved_diagnostic_base_path": Path(
                str(cached_payload["resolved_diagnostic_base_path"])
            ),
            "diagnostic_project_path": cached_payload.get("diagnostic_project_path"),
            "diagnostics": diagnostics,
            "connected_map": cached_payload["connected_map"],
            "fallback_focus_paths": cached_payload["fallback_focus_paths"],
            "config_focus_paths": cached_payload["config_focus_paths"],
            "effective_focus_paths": cached_payload["effective_focus_paths"],
            "inventory": cached_payload["inventory"],
            "candidate_solutions": cached_payload["candidate_solutions"],
            "operational_seed_plan": cached_payload.get("operational_seed_plan"),
            "command": cached_payload.get("command"),
            "command_elapsed_ms": 0.0,
            "cached_command_elapsed_ms": cached_payload.get("command_elapsed_ms"),
            "command_exit_code": cached_payload.get("command_exit_code"),
        }

    command_result = _run_command(repo_path, diagnostic_command) if diagnostic_command else None
    resolved_diagnostic_base_path = _resolve_diagnostic_base_path(
        repo_path,
        diagnostic_command=diagnostic_command,
        diagnostic_base_path=diagnostic_base_path,
    )
    diagnostic_project_path = _resolve_diagnostic_project_path(
        repo_path,
        diagnostic_command=diagnostic_command,
        diagnostic_base_path=resolved_diagnostic_base_path,
    )
    diagnostics = (
        parse_repository_diagnostics(
            repo_path=repo_path,
            output=command_result["combined_output"],
            base_path=resolved_diagnostic_base_path,
        )
        if command_result is not None
        else []
    )
    graph_seed_paths = sorted({item.path for item in diagnostics if item.path})
    operational_seed_plan: dict[str, Any] | None = None
    connected_map_bridge_paths = list(focus_paths)
    if not graph_seed_paths:
        operational_seed_plan = _derive_operational_seed_plan_without_diagnostics(
            repo_path=repo_path,
            focus_paths=focus_paths,
            max_files=max_files,
        )
        graph_seed_paths = list(operational_seed_plan["entrypoint_files"])
        connected_map_bridge_paths = []
    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=graph_seed_paths,
        bridge_paths=connected_map_bridge_paths,
        candidate_file_paths=(
            None
            if operational_seed_plan is None
            else list(operational_seed_plan["candidate_file_paths"])
        ),
        candidate_scope_paths=(
            None
            if operational_seed_plan is None
            else list(operational_seed_plan["support_roots"])
        ),
        enable_reverse_bridging=operational_seed_plan is None,
        include_patterns=DEFAULT_INCLUDE_PATTERNS,
        max_files=max_files,
        max_file_size_bytes=max_file_size_bytes,
        max_dependency_depth=max_dependency_depth,
        max_connected_files=max_connected_files,
    )
    fallback_focus_paths = _focus_paths_from_diagnostics(
        repo_path=repo_path,
        diagnostics=diagnostics,
        explicit_focus_paths=focus_paths,
    )
    config_focus_paths = _candidate_config_focus_paths(
        repo_path=repo_path,
        focus_paths=focus_paths,
        diagnostic_base_path=resolved_diagnostic_base_path,
        diagnostic_project_path=diagnostic_project_path,
    )
    effective_focus_paths = _effective_focus_paths_for_snapshot(
        diagnostics=diagnostics,
        connected_files=list(connected_map["connected_files"]),
        fallback_focus_paths=fallback_focus_paths,
        config_focus_paths=config_focus_paths,
    )
    inventory = _inventory_repo_surface(
        repo_path=repo_path,
        focus_paths=effective_focus_paths,
        include_patterns=DEFAULT_INCLUDE_PATTERNS,
        exclude_dirnames=set(repository_service._DEFAULT_EXCLUDED_PATH_PARTS),
        max_file_size_bytes=max_file_size_bytes,
    )
    candidate_solutions = _candidate_solutions(diagnostics)
    cache_status = (
        "miss_stored" if cache_path is not None else "miss_not_cacheable"
    )
    _store_probe_prepass_cache(
        cache_path,
        {
            "schema_version": _PREPASS_CACHE_SCHEMA_VERSION,
            "created_at": repository_service._utc_now().isoformat(),  # type: ignore[attr-defined]
            "repo_state": repo_state,
            "resolved_diagnostic_base_path": str(resolved_diagnostic_base_path),
            "diagnostic_project_path": diagnostic_project_path,
            "diagnostics": [item.model_dump(mode="json") for item in diagnostics],
            "connected_map": connected_map,
            "fallback_focus_paths": fallback_focus_paths,
            "config_focus_paths": config_focus_paths,
            "effective_focus_paths": effective_focus_paths,
            "inventory": inventory,
            "candidate_solutions": candidate_solutions,
            "operational_seed_plan": operational_seed_plan,
            "command": command_result["command"] if command_result else diagnostic_command,
            "command_elapsed_ms": command_result["elapsed_ms"] if command_result else None,
            "command_exit_code": command_result["exit_code"] if command_result else None,
        },
    )
    return {
        "elapsed_ms": round((time.perf_counter_ns() - started) / 1_000_000.0, 2),
        "cache_status": cache_status,
        "cache_enabled": bool(repo_state.get("cache_enabled")),
        "cache_reason": repo_state.get("reason"),
        "cache_key": cache_key,
        "cache_path": str(cache_path) if cache_path else None,
        "repo_state": repo_state,
        "resolved_diagnostic_base_path": resolved_diagnostic_base_path,
        "diagnostic_project_path": diagnostic_project_path,
        "diagnostics": diagnostics,
        "connected_map": connected_map,
        "fallback_focus_paths": fallback_focus_paths,
        "config_focus_paths": config_focus_paths,
        "effective_focus_paths": effective_focus_paths,
        "inventory": inventory,
        "candidate_solutions": candidate_solutions,
        "operational_seed_plan": operational_seed_plan,
        "command": command_result["command"] if command_result else diagnostic_command,
        "command_elapsed_ms": command_result["elapsed_ms"] if command_result else None,
        "cached_command_elapsed_ms": None,
        "command_exit_code": command_result["exit_code"] if command_result else None,
    }


def _run_command(repo_path: Path, command: str) -> dict[str, Any]:
    started = time.perf_counter_ns()
    completed = subprocess.run(  # noqa: S603
        ["/bin/zsh", "-lc", command],
        cwd=str(repo_path),
        check=False,
        capture_output=True,
        text=True,
    )
    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000.0
    return {
        "command": command,
        "elapsed_ms": round(elapsed_ms, 2),
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "combined_output": "\n".join(
            part for part in (completed.stdout.strip(), completed.stderr.strip()) if part
        ).strip(),
    }


def run_probe(
    *,
    repo_path: Path,
    focus_paths: list[str],
    diagnostic_command: str | None,
    diagnostic_base_path: str | None,
    planner_model: str | None,
    runtime_dir: Path,
    reuse_existing_state: bool,
    max_files: int,
    max_file_size_bytes: int,
    max_total_bytes: int | None,
    max_dependency_depth: int,
    max_connected_files: int,
) -> dict[str, Any]:
    connector = _repository_connector(repo_path)
    snapshot_request = RepositorySnapshotCreateRequest(
        focus_paths=[],
        include_patterns=DEFAULT_INCLUDE_PATTERNS,
        exclude_patterns=DEFAULT_EXCLUDE_PATTERNS,
        max_files=max_files,
        max_file_size_bytes=max_file_size_bytes,
        max_total_bytes=max_total_bytes,
    )
    runtime_dir = runtime_dir.resolve()
    runtime_dir.mkdir(parents=True, exist_ok=True)
    original_runtime_dir = os.environ.get("ALGENTA_RUNTIME_DIR")
    os.environ["ALGENTA_RUNTIME_DIR"] = str(runtime_dir)
    repository_runtime_root = runtime_service._repo_root_dir(
        str(connector.org_id),
        str(connector.id),
    )
    if not reuse_existing_state and repository_runtime_root.exists():
        shutil.rmtree(repository_runtime_root, ignore_errors=True)
    if planner_model:
        original_planner_model = os.environ.get("ALGENTA_REPOSITORY_INTELLIGENCE_MODEL")
        os.environ["ALGENTA_REPOSITORY_INTELLIGENCE_MODEL"] = planner_model
    else:
        original_planner_model = None
    try:
        prepass = _compute_probe_prepass(
            repo_path=repo_path,
            focus_paths=focus_paths,
            diagnostic_command=diagnostic_command,
            diagnostic_base_path=diagnostic_base_path,
            repository_runtime_root=repository_runtime_root,
            max_files=max_files,
            max_file_size_bytes=max_file_size_bytes,
            max_dependency_depth=max_dependency_depth,
            max_connected_files=max_connected_files,
        )
        diagnostics = list(prepass["diagnostics"])
        connected_map = prepass["connected_map"]
        config_focus_paths = list(prepass["config_focus_paths"])
        effective_focus_paths = list(prepass["effective_focus_paths"])
        inventory = prepass["inventory"]
        resolved_diagnostic_base_path = prepass["resolved_diagnostic_base_path"]
        diagnostic_project_path = prepass["diagnostic_project_path"]
        snapshot_request = snapshot_request.model_copy(
            update={"focus_paths": effective_focus_paths}
        )

        started = time.perf_counter_ns()
        cold_snapshot = repository_service.create_repository_snapshot(
            connector=connector,
            request=snapshot_request,
        )
        cold_snapshot_elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000.0

        warm_started = time.perf_counter_ns()
        warm_snapshot = repository_service.create_repository_snapshot(
            connector=connector,
            request=snapshot_request,
        )
        warm_snapshot_elapsed_ms = (time.perf_counter_ns() - warm_started) / 1_000_000.0

        graph_summary = _load_snapshot_graph_summary(
            repository_graph_path=cold_snapshot.repository_graph_artifact.storage_path,
            dependency_graph_path=cold_snapshot.dependency_graph_artifact.storage_path,
            symbol_graph_path=cold_snapshot.symbol_graph_artifact.storage_path,
            seed_files=list(connected_map["seed_files"]),
        )

        triage_result: dict[str, Any] | None = None
        triage_elapsed_ms: float | None = None
        graph_query_result: dict[str, Any] | None = None
        graph_query_elapsed_ms: float | None = None
        decision_plan_result: dict[str, Any] | None = None
        decision_plan_elapsed_ms: float | None = None
        simulation_result: dict[str, Any] | None = None
        simulation_elapsed_ms: float | None = None
        apply_patch_only_result: dict[str, Any] | None = None
        apply_patch_only_elapsed_ms: float | None = None
        planner_status = "not_attempted_no_diagnostics"
        if diagnostics:
            workspace_context = []
            if diagnostic_command:
                workspace_context.append(f"command:{diagnostic_command}")
            if resolved_diagnostic_base_path == repo_path:
                diagnostic_base_path_ref = "."
            else:
                diagnostic_base_path_ref = str(
                    resolved_diagnostic_base_path.relative_to(repo_path)
                ).replace("\\", "/")
            workspace_context.append(
                f"diagnostic_base_path:{diagnostic_base_path_ref}"
            )
            if diagnostic_project_path:
                workspace_context.append(f"tsconfig_project:{diagnostic_project_path}")
            triage_request = RepositoryTriageRequest(
                snapshot_id=cold_snapshot.snapshot_id,
                signals={
                    "issue_text": (
                        f"Read-only repository probe from command: {diagnostic_command}"
                        if diagnostic_command
                        else "Read-only repository probe diagnostics."
                    ),
                    "diagnostics": [item.model_dump(mode="json") for item in diagnostics[:64]],
                    "changed_files": sorted({item.path for item in diagnostics if item.path})[:64],
                    "workspace_context": workspace_context,
                },
                max_evidence_items=16,
                max_snippet_lines=20,
                token_budget=4000,
            )
            triage_started = time.perf_counter_ns()
            triage = repository_service.triage_repository(
                connector=connector,
                request=triage_request,
            )
            triage_elapsed_ms = (time.perf_counter_ns() - triage_started) / 1_000_000.0
            triage_result = triage.model_dump(mode="json")

            graph_seed_file = (
                triage.suspect_files[0]
                if triage.suspect_files
                else (effective_focus_paths[0] if effective_focus_paths else None)
            )
            graph_seed_symbol = None
            if graph_seed_file:
                for item in triage.evidence_items:
                    if item.file_path == graph_seed_file and item.symbol_name:
                        graph_seed_symbol = item.symbol_name
                        break
            if graph_seed_file or graph_seed_symbol:
                graph_query_started = time.perf_counter_ns()
                graph_query = repository_service.query_repository_graph(
                    connector=connector,
                    request=RepositoryGraphQueryRequest(
                        snapshot_id=cold_snapshot.snapshot_id,
                        file_path=graph_seed_file,
                        symbol_name=graph_seed_symbol,
                        direction="both",
                        max_depth=2,
                        max_nodes=96,
                    ),
                )
                graph_query_elapsed_ms = (
                    time.perf_counter_ns() - graph_query_started
                ) / 1_000_000.0
                graph_query_result = graph_query.model_dump(mode="json")

            planner_status = "planning_started"
            try:
                decision_started = time.perf_counter_ns()
                decision_plan = asyncio.run(
                    repository_service.create_repository_decision_plan(
                        connector=connector,
                        request=RepositoryDecisionPlanCreateRequest(
                            snapshot_id=cold_snapshot.snapshot_id,
                            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
                            model=planner_model,
                        ),
                    )
                )
                decision_plan_elapsed_ms = (
                    time.perf_counter_ns() - decision_started
                ) / 1_000_000.0
                decision_plan_result = decision_plan.model_dump(mode="json")
                planner_status = "decision_plan_completed"

                simulation_started = time.perf_counter_ns()
                envelope = asyncio.run(
                    repository_service.simulate_repository_decision(
                        connector=connector,
                        request=RepositorySimulationRequest(
                            snapshot_id=cold_snapshot.snapshot_id,
                            decision_plan_id=decision_plan.decision_plan_id,
                        ),
                    )
                )
                simulation_elapsed_ms = (
                    time.perf_counter_ns() - simulation_started
                ) / 1_000_000.0
                simulation_result = envelope.model_dump(mode="json")
                planner_status = "simulation_completed"

                simulation_id = str(envelope.validated_inputs["simulation_id"])
                apply_started = time.perf_counter_ns()
                apply_patch_only = asyncio.run(
                    repository_service.apply_repository_decision(
                        connector=connector,
                        request=RepositoryApplyRequest(
                            snapshot_id=cold_snapshot.snapshot_id,
                            decision_plan_id=decision_plan.decision_plan_id,
                            simulation_id=simulation_id,
                            mode=RepositoryApplyMode.PATCH_ONLY,
                        ),
                    )
                )
                apply_patch_only_elapsed_ms = (
                    time.perf_counter_ns() - apply_started
                ) / 1_000_000.0
                apply_patch_only_result = apply_patch_only.model_dump(mode="json")
                planner_status = "patch_only_completed"
            except repository_service.RepositoryIntelligenceError as exc:
                planner_status = exc.code
                decision_plan_result = {
                    "error": {
                        "code": exc.code,
                        "message": exc.message,
                        "details": exc.details,
                    }
                }
    finally:
        if original_runtime_dir is None:
            os.environ.pop("ALGENTA_RUNTIME_DIR", None)
        else:
            os.environ["ALGENTA_RUNTIME_DIR"] = original_runtime_dir
        if planner_model:
            if original_planner_model is None:
                os.environ.pop("ALGENTA_REPOSITORY_INTELLIGENCE_MODEL", None)
            else:
                os.environ["ALGENTA_REPOSITORY_INTELLIGENCE_MODEL"] = original_planner_model

    return {
        "repo_path": str(repo_path),
        "read_only": True,
        "runtime": {
            "runtime_dir": str(runtime_dir),
            "repository_runtime_root": str(repository_runtime_root),
            "persisted": True,
            "reuse_existing_state": reuse_existing_state,
        },
        "focus_paths": effective_focus_paths,
        "config_focus_paths": config_focus_paths,
        "diagnostic_base_path": str(resolved_diagnostic_base_path),
        "diagnostic_project_path": diagnostic_project_path,
        "prepass": {
            "elapsed_ms": prepass["elapsed_ms"],
            "cache_status": prepass["cache_status"],
            "cache_enabled": prepass["cache_enabled"],
            "cache_reason": prepass["cache_reason"],
            "cache_key": prepass["cache_key"],
            "cache_path": prepass["cache_path"],
            "repo_state": prepass["repo_state"],
        },
        "inventory": inventory,
        "connected_map": connected_map,
        "operational_seed_plan": prepass.get("operational_seed_plan"),
        "diagnostic_command": None
        if diagnostic_command is None
        else {
            "command": prepass["command"],
            "elapsed_ms": prepass["command_elapsed_ms"],
            "cached_elapsed_ms": prepass["cached_command_elapsed_ms"],
            "exit_code": prepass["command_exit_code"],
            "diagnostic_count": len(diagnostics),
            "cache_status": prepass["cache_status"],
        },
        "snapshot": {
            "elapsed_ms": round(cold_snapshot_elapsed_ms, 2),
            "status": cold_snapshot.status,
            "snapshot_id": cold_snapshot.snapshot_id,
            "file_count": cold_snapshot.file_count,
            "raw_repo_token_estimate": cold_snapshot.raw_repo_token_estimate,
            "language_counts": cold_snapshot.language_counts,
            "resolved_revision": cold_snapshot.resolved_revision,
            "warm_elapsed_ms": round(warm_snapshot_elapsed_ms, 2),
            "warm_status": warm_snapshot.status,
            "graph_summary": graph_summary,
        },
        "triage": None
        if triage_result is None
        else {
            "elapsed_ms": round(float(triage_elapsed_ms or 0.0), 2),
            **triage_result,
        },
        "graph_query": None
        if graph_query_result is None
        else {
            "elapsed_ms": round(float(graph_query_elapsed_ms or 0.0), 2),
            **graph_query_result,
        },
        "decision_plan": None
        if decision_plan_result is None
        else {
            "elapsed_ms": round(float(decision_plan_elapsed_ms or 0.0), 2),
            **decision_plan_result,
        },
        "simulation": None
        if simulation_result is None
        else {
            "elapsed_ms": round(float(simulation_elapsed_ms or 0.0), 2),
            **simulation_result,
        },
        "apply_patch_only": None
        if apply_patch_only_result is None
        else {
            "elapsed_ms": round(float(apply_patch_only_elapsed_ms or 0.0), 2),
            **apply_patch_only_result,
        },
        "candidate_solutions": prepass["candidate_solutions"],
        "planner_status": planner_status,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run a read-only Algenta Repository Intelligence probe against a real local repository."
        )
    )
    parser.add_argument("--repo", type=Path, required=True, help="Path to the local repository.")
    parser.add_argument(
        "--focus-path",
        dest="focus_paths",
        action="append",
        default=[],
        help="Optional relative path or subtree to snapshot before diagnostics narrow further.",
    )
    parser.add_argument(
        "--diagnostic-command",
        type=str,
        default=None,
        help="Optional read-only command to run inside the repository to collect diagnostics.",
    )
    parser.add_argument(
        "--diagnostic-base-path",
        type=str,
        default=None,
        help="Optional repository-relative base path used to resolve relative diagnostics.",
    )
    parser.add_argument(
        "--planner-model",
        type=str,
        default=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,  # type: ignore[attr-defined]
        help=(
            "Repository planner model to use for decision-plan generation. Defaults to the "
            "bounded deterministic local planner."
        ),
    )
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        default=DEFAULT_PERSISTED_RUNTIME_DIR,
        help="Persistent runtime directory used to store repository benchmark artifacts.",
    )
    parser.add_argument(
        "--reuse-existing-state",
        action="store_true",
        help="Reuse existing persisted repository runtime state instead of resetting it first.",
    )
    parser.add_argument("--max-files", type=int, default=6000)
    parser.add_argument("--max-file-size-bytes", type=int, default=350_000)
    parser.add_argument("--max-total-bytes", type=int, default=25_000_000)
    parser.add_argument("--max-dependency-depth", type=int, default=4)
    parser.add_argument("--max-connected-files", type=int, default=256)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    result = run_probe(
        repo_path=args.repo.resolve(),
        focus_paths=list(args.focus_paths),
        diagnostic_command=args.diagnostic_command,
        diagnostic_base_path=args.diagnostic_base_path,
        planner_model=args.planner_model,
        runtime_dir=args.runtime_dir,
        reuse_existing_state=bool(args.reuse_existing_state),
        max_files=int(args.max_files),
        max_file_size_bytes=int(args.max_file_size_bytes),
        max_total_bytes=int(args.max_total_bytes),
        max_dependency_depth=int(args.max_dependency_depth),
        max_connected_files=int(args.max_connected_files),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
