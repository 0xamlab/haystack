from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_language_priority import (
    canonical_repository_language,
)


def _probe_module():
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    return probe_module


def _is_repo_profile_manifest_name(name: str) -> bool:
    probe_module = _probe_module()

    lower_name = name.lower()
    return (
        lower_name in probe_module._REPO_PROFILE_MANIFEST_BASENAMES
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
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

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
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

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
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

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
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

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
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

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
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

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
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

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
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

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
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

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
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

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
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

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
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return set()
    tokens: set[str] = set()
    for part in PurePosixPath(normalized_path).parts:
        lowered_part = part.lower()
        tokens.add(lowered_part)
        tokens.update(token for token in re.split(r"[^a-z0-9]+", lowered_part) if token)
    return tokens


def _is_namespace_style_source_path(path: str) -> bool:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

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
    probe_module = _probe_module()

    matched_tokens = _profile_path_tokens(path) & probe_module._NON_OPERATIONAL_PROFILE_PATH_PARTS
    if matched_tokens and _is_namespace_style_source_path(path):
        matched_tokens = {
            token for token in matched_tokens if token not in probe_module._NAMESPACE_PACKAGE_TOKENS
        }
    return bool(matched_tokens)


def _is_non_operational_profile_path_for_ecosystems(
    path: str,
    *,
    ecosystems: set[str] | None = None,
    repo_path: Path | None = None,
) -> bool:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return False
    matched_tokens = (
        _profile_path_tokens(normalized_path) & probe_module._NON_OPERATIONAL_PROFILE_PATH_PARTS
    )
    if matched_tokens and _is_namespace_style_source_path(normalized_path):
        matched_tokens = {
            token for token in matched_tokens if token not in probe_module._NAMESPACE_PACKAGE_TOKENS
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
        canonical_ecosystems & probe_module._DOCUMENTATION_PRIMARY_ECOSYSTEMS
        and matched_tokens <= probe_module._DOCUMENTATION_OPERATIONAL_PATH_PARTS
    ):
        return False
    if (
        canonical_ecosystems & probe_module._SCENARIO_PRIMARY_ECOSYSTEMS
        and matched_tokens <= probe_module._SCENARIO_OPERATIONAL_PATH_PARTS
    ):
        return False
    return True


def _is_non_operational_project_path(path: str) -> bool:
    probe_module = _probe_module()

    return bool(_profile_path_tokens(path) & probe_module._NON_OPERATIONAL_PROJECT_PATH_PARTS)


def _probe_language_for_path(path: str, *, repo_path: Path | None = None) -> str:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return "unknown"
    text: str | None = None
    candidate_path = Path(normalized_path)
    if repo_path is not None and (
        candidate_path.name.lower() in repository_service.hack_adapter.HACK_CONFIG_BASENAMES
        or candidate_path.suffix.lower() in {".hack", ".hh", ".hhi", ".php"}
        or candidate_path.suffix.lower()
        in {
            "",
            ".as",
            ".al",
            ".apex",
            ".applescript",
            ".auk",
            ".awk",
            ".bas",
            ".cl",
            ".clh",
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
            ".gradle",
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
            ".qs",
            ".sql",
            ".sqlproj",
            ".sass",
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
        or candidate_path.name.lower() in {"qsharp.json", "shadow-cljs.edn"}
        or repository_service.starlark_adapter.has_starlark_path_hints(candidate_path)
    ):
        try:
            text = (repo_path / normalized_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = None
    return repository_service._language_for_path(candidate_path, text=text, repo_root=repo_path)


def _is_profile_entrypoint_noise(path: str) -> bool:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

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
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

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
    if language == "sml" and PurePosixPath(normalized_path).suffix.lower() == ".sig":
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
    return probe_module._is_repo_profile_code_candidate(normalized_path, repo_path=repo_path)
