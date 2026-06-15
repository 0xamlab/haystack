from __future__ import annotations

import re
import os
import stat
from functools import lru_cache
from pathlib import Path, PurePosixPath

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services.repository_language_priority import (
    canonical_repository_language,
)
from benchmarks.repository_intelligence_real_repo_probe_repo_hint_support import (
    clear_ambiguous_as_repo_hint_cache,
    clear_ambiguous_c_header_repo_hint_cache,
    clear_ambiguous_v_repo_hint_cache,
    probe_ambiguous_as_repo_hint_language,
    probe_ambiguous_c_header_repo_hint_language,
    probe_ambiguous_v_repo_hint_language,
)

_CFML_SOURCE_HINT_CACHE_LIMIT = 64
_CFML_SOURCE_HINT_CACHE: dict[str, bool] = {}
_CFML_SOURCE_SUFFIXES = (".cfc", ".cfm", ".cfml")

_COQ_SOURCE_PATH_CACHE_LIMIT = 8192
_COQ_SOURCE_PATH_CACHE: dict[tuple[str, str], bool] = {}
_DELPHI_SOURCE_PATH_CACHE_LIMIT = 8192
_DELPHI_SOURCE_PATH_CACHE: dict[tuple[str, str], bool] = {}
_DELPHI_PROJECT_CONFIG_PATH_CACHE_LIMIT = 8192
_DELPHI_PROJECT_CONFIG_PATH_CACHE: dict[tuple[str, str], bool] = {}
_DELPHI_REPOSITORY_SOURCE_PRESENT_CACHE_LIMIT = 256
_DELPHI_REPOSITORY_SOURCE_PRESENT_CACHE: dict[str, bool] = {}
_DM_PROJECT_CONFIG_PATH_CACHE_LIMIT = 8192
_DM_PROJECT_CONFIG_PATH_CACHE: dict[tuple[str, str], bool] = {}
_EIFFEL_PROJECT_CONFIG_PATH_CACHE_LIMIT = 8192
_EIFFEL_PROJECT_CONFIG_PATH_CACHE: dict[tuple[str, str], bool] = {}
_EIFFEL_REPOSITORY_SOURCE_PRESENT_CACHE_LIMIT = 256
_EIFFEL_REPOSITORY_SOURCE_PRESENT_CACHE: dict[str, bool] = {}

_PROBE_LANGUAGE_FOR_PATH_CACHE_LIMIT = 16384
_PROBE_LANGUAGE_FOR_PATH_CACHE: dict[tuple[str, str, int | None, int | None], str] = {}
_PROBE_LANGUAGE_REPO_HINT_CACHE_LIMIT = 512
_PROBE_LANGUAGE_REPO_HINT_CACHE: dict[tuple[str, str], str] = {}
_REPO_FILE_STAT_CACHE_SCOPE_DEPTH = 0
_REPO_FILE_STAT_MISSING = object()
_REPO_FILE_STAT_CACHE: dict[tuple[str, str], os.stat_result | object] = {}
_REPO_FILE_LSTAT_MISSING = object()
_REPO_FILE_LSTAT_CACHE: dict[tuple[str, str], os.stat_result | object] = {}
_OPERATIONAL_ENTRYPOINT_CANDIDATE_CACHE_LIMIT = 16384
_OPERATIONAL_ENTRYPOINT_CANDIDATE_CACHE: dict[
    tuple[str, str, str, int | None, int | None],
    bool,
] = {}
_NON_OPERATIONAL_PROFILE_PATH_FOR_ECOSYSTEMS_CACHE_LIMIT = 16384
_NON_OPERATIONAL_PROFILE_PATH_FOR_ECOSYSTEMS_CACHE: dict[
    tuple[str, str, tuple[str, ...], int | None, int | None],
    bool,
] = {}
_PROFILE_PATH_TOKENS_CACHE_LIMIT = 16384
_PROFILE_PATH_TOKENS_CACHE: dict[str, frozenset[str]] = {}
_SUFFIXLESS_PROBE_PREFIX_BYTES = 2048
_PREFIX_SAFE_SUFFIXLESS_LANGUAGES = frozenset(
    {"awk", "emacslisp", "fish", "just", "nushell", "shell", "tcl"}
)
_SUFFIXLESS_FISH_RUNTIME_DIRECTORIES = frozenset(
    {"functions", "conf.d", "completions", "themes"}
)
_SUFFIXLESS_SCRIPT_DIRECTORY_NAMES = frozenset(
    {"bin", "script", "scripts", "tool", "tools", "tooling"}
)
_REPO_PROFILE_MANIFEST_SUFFIXES = (
    ".cabal",
    ".gemspec",
    ".podspec",
    ".rockspec",
    ".nimble",
    ".opam",
    ".core",
    ".mlb",
    ".cm",
    ".app.src",
    ".sbt",
    ".csproj",
    ".fsproj",
    ".vbproj",
    ".hxml",
    ".ipkg",
    ".vbp",
    ".yyp",
    ".wsf",
    ".asd",
    ".lvproj",
    ".lvlib",
    ".lvclass",
    ".gpr",
    ".dproj",
    ".lpi",
    ".lpk",
    ".sln",
    ".sqlproj",
    ".dbproj",
    ".psd1",
    ".mqproj",
    ".agda-lib",
    ".gms",
    ".scad",
)
_REPO_PROFILE_JSON_CONFIG_PREFIXES = ("tsconfig.", "jsconfig.")
_CMAKE_CONFIG_BASENAMES = repository_service.cmake_adapter.CMAKE_CONFIG_BASENAMES
_DIRECT_TEXT_SUFFIX_LANGUAGE_MAP = repository_service._DIRECT_TEXT_SUFFIX_LANGUAGE_MAP
# Text suffixes shared by more than one language (or with binary resource files), where the
# suffix alone is not a reliable language signal and the service disambiguates by content.
_AMBIGUOUS_DIRECT_TEXT_SUFFIXES = frozenset(
    {
        ".mo",  # motoko vs modelica
        ".res",  # rescript vs binary (Delphi/Windows) resource
        ".resi",  # rescript interface vs resource
    }
)
_DIRECT_PATH_SUFFIX_LANGUAGE_MAP = {
    ".cljs": "clojurescript",
    ".l5x": "ladder",
    ".purs": "purescript",
    ".rkt": "racket",
    ".rktl": "racket",
    ".scm": "scheme",
    ".sld": "scheme",
    ".sps": "scheme",
    ".ss": "scheme",
    ".tcl": "tcl",
    ".tm": "tcl",
}
_DOCKERFILE_BASENAMES = repository_service.dockerfile_adapter.DOCKERFILE_BASENAMES
_ENTRYPOINT_DEMOTED_LANGUAGES = repository_service._ENTRYPOINT_DEMOTED_LANGUAGES
_HACK_CONFIG_BASENAMES = repository_service.hack_adapter.HACK_CONFIG_BASENAMES
_MOONBIT_CONFIG_BASENAMES = repository_service.moonbit_adapter.MOONBIT_CONFIG_BASENAMES
_NON_CODE_GRAPH_LANGUAGES = repository_service._NON_CODE_GRAPH_LANGUAGES
_RESCRIPT_CONFIG_BASENAMES = repository_service.rescript_adapter.RESCRIPT_CONFIG_BASENAMES
_HAS_ABAPCDS_PATH_HINTS = repository_service.abapcds_adapter.has_abapcds_path_hints
_HAS_AIDL_PATH_HINTS = repository_service.aidl_adapter.has_aidl_path_hints
_HAS_AIKEN_PATH_HINTS = repository_service.aiken_adapter.has_aiken_path_hints
_HAS_ALLOY_PATH_HINTS = repository_service.alloy_adapter.has_alloy_path_hints
_HAS_ANGELSCRIPT_PATH_HINTS = repository_service.angelscript_adapter.has_angelscript_path_hints
_HAS_ANSWER_SET_PROGRAMMING_PATH_HINTS = (
    repository_service.answer_set_programming_adapter.has_answer_set_programming_path_hints
)
_HAS_ANTLR_PATH_HINTS = repository_service.antlr_adapter.has_antlr_path_hints
_HAS_APACHECONF_PATH_HINTS = repository_service.apacheconf_adapter.has_apacheconf_path_hints
_HAS_ASPECTJ_PATH_HINTS = repository_service.aspectj_adapter.has_aspectj_path_hints
_HAS_ASL_PATH_HINTS = repository_service.asl_adapter.has_asl_path_hints
_HAS_ASPNET_PATH_HINTS = repository_service.aspnet_adapter.has_aspnet_path_hints
_HAS_ATS_PATH_HINTS = repository_service.ats_adapter.has_ats_path_hints
_HAS_FREEMARKER_PATH_HINTS = repository_service.freemarker_adapter.has_freemarker_path_hints
_HAS_GRAPHQL_PATH_HINTS = repository_service.graphql_adapter.has_graphql_path_hints
_HAS_MAKO_PATH_HINTS = repository_service.mako_adapter.has_mako_path_hints
_HAS_MAVEN_PATH_HINTS = repository_service.maven_adapter.has_maven_path_hints
_HAS_MOONSCRIPT_PATH_HINTS = repository_service.moonscript_adapter.has_moonscript_path_hints
_HAS_NGINX_PATH_HINTS = repository_service.nginx_adapter.has_nginx_path_hints
_HAS_OCAMLLEX_PATH_HINTS = repository_service.ocamllex_adapter.has_ocamllex_path_hints
_HAS_OCAMLYACC_PATH_HINTS = repository_service.ocamlyacc_adapter.has_ocamlyacc_path_hints
_HAS_ONEC_ENTERPRISE_PATH_HINTS = (
    repository_service.onec_enterprise_adapter.has_onec_enterprise_path_hints
)
_HAS_PKL_PATH_HINTS = repository_service.pkl_adapter.has_pkl_path_hints
_HAS_PLPGSQL_PATH_HINTS = repository_service.plpgsql_adapter.has_plpgsql_path_hints
_HAS_STARLARK_PATH_HINTS = repository_service.starlark_adapter.has_starlark_path_hints
_HAS_TEMPL_PATH_HINTS = repository_service.templ_adapter.has_templ_path_hints
_HAS_THRIFT_PATH_HINTS = repository_service.thrift_adapter.has_thrift_path_hints
_HAS_VCL_PATH_HINTS = repository_service.vcl_adapter.has_vcl_path_hints
_HAS_WEBASSEMBLY_PATH_HINTS = repository_service.webassembly_adapter.has_webassembly_path_hints
_HAS_XTEND_PATH_HINTS = repository_service.xtend_adapter.has_xtend_path_hints


def _probe_module():
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    return probe_module


def _strip_probe_path_wrappers(value: str) -> str:
    normalized_value = str(value or "").strip()
    while (
        len(normalized_value) >= 2
        and normalized_value[0] == normalized_value[-1]
        and normalized_value[0] in {'"', "'"}
    ):
        normalized_value = normalized_value[1:-1].strip()
    return normalized_value


@lru_cache(maxsize=32768)
def _normalized_path_components(
    normalized_path: str,
) -> tuple[PurePosixPath, str, str, str]:
    candidate_path = PurePosixPath(normalized_path)
    return (
        candidate_path,
        candidate_path.name.lower(),
        candidate_path.suffix.lower(),
        candidate_path.parent.name.lower(),
    )


def _repo_cache_key(repo_path: Path) -> str:
    from benchmarks import repository_intelligence_real_repo_probe_collection_support as collection_support

    return collection_support._repo_cache_key(repo_path)


def _read_probe_prefix(candidate_file: Path) -> str | None:
    try:
        with candidate_file.open("rb") as handle:
            return handle.read(_SUFFIXLESS_PROBE_PREFIX_BYTES).decode(
                "utf-8",
                errors="replace",
            )
    except OSError:
        return None


def _suffixless_probe_prefix_text(
    candidate_path: Path,
    *,
    candidate_file: Path,
    candidate_stat: os.stat_result | None,
    repository_service,
) -> str | None:
    basename = candidate_path.name.lower()
    if basename in repository_service.just_adapter.JUSTFILE_BASENAMES:
        return _read_probe_prefix(candidate_file)
    if basename in repository_service.emacslisp_adapter._EMACSLISP_MANIFEST_BASENAMES:
        return _read_probe_prefix(candidate_file)
    # Suffixless Vim config files (vimrc / _vimrc / gvimrc) are vimscript; the service
    # classifies them by content, so the probe must read their text to match it.
    if repository_service.vimscript_adapter.has_vimscript_path_hints(candidate_path):
        return _read_probe_prefix(candidate_file)
    lowered_parent_parts = {part.lower() for part in candidate_path.parts[:-1]}
    has_fish_runtime_context = bool(
        lowered_parent_parts.intersection(_SUFFIXLESS_FISH_RUNTIME_DIRECTORIES)
    )
    if not has_fish_runtime_context and (
        candidate_stat is None
        or (
            not lowered_parent_parts.intersection(_SUFFIXLESS_SCRIPT_DIRECTORY_NAMES)
            and not (candidate_stat.st_mode & stat.S_IXUSR)
            and not (candidate_stat.st_mode & stat.S_IXGRP)
            and not (candidate_stat.st_mode & stat.S_IXOTH)
        )
    ):
        return None
    prefix_text = _read_probe_prefix(candidate_file)
    if not prefix_text:
        return None
    if has_fish_runtime_context:
        return prefix_text
    if prefix_text.startswith("#!"):
        return prefix_text
    if repository_service.emacslisp_adapter._EMACSLISP_MARKER_RE.search(prefix_text):
        return prefix_text
    return prefix_text if repository_service.awk_adapter.is_probable_awk_source(
        path=candidate_path,
        text=prefix_text,
    ) else None


def _suffixless_path_requires_full_text_probe(
    candidate_path: Path,
    *,
    candidate_file: Path,
    candidate_stat: os.stat_result | None,
    repository_service,
) -> bool:
    return (
        _suffixless_probe_prefix_text(
            candidate_path,
            candidate_file=candidate_file,
            candidate_stat=candidate_stat,
            repository_service=repository_service,
        )
        is not None
    )


def _probe_suffixless_language_from_prefix(
    candidate_path: Path,
    *,
    prefix_text: str,
    repo_path: Path | None,
) -> str:
    language = repository_service._language_for_path(
        candidate_path,
        text=prefix_text,
        repo_root=repo_path,
    )
    if language in _PREFIX_SAFE_SUFFIXLESS_LANGUAGES:
        return language
    return "unknown"


def clear_delphi_project_config_path_cache() -> None:
    _DELPHI_SOURCE_PATH_CACHE.clear()
    _DELPHI_PROJECT_CONFIG_PATH_CACHE.clear()
    _DELPHI_REPOSITORY_SOURCE_PRESENT_CACHE.clear()


def clear_coq_source_path_cache() -> None:
    _COQ_SOURCE_PATH_CACHE.clear()


def clear_dm_project_config_path_cache() -> None:
    _DM_PROJECT_CONFIG_PATH_CACHE.clear()


def clear_eiffel_project_config_path_cache() -> None:
    _EIFFEL_PROJECT_CONFIG_PATH_CACHE.clear()
    _EIFFEL_REPOSITORY_SOURCE_PRESENT_CACHE.clear()


def clear_probe_language_for_path_cache() -> None:
    _CFML_SOURCE_HINT_CACHE.clear()
    _PROBE_LANGUAGE_FOR_PATH_CACHE.clear()
    _PROBE_LANGUAGE_REPO_HINT_CACHE.clear()
    _REPO_FILE_STAT_CACHE.clear()
    _REPO_FILE_LSTAT_CACHE.clear()
    _OPERATIONAL_ENTRYPOINT_CANDIDATE_CACHE.clear()
    _NON_OPERATIONAL_PROFILE_PATH_FOR_ECOSYSTEMS_CACHE.clear()
    _PROFILE_PATH_TOKENS_CACHE.clear()
    clear_ambiguous_as_repo_hint_cache()
    clear_ambiguous_c_header_repo_hint_cache()
    clear_ambiguous_v_repo_hint_cache()
    clear_coq_source_path_cache()
    clear_delphi_project_config_path_cache()
    clear_dm_project_config_path_cache()
    clear_eiffel_project_config_path_cache()


def delphi_project_config_path_cache_size() -> int:
    return len(_DELPHI_PROJECT_CONFIG_PATH_CACHE)


def begin_repo_file_stat_cache_scope() -> None:
    global _REPO_FILE_STAT_CACHE_SCOPE_DEPTH

    if _REPO_FILE_STAT_CACHE_SCOPE_DEPTH == 0:
        _REPO_FILE_STAT_CACHE.clear()
        _REPO_FILE_LSTAT_CACHE.clear()
    _REPO_FILE_STAT_CACHE_SCOPE_DEPTH += 1


def end_repo_file_stat_cache_scope() -> None:
    global _REPO_FILE_STAT_CACHE_SCOPE_DEPTH

    if _REPO_FILE_STAT_CACHE_SCOPE_DEPTH <= 0:
        _REPO_FILE_STAT_CACHE.clear()
        _REPO_FILE_LSTAT_CACHE.clear()
        _REPO_FILE_STAT_CACHE_SCOPE_DEPTH = 0
        return
    _REPO_FILE_STAT_CACHE_SCOPE_DEPTH -= 1
    if _REPO_FILE_STAT_CACHE_SCOPE_DEPTH == 0:
        _REPO_FILE_STAT_CACHE.clear()
        _REPO_FILE_LSTAT_CACHE.clear()


def _repo_file_stat(
    repo_path: Path,
    normalized_path: str,
) -> os.stat_result | None:
    candidate_path = repo_path / normalized_path
    if _REPO_FILE_STAT_CACHE_SCOPE_DEPTH <= 0:
        try:
            return candidate_path.stat()
        except OSError:
            return None

    cache_key = (str(repo_path), normalized_path)
    cached_result = _REPO_FILE_STAT_CACHE.get(cache_key)
    if cached_result is _REPO_FILE_STAT_MISSING:
        return None
    if cached_result is not None:
        return cached_result if isinstance(cached_result, os.stat_result) else None
    try:
        candidate_stat = candidate_path.stat()
    except OSError:
        _REPO_FILE_STAT_CACHE[cache_key] = _REPO_FILE_STAT_MISSING
        return None
    _REPO_FILE_STAT_CACHE[cache_key] = candidate_stat
    return candidate_stat


def _repo_file_lstat(
    repo_path: Path,
    normalized_path: str,
) -> os.stat_result | None:
    candidate_path = repo_path / normalized_path
    if _REPO_FILE_STAT_CACHE_SCOPE_DEPTH <= 0:
        try:
            return candidate_path.lstat()
        except OSError:
            return None

    cache_key = (str(repo_path), normalized_path)
    cached_result = _REPO_FILE_LSTAT_CACHE.get(cache_key)
    if cached_result is _REPO_FILE_LSTAT_MISSING:
        return None
    if cached_result is not None:
        return cached_result if isinstance(cached_result, os.stat_result) else None
    try:
        candidate_stat = candidate_path.lstat()
    except OSError:
        _REPO_FILE_LSTAT_CACHE[cache_key] = _REPO_FILE_LSTAT_MISSING
        return None
    _REPO_FILE_LSTAT_CACHE[cache_key] = candidate_stat
    return candidate_stat


def _repo_path_is_regular_file(
    repo_path: Path,
    normalized_path: str,
) -> bool:
    candidate_stat = _repo_file_stat(repo_path, normalized_path)
    return candidate_stat is not None and stat.S_ISREG(candidate_stat.st_mode)


def _repo_path_is_symlink(
    repo_path: Path,
    normalized_path: str,
) -> bool:
    candidate_lstat = _repo_file_lstat(repo_path, normalized_path)
    return candidate_lstat is not None and stat.S_ISLNK(candidate_lstat.st_mode)


def _is_delphi_source_path(repo_path: Path, relative_path: str) -> bool:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    normalized_path = repository_service._normalize_repository_relative_path(relative_path)
    if not normalized_path:
        return False
    cache_key = (_repo_cache_key(repo_path), normalized_path)
    cached_result = _DELPHI_SOURCE_PATH_CACHE.get(cache_key)
    if cached_result is not None:
        return cached_result

    def _remember(result: bool) -> bool:
        if len(_DELPHI_SOURCE_PATH_CACHE) >= _DELPHI_SOURCE_PATH_CACHE_LIMIT:
            oldest_key = next(iter(_DELPHI_SOURCE_PATH_CACHE))
            _DELPHI_SOURCE_PATH_CACHE.pop(oldest_key, None)
        _DELPHI_SOURCE_PATH_CACHE[cache_key] = result
        return result

    normalized_candidate_path = Path(normalized_path)
    if not repository_service.delphi_adapter.has_delphi_path_hints(normalized_candidate_path):
        return _remember(False)
    if not _repo_path_is_regular_file(repo_path, normalized_path) or _repo_path_is_symlink(
        repo_path, normalized_path
    ):
        return _remember(False)
    try:
        text = (repo_path / normalized_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return _remember(False)
    return _remember(
        repository_service.delphi_adapter.is_probable_delphi_source(
            path=normalized_candidate_path,
            text=text,
        )
    )


def _is_coq_source_path(repo_path: Path, relative_path: str) -> bool:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    normalized_path = repository_service._normalize_repository_relative_path(relative_path)
    if not normalized_path:
        return False
    cache_key = (_repo_cache_key(repo_path), normalized_path)
    cached_result = _COQ_SOURCE_PATH_CACHE.get(cache_key)
    if cached_result is not None:
        return cached_result

    def _remember(result: bool) -> bool:
        if len(_COQ_SOURCE_PATH_CACHE) >= _COQ_SOURCE_PATH_CACHE_LIMIT:
            oldest_key = next(iter(_COQ_SOURCE_PATH_CACHE))
            _COQ_SOURCE_PATH_CACHE.pop(oldest_key, None)
        _COQ_SOURCE_PATH_CACHE[cache_key] = result
        return result

    normalized_candidate_path = Path(normalized_path)
    if normalized_candidate_path.suffix.lower() != ".v":
        return _remember(False)
    if not repository_service.coq_adapter.has_coq_path_hints(normalized_candidate_path):
        return _remember(False)
    if not _repo_path_is_regular_file(repo_path, normalized_path) or _repo_path_is_symlink(
        repo_path, normalized_path
    ):
        return _remember(False)
    try:
        text = (repo_path / normalized_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return _remember(False)
    return _remember(
        repository_service.coq_adapter.is_probable_coq_source(
            path=normalized_candidate_path,
            text=text,
        )
    )


def _repo_has_delphi_source(repo_path: Path) -> bool:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _git_repo_relative_files = probe_module._git_repo_relative_files

    cache_key = _repo_cache_key(repo_path)
    cached_result = _DELPHI_REPOSITORY_SOURCE_PRESENT_CACHE.get(cache_key)
    if cached_result is not None:
        return cached_result

    def _remember(result: bool) -> bool:
        if len(_DELPHI_REPOSITORY_SOURCE_PRESENT_CACHE) >= (
            _DELPHI_REPOSITORY_SOURCE_PRESENT_CACHE_LIMIT
        ):
            oldest_key = next(iter(_DELPHI_REPOSITORY_SOURCE_PRESENT_CACHE))
            _DELPHI_REPOSITORY_SOURCE_PRESENT_CACHE.pop(oldest_key, None)
        _DELPHI_REPOSITORY_SOURCE_PRESENT_CACHE[cache_key] = result
        return result

    source_suffixes = {".dpr", ".dpk", ".pas"}
    git_relative_files = _git_repo_relative_files(repo_path)
    if git_relative_files is not None:
        for relative_source_path in git_relative_files:
            if PurePosixPath(relative_source_path).suffix.lower() not in source_suffixes:
                continue
            if (
                repository_service._is_test_path(relative_source_path)
                or _is_non_operational_profile_path(relative_source_path)
            ):
                continue
            if _is_delphi_source_path(repo_path, relative_source_path):
                return _remember(True)
        return _remember(False)

    for suffix in ("*.dpr", "*.dpk", "*.pas"):
        for source_path in sorted(repo_path.rglob(suffix)):
            if not source_path.is_file() or source_path.is_symlink():
                continue
            relative_source_path = repository_service._normalize_repository_relative_path(
                str(source_path.relative_to(repo_path))
            )
            if (
                not relative_source_path
                or repository_service._is_test_path(relative_source_path)
                or _is_non_operational_profile_path(relative_source_path)
            ):
                continue
            if _is_delphi_source_path(repo_path, relative_source_path):
                return _remember(True)
    return _remember(False)


def _repo_has_eiffel_source(repo_path: Path) -> bool:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _git_repo_relative_files = probe_module._git_repo_relative_files

    cache_key = _repo_cache_key(repo_path)
    cached_result = _EIFFEL_REPOSITORY_SOURCE_PRESENT_CACHE.get(cache_key)
    if cached_result is not None:
        return cached_result

    def _remember(result: bool) -> bool:
        if len(_EIFFEL_REPOSITORY_SOURCE_PRESENT_CACHE) >= (
            _EIFFEL_REPOSITORY_SOURCE_PRESENT_CACHE_LIMIT
        ):
            oldest_key = next(iter(_EIFFEL_REPOSITORY_SOURCE_PRESENT_CACHE))
            _EIFFEL_REPOSITORY_SOURCE_PRESENT_CACHE.pop(oldest_key, None)
        _EIFFEL_REPOSITORY_SOURCE_PRESENT_CACHE[cache_key] = result
        return result

    git_relative_files = _git_repo_relative_files(repo_path)
    if git_relative_files is not None:
        for relative_source_path in git_relative_files:
            if PurePosixPath(relative_source_path).suffix.lower() != ".e":
                continue
            if (
                repository_service._is_test_path(relative_source_path)
                or _is_non_operational_profile_path(relative_source_path)
            ):
                continue
            if _probe_language_for_path(relative_source_path, repo_path=repo_path) == "eiffel":
                return _remember(True)
        return _remember(False)

    for source_path in sorted(repo_path.rglob("*.e")):
        if not source_path.is_file() or source_path.is_symlink():
            continue
        relative_source_path = repository_service._normalize_repository_relative_path(
            str(source_path.relative_to(repo_path))
        )
        if (
            not relative_source_path
            or repository_service._is_test_path(relative_source_path)
            or _is_non_operational_profile_path(relative_source_path)
        ):
            continue
        if _probe_language_for_path(relative_source_path, repo_path=repo_path) == "eiffel":
            return _remember(True)
    return _remember(False)


@lru_cache(maxsize=8192)
def _is_repo_profile_manifest_name(name: str) -> bool:
    probe_module = _probe_module()

    lower_name = name.lower()
    if (
        lower_name in probe_module._REPO_PROFILE_MANIFEST_BASENAMES
        or lower_name == "pkgindex.tcl"
    ):
        return True
    if lower_name.endswith(".json") and lower_name.startswith(
        _REPO_PROFILE_JSON_CONFIG_PREFIXES
    ):
        return True
    return lower_name.endswith(_REPO_PROFILE_MANIFEST_SUFFIXES)


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
    normalized_repo_path = _repo_cache_key(repo_path)
    cached_repo_has_cfml_sources = _CFML_SOURCE_HINT_CACHE.get(normalized_repo_path)
    if cached_repo_has_cfml_sources is None:
        from benchmarks import repository_intelligence_real_repo_probe_collection_support as collection_support

        has_cached_repo_relative_files, cached_repo_relative_files = (
            collection_support._cached_git_repo_relative_files(repo_path)
        )
        repo_relative_files = (
            cached_repo_relative_files
            if has_cached_repo_relative_files
            else collection_support._git_repo_relative_files(repo_path)
        )
        excluded_dirnames = set(repository_service._DEFAULT_EXCLUDED_PATH_PARTS)
        repo_has_cfml_sources = False
        if repo_relative_files is not None:
            for relative_source_path in repo_relative_files:
                if not relative_source_path.lower().endswith(_CFML_SOURCE_SUFFIXES):
                    continue
                if (
                    repository_service._is_test_path(relative_source_path)
                    or _is_non_operational_profile_path(relative_source_path)
                ):
                    continue
                repo_has_cfml_sources = True
                break
        else:
            for dirpath, dirnames, filenames in os.walk(repo_path):
                dirnames[:] = [name for name in dirnames if name not in excluded_dirnames]
                for filename in filenames:
                    if not filename.lower().endswith(_CFML_SOURCE_SUFFIXES):
                        continue
                    source_path = Path(dirpath) / filename
                    if not source_path.is_file() or source_path.is_symlink():
                        continue
                    relative_source_path = repository_service._normalize_repository_relative_path(
                        str(source_path.relative_to(repo_path))
                    )
                    if (
                        not relative_source_path
                        or repository_service._is_test_path(relative_source_path)
                        or _is_non_operational_profile_path(relative_source_path)
                    ):
                        continue
                    repo_has_cfml_sources = True
                    break
                if repo_has_cfml_sources:
                    break
        if len(_CFML_SOURCE_HINT_CACHE) >= _CFML_SOURCE_HINT_CACHE_LIMIT:
            oldest_key = next(iter(_CFML_SOURCE_HINT_CACHE))
            _CFML_SOURCE_HINT_CACHE.pop(oldest_key, None)
        _CFML_SOURCE_HINT_CACHE[normalized_repo_path] = repo_has_cfml_sources
        cached_repo_has_cfml_sources = repo_has_cfml_sources
    if not cached_repo_has_cfml_sources:
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
    project_root_relative_path = repository_service._normalize_repository_relative_path(
        str(project_root.relative_to(repo_path))
    )
    from benchmarks import repository_intelligence_real_repo_probe_collection_support as collection_support

    has_cached_repo_relative_files, cached_repo_relative_files = (
        collection_support._cached_git_repo_relative_files(repo_path)
    )
    repo_relative_files = (
        cached_repo_relative_files
        if has_cached_repo_relative_files
        else collection_support._git_repo_relative_files(repo_path)
    )
    seen_paths: set[str] = set()
    if repo_relative_files is not None:
        prioritized_relative_files = repo_relative_files
        if project_root_relative_path not in {"", "."}:
            project_root_prefix = f"{project_root_relative_path}/"
            project_relative_files = [
                relative_source_path
                for relative_source_path in repo_relative_files
                if relative_source_path.startswith(project_root_prefix)
            ]
            prioritized_relative_files = project_relative_files + repo_relative_files
        for relative_source_path in prioritized_relative_files:
            if not relative_source_path.lower().endswith(_CFML_SOURCE_SUFFIXES):
                continue
            if (
                relative_source_path in seen_paths
                or repository_service._is_test_path(relative_source_path)
                or _is_non_operational_profile_path(relative_source_path)
            ):
                continue
            seen_paths.add(relative_source_path)
            if _probe_language_for_path(relative_source_path, repo_path=repo_path) == "cfml":
                return True
        return False
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
    cache_key = (_repo_cache_key(repo_path), normalized_path)
    cached_result = _DELPHI_PROJECT_CONFIG_PATH_CACHE.get(cache_key)
    if cached_result is not None:
        return cached_result

    def _remember(result: bool) -> bool:
        if len(_DELPHI_PROJECT_CONFIG_PATH_CACHE) >= _DELPHI_PROJECT_CONFIG_PATH_CACHE_LIMIT:
            oldest_key = next(iter(_DELPHI_PROJECT_CONFIG_PATH_CACHE))
            _DELPHI_PROJECT_CONFIG_PATH_CACHE.pop(oldest_key, None)
        _DELPHI_PROJECT_CONFIG_PATH_CACHE[cache_key] = result
        return result

    path = PurePosixPath(normalized_path)
    if path.suffix.lower() != ".dproj":
        return _remember(False)
    if (
        repository_service._is_test_path(normalized_path)
        or _is_non_operational_profile_path(normalized_path)
    ):
        return _remember(False)
    candidate = repo_path / normalized_path
    if not candidate.is_file() or candidate.is_symlink():
        return _remember(False)
    try:
        text = candidate.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return _remember(False)
    if not repository_service.delphi_adapter.is_probable_delphi_source(
        path=Path(normalized_path),
        text=text,
    ):
        return _remember(False)
    sibling_entrypoint_paths: set[str] = set()
    project_dir = path.parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    stem = path.stem
    sibling_entrypoint_paths.update(
        {
            f"{root_prefix}{stem}.dpr",
            f"{root_prefix}{stem}.dpk",
            f"{root_prefix}{stem}.pas",
            f"{root_prefix}main.dpr",
            f"{root_prefix}main.pas",
        }
    )
    for match in re.finditer(
        r"<MainSource>\s*(?P<path>[^<]+?)\s*</MainSource>",
        text,
        flags=re.IGNORECASE,
    ):
        resolved_path = repository_service._normalize_repository_relative_path(
            str(project_dir / str(match.group("path") or "").strip())
        )
        if resolved_path:
            sibling_entrypoint_paths.add(resolved_path)
    for sibling_path in sorted(sibling_entrypoint_paths):
        normalized_sibling_path = repository_service._normalize_repository_relative_path(
            sibling_path
        )
        if (
            not normalized_sibling_path
            or normalized_sibling_path == normalized_path
            or repository_service._is_test_path(normalized_sibling_path)
            or _is_non_operational_profile_path(normalized_sibling_path)
        ):
            continue
        if _is_delphi_source_path(repo_path, normalized_sibling_path):
            return _remember(True)
    return _remember(_repo_has_delphi_source(repo_path))


def _is_eiffel_project_config_path(repo_path: Path, relative_path: str) -> bool:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    normalized_path = repository_service._normalize_repository_relative_path(relative_path)
    if not normalized_path:
        return False
    cache_key = (_repo_cache_key(repo_path), normalized_path)
    cached_result = _EIFFEL_PROJECT_CONFIG_PATH_CACHE.get(cache_key)
    if cached_result is not None:
        return cached_result

    def _remember(result: bool) -> bool:
        if len(_EIFFEL_PROJECT_CONFIG_PATH_CACHE) >= _EIFFEL_PROJECT_CONFIG_PATH_CACHE_LIMIT:
            oldest_key = next(iter(_EIFFEL_PROJECT_CONFIG_PATH_CACHE))
            _EIFFEL_PROJECT_CONFIG_PATH_CACHE.pop(oldest_key, None)
        _EIFFEL_PROJECT_CONFIG_PATH_CACHE[cache_key] = result
        return result

    path = PurePosixPath(normalized_path)
    if path.suffix.lower() not in {".ecf", ".ace"}:
        return _remember(False)
    candidate = repo_path / normalized_path
    if not candidate.is_file() or candidate.is_symlink():
        return _remember(False)
    try:
        text = candidate.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return _remember(False)
    if not repository_service.eiffel_adapter.is_probable_eiffel_source(
        path=Path(normalized_path),
        text=text,
    ):
        return _remember(False)
    return _remember(_repo_has_eiffel_source(repo_path))


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


def _is_dm_project_config_path(repo_path: Path, relative_path: str) -> bool:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    normalized_path = repository_service._normalize_repository_relative_path(relative_path)
    if not normalized_path:
        return False
    cache_key = (_repo_cache_key(repo_path), normalized_path)
    cached_result = _DM_PROJECT_CONFIG_PATH_CACHE.get(cache_key)
    if cached_result is not None:
        return cached_result

    def _remember(result: bool) -> bool:
        if len(_DM_PROJECT_CONFIG_PATH_CACHE) >= _DM_PROJECT_CONFIG_PATH_CACHE_LIMIT:
            oldest_key = next(iter(_DM_PROJECT_CONFIG_PATH_CACHE))
            _DM_PROJECT_CONFIG_PATH_CACHE.pop(oldest_key, None)
        _DM_PROJECT_CONFIG_PATH_CACHE[cache_key] = result
        return result

    if PurePosixPath(normalized_path).suffix.lower() != ".dme":
        return _remember(False)
    candidate = repo_path / normalized_path
    if not candidate.is_file() or candidate.is_symlink():
        return _remember(False)
    try:
        text = candidate.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return _remember(False)
    stripped_text = repository_service.dm_adapter.strip_comments(text)
    return _remember(repository_service.dm_adapter.is_probable_dm_source(
        path=Path(normalized_path),
        text=text,
        stripped_text=stripped_text,
    ))


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
    raw_path = str(path)
    cached_tokens = _PROFILE_PATH_TOKENS_CACHE.get(raw_path)
    if cached_tokens is not None:
        return set(cached_tokens)

    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    normalized_path = repository_service._normalize_repository_relative_path(raw_path)
    if not normalized_path:
        return set()
    tokens: set[str] = set()
    for part in PurePosixPath(normalized_path).parts:
        lowered_part = part.lower()
        tokens.add(lowered_part)
        tokens.update(token for token in re.split(r"[^a-z0-9]+", lowered_part) if token)
    frozen_tokens = frozenset(tokens)
    if len(_PROFILE_PATH_TOKENS_CACHE) >= _PROFILE_PATH_TOKENS_CACHE_LIMIT:
        oldest_key = next(iter(_PROFILE_PATH_TOKENS_CACHE))
        _PROFILE_PATH_TOKENS_CACHE.pop(oldest_key, None)
    _PROFILE_PATH_TOKENS_CACHE[raw_path] = frozen_tokens
    return set(frozen_tokens)


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
    canonical_ecosystems = tuple(
        sorted(
            canonical_repository_language(ecosystem)
            for ecosystem in (ecosystems or set())
            if canonical_repository_language(ecosystem)
        )
    )
    cache_key = ("", normalized_path, canonical_ecosystems, None, None)
    if repo_path is not None:
        candidate_stat = _repo_file_stat(repo_path, normalized_path)
        if candidate_stat is not None:
            cache_key = (
                str(repo_path),
                normalized_path,
                canonical_ecosystems,
                candidate_stat.st_mtime_ns,
                candidate_stat.st_size,
            )
        else:
            cache_key = (
                str(repo_path),
                normalized_path,
                canonical_ecosystems,
                None,
                None,
            )
    cached_result = _NON_OPERATIONAL_PROFILE_PATH_FOR_ECOSYSTEMS_CACHE.get(cache_key)
    if cached_result is not None:
        return cached_result

    def _remember(result: bool) -> bool:
        if len(_NON_OPERATIONAL_PROFILE_PATH_FOR_ECOSYSTEMS_CACHE) >= (
            _NON_OPERATIONAL_PROFILE_PATH_FOR_ECOSYSTEMS_CACHE_LIMIT
        ):
            oldest_key = next(iter(_NON_OPERATIONAL_PROFILE_PATH_FOR_ECOSYSTEMS_CACHE))
            _NON_OPERATIONAL_PROFILE_PATH_FOR_ECOSYSTEMS_CACHE.pop(oldest_key, None)
        _NON_OPERATIONAL_PROFILE_PATH_FOR_ECOSYSTEMS_CACHE[cache_key] = result
        return result

    matched_tokens = (
        _profile_path_tokens(normalized_path) & probe_module._NON_OPERATIONAL_PROFILE_PATH_PARTS
    )
    if matched_tokens and _is_namespace_style_source_path(normalized_path):
        matched_tokens = {
            token for token in matched_tokens if token not in probe_module._NAMESPACE_PACKAGE_TOKENS
        }
    if not matched_tokens:
        return _remember(False)
    canonical_ecosystem_set = set(canonical_ecosystems)
    if not canonical_ecosystem_set and repo_path is not None:
        detected_language = canonical_repository_language(
            _probe_language_for_path(normalized_path, repo_path=repo_path)
        )
        if detected_language:
            canonical_ecosystem_set.add(detected_language)
    if (
        canonical_ecosystem_set & probe_module._DOCUMENTATION_PRIMARY_ECOSYSTEMS
        and matched_tokens <= probe_module._DOCUMENTATION_OPERATIONAL_PATH_PARTS
    ):
        return _remember(False)
    if (
        canonical_ecosystem_set & probe_module._EXAMPLE_PRIMARY_ECOSYSTEMS
        and matched_tokens <= probe_module._EXAMPLE_OPERATIONAL_PATH_PARTS
    ):
        return _remember(False)
    if "webassembly" in canonical_ecosystem_set and matched_tokens <= {
        "core",
        "spec",
        "specs",
        "suite",
        "suites",
        "test",
        "tests",
    }:
        return _remember(False)
    if (
        canonical_ecosystem_set & probe_module._SCENARIO_PRIMARY_ECOSYSTEMS
        and matched_tokens <= probe_module._SCENARIO_OPERATIONAL_PATH_PARTS
    ):
        return _remember(False)
    return _remember(True)


def _is_non_operational_project_path(path: str) -> bool:
    probe_module = _probe_module()

    return bool(_profile_path_tokens(path) & probe_module._NON_OPERATIONAL_PROJECT_PATH_PARTS)


def _direct_probe_language_hint(*, basename: str, suffix: str) -> str | None:
    if basename in _CMAKE_CONFIG_BASENAMES or suffix == ".cmake":
        return "cmake"
    if basename in _DOCKERFILE_BASENAMES:
        return "dockerfile"
    if basename == "meson.build":
        return "meson"
    if basename == "build.zig":
        return "zig"
    if basename == "package.swift":
        return "swift"
    if suffix in _DIRECT_PATH_SUFFIX_LANGUAGE_MAP:
        return _DIRECT_PATH_SUFFIX_LANGUAGE_MAP[suffix]
    # Suffixes shared by multiple languages (or with binary resources) must be disambiguated
    # by content, not by the suffix alone — the service runs a content check for these and
    # returns ``unknown`` for non-matching content. Skipping the direct hint here defers to
    # the content-aware probe path so e.g. a motoko ``.mo`` is not pinned to modelica and a
    # Delphi ``.res`` resource is not pinned to rescript.
    if suffix in _AMBIGUOUS_DIRECT_TEXT_SUFFIXES:
        return None
    if suffix in _DIRECT_TEXT_SUFFIX_LANGUAGE_MAP:
        return _DIRECT_TEXT_SUFFIX_LANGUAGE_MAP[suffix]
    return None


def _structural_direct_probe_language_hint(*, basename: str, suffix: str) -> str | None:
    """Direct hint limited to *structural* manifests/suffixes (no text-suffix shortcuts).

    Used where a hint must be authoritative enough to skip the content-aware probe entirely
    (e.g. ``.l5x`` ladder, ``CMakeLists.txt``). Text suffixes (``_DIRECT_TEXT_SUFFIX_LANGUAGE_MAP``,
    e.g. ``.typ``) still defer to the content-aware probe, so callers that observe per-file
    language resolution keep doing so for those suffixes.
    """
    if basename in _CMAKE_CONFIG_BASENAMES or suffix == ".cmake":
        return "cmake"
    if basename in _DOCKERFILE_BASENAMES:
        return "dockerfile"
    if basename == "meson.build":
        return "meson"
    if basename == "build.zig":
        return "zig"
    if basename == "package.swift":
        return "swift"
    if suffix in _DIRECT_PATH_SUFFIX_LANGUAGE_MAP:
        return _DIRECT_PATH_SUFFIX_LANGUAGE_MAP[suffix]
    return None


def _cache_probe_language_for_path(
    cache_key: tuple[str, str, int | None, int | None] | None,
    language: str,
) -> str:
    if cache_key is not None:
        if len(_PROBE_LANGUAGE_FOR_PATH_CACHE) >= _PROBE_LANGUAGE_FOR_PATH_CACHE_LIMIT:
            oldest_key = next(iter(_PROBE_LANGUAGE_FOR_PATH_CACHE))
            _PROBE_LANGUAGE_FOR_PATH_CACHE.pop(oldest_key, None)
        _PROBE_LANGUAGE_FOR_PATH_CACHE[cache_key] = language
    return language


def _probe_language_for_path(path: str, *, repo_path: Path | None = None) -> str:
    probe_module = _probe_module()

    normalized_path = repository_service._normalize_repository_relative_path(path)
    stripped_path = _strip_probe_path_wrappers(normalized_path)
    if stripped_path != normalized_path:
        normalized_path = repository_service._normalize_repository_relative_path(stripped_path)
    if not normalized_path:
        return "unknown"
    candidate_pure_path, candidate_basename, candidate_suffix, _parent_basename = (
        _normalized_path_components(normalized_path)
    )
    candidate_path = Path(candidate_pure_path)
    text: str | None = None
    suffixless_probe_prefix_text: str | None = None
    candidate_file: Path | None = None
    candidate_stat: os.stat_result | None = None
    cache_key: tuple[str, str, int | None, int | None] | None = None
    direct_language_hint = _direct_probe_language_hint(
        basename=candidate_basename,
        suffix=candidate_suffix,
    )
    if direct_language_hint is not None:
        return direct_language_hint
    if repo_path is not None:
        candidate_file = repo_path / normalized_path
        candidate_stat = _repo_file_stat(repo_path, normalized_path)
        if candidate_stat is not None:
            cache_key = (
                str(repo_path),
                normalized_path,
                candidate_stat.st_mtime_ns,
                candidate_stat.st_size,
            )
        else:
            cache_key = (str(repo_path), normalized_path, None, None)
        cached_language = _PROBE_LANGUAGE_FOR_PATH_CACHE.get(cache_key)
        if cached_language is not None:
            return cached_language
    repo_hint_language = _probe_language_repo_hint(
        normalized_path,
        repo_path=repo_path,
    )
    if repo_hint_language != "unknown":
        return _cache_probe_language_for_path(cache_key, repo_hint_language)
    if repo_path is not None and candidate_suffix == "" and candidate_file is not None:
        suffixless_probe_prefix_text = _suffixless_probe_prefix_text(
            candidate_path,
            candidate_file=candidate_file,
            candidate_stat=candidate_stat,
            repository_service=repository_service,
        )
        if suffixless_probe_prefix_text is not None:
            suffixless_prefix_language = _probe_suffixless_language_from_prefix(
                candidate_path,
                prefix_text=suffixless_probe_prefix_text,
                repo_path=repo_path,
            )
            if suffixless_prefix_language != "unknown":
                return _cache_probe_language_for_path(cache_key, suffixless_prefix_language)
    if repo_path is not None and (
        candidate_basename in _HACK_CONFIG_BASENAMES
        or candidate_suffix in {".hack", ".hh", ".hhi", ".php"}
        or candidate_suffix
        in {
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
            ".fs",
            ".fsi",
            ".fsx",
            ".agda",
            ".agda-lib",
            ".apl",
            ".aplf",
            ".bqn",
            ".circom",
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
            ".dyalog",
            ".reb",
            ".rebol",
            ".r3",
            ".red",
            ".reds",
            ".i",
            ".pp",
            ".hx",
            ".hxml",
            ".scad",
            ".ace",
            ".frm",
            ".gawk",
            ".gradle",
            ".h",
            ".hoon",
            ".inc",
            ".metal",
            ".metalh",
            ".l5x",
            ".l",
            ".lex",
            ".mll",
            ".m",
            ".mqproj",
            ".mawk",
            ".mm",
            ".p",
            ".pf",
            ".mod",
            ".nawk",
            ".pas",
            ".pl",
            ".pch",
            ".purs",
            ".qs",
            ".res",
            ".resi",
            ".roc",
            ".run",
            ".gql",
            ".graphql",
            ".graphqls",
            ".pkl",
            ".pgsql",
            ".sql",
            ".sqlproj",
            ".sass",
            ".st",
            ".w",
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
            ".mo",
            ".moon",
            ".dbproj",
            ".dfy",
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
            ".wat",
            ".wl",
            ".wls",
            ".wsf",
            ".wast",
            ".xtend",
            ".xq",
            ".xquery",
            ".xqy",
            ".xql",
            ".xqm",
            ".xml",
            ".y",
            ".yacc",
            ".mly",
            ".templ",
            ".thrift",
            ".vcl",
        }
        or candidate_basename in {
            "ballerina.toml",
            "fastcgi.conf",
            "fastcgi_params",
            "maven.config",
            "mime.types",
            "nginx.conf",
            "pklproject",
            "qsharp.json",
            "scgi_params",
            "shadow-cljs.edn",
            "uwsgi_params",
        }
        or _HAS_ABAPCDS_PATH_HINTS(candidate_path)
        or _HAS_AIDL_PATH_HINTS(candidate_path)
        or _HAS_AIKEN_PATH_HINTS(candidate_path)
        or _HAS_ALLOY_PATH_HINTS(candidate_path)
        or _HAS_ANGELSCRIPT_PATH_HINTS(candidate_path)
        or _HAS_ANSWER_SET_PROGRAMMING_PATH_HINTS(candidate_path)
        or _HAS_NGINX_PATH_HINTS(candidate_path)
        or _HAS_APACHECONF_PATH_HINTS(candidate_path)
        or _HAS_ASPNET_PATH_HINTS(candidate_path)
        or _HAS_ASL_PATH_HINTS(candidate_path)
        or _HAS_ASPECTJ_PATH_HINTS(path=candidate_path)
        or _HAS_ATS_PATH_HINTS(candidate_path)
        or _HAS_GRAPHQL_PATH_HINTS(candidate_path)
        or _HAS_FREEMARKER_PATH_HINTS(candidate_path)
        or _HAS_MAKO_PATH_HINTS(candidate_path)
        or _HAS_MAVEN_PATH_HINTS(candidate_path)
        or _HAS_MOONSCRIPT_PATH_HINTS(candidate_path)
        or _HAS_ONEC_ENTERPRISE_PATH_HINTS(candidate_path)
        or _HAS_PKL_PATH_HINTS(candidate_path)
        or _HAS_PLPGSQL_PATH_HINTS(candidate_path)
        or _HAS_OCAMLLEX_PATH_HINTS(candidate_path)
        or _HAS_OCAMLYACC_PATH_HINTS(candidate_path)
        or _HAS_TEMPL_PATH_HINTS(candidate_path)
        or _HAS_THRIFT_PATH_HINTS(candidate_path)
        or _HAS_VCL_PATH_HINTS(candidate_path)
        or _HAS_STARLARK_PATH_HINTS(candidate_path)
        or _HAS_WEBASSEMBLY_PATH_HINTS(candidate_path)
        or _HAS_XTEND_PATH_HINTS(candidate_path)
        or (
            candidate_suffix == ""
            and suffixless_probe_prefix_text is not None
        )
    ):
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = None
    language = repository_service._language_for_path(
        candidate_path,
        text=text,
        repo_root=repo_path,
    )
    return _cache_probe_language_for_path(cache_key, language)


def _probe_language_repo_hint(
    normalized_path: str,
    *,
    repo_path: Path | None,
) -> str:
    if repo_path is None:
        return "unknown"

    _candidate_path, _basename, suffix, _parent_basename = _normalized_path_components(
        normalized_path
    )
    if suffix not in {".as", ".fs", ".h", ".pch", ".v"}:
        return "unknown"

    cache_key = (_repo_cache_key(repo_path), suffix)
    cached_language = _PROBE_LANGUAGE_REPO_HINT_CACHE.get(cache_key)
    # The ``.v`` repo-wide vote can resolve to "coq" for a mixed Coq+Verilog repo, which is
    # not authoritative for a specific ``.v`` file. That single per-file disambiguation must
    # NOT be cached against the suffix-only key (it varies per path), so a cached "coq" verdict
    # is re-checked per file below; every other cached verdict is returned directly.
    if cached_language is not None and cached_language != "coq":
        return cached_language

    if cached_language == "coq":
        language = "coq"
    elif suffix == ".as":
        language = probe_ambiguous_as_repo_hint_language(repo_path)
    elif suffix in {".h", ".pch"}:
        language = probe_ambiguous_c_header_repo_hint_language(repo_path)
    elif suffix == ".fs" and repository_service._has_fsharp_project_context(
        path=Path(normalized_path),
        repo_root=repo_path,
    ):
        language = "fsharp"
    elif suffix == ".v":
        language = probe_ambiguous_v_repo_hint_language(repo_path)
    else:
        language = "unknown"

    if language == "coq":
        # Only a repo-wide Coq vote reaches here. Confirm THIS ``.v`` file is really Coq from
        # its own content; otherwise defer to content/suffix classification (e.g. a Verilog
        # ``.v`` that merely shares the repo with a Coq subtree). Cache the repo-wide "coq"
        # vote (so the vote isn't recomputed) but return the per-file resolution.
        _store_probe_language_repo_hint(cache_key, "coq")
        if _is_coq_source_path(repo_path, normalized_path):
            return "coq"
        return "unknown"
    return _store_probe_language_repo_hint(cache_key, language)


def _store_probe_language_repo_hint(
    cache_key: tuple[str, str],
    language: str,
) -> str:
    if cache_key in _PROBE_LANGUAGE_REPO_HINT_CACHE:
        return language
    if len(_PROBE_LANGUAGE_REPO_HINT_CACHE) >= _PROBE_LANGUAGE_REPO_HINT_CACHE_LIMIT:
        oldest_key = next(iter(_PROBE_LANGUAGE_REPO_HINT_CACHE))
        _PROBE_LANGUAGE_REPO_HINT_CACHE.pop(oldest_key, None)
    _PROBE_LANGUAGE_REPO_HINT_CACHE[cache_key] = language
    return language


def _is_profile_entrypoint_noise(path: str) -> bool:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return True
    _candidate_path, basename, _suffix, _parent_basename = _normalized_path_components(
        normalized_path
    )
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
    # Cache the (repo, path, stat) -> result so repeated probes of the same entrypoint
    # candidate don't recompute (and don't re-invoke _is_repo_profile_code_candidate /
    # the language probe). The cache is keyed on the file stat so edits invalidate it.
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return False
    candidate_stat = _repo_file_stat(repo_path, normalized_path) if repo_path is not None else None
    cache_key = (
        str(repo_path) if repo_path is not None else "",
        normalized_path,
        "",
        candidate_stat.st_mtime_ns if candidate_stat is not None else None,
        candidate_stat.st_size if candidate_stat is not None else None,
    )
    cached_result = _OPERATIONAL_ENTRYPOINT_CANDIDATE_CACHE.get(cache_key)
    if cached_result is not None:
        return cached_result
    result = _compute_operational_profile_entrypoint_candidate(path, repo_path=repo_path)
    if len(_OPERATIONAL_ENTRYPOINT_CANDIDATE_CACHE) >= _OPERATIONAL_ENTRYPOINT_CANDIDATE_CACHE_LIMIT:
        oldest_key = next(iter(_OPERATIONAL_ENTRYPOINT_CANDIDATE_CACHE))
        _OPERATIONAL_ENTRYPOINT_CANDIDATE_CACHE.pop(oldest_key, None)
    _OPERATIONAL_ENTRYPOINT_CANDIDATE_CACHE[cache_key] = result
    return result


def _compute_operational_profile_entrypoint_candidate(
    path: str,
    *,
    repo_path: Path | None = None,
) -> bool:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return False
    candidate_path, basename, suffix, _parent_basename = _normalized_path_components(
        normalized_path
    )
    if repository_service._is_test_path(normalized_path) and suffix not in {".wat", ".wast"}:
        return False
    if _is_profile_entrypoint_noise(normalized_path):
        return False
    # Build-tool config wrappers (vite.config.js, next.config.js, theme.config.jsx, …) are
    # configuration, not operational entrypoints — they must not seed the entrypoint surface.
    if basename.endswith(
        (
            ".config.js",
            ".config.jsx",
            ".config.ts",
            ".config.tsx",
            ".config.mjs",
            ".config.cjs",
            ".config.mts",
            ".config.cts",
        )
    ):
        return False
    language = (
        "cmake"
        if basename in repository_service.cmake_adapter.CMAKE_CONFIG_BASENAMES
        else _probe_language_for_path(normalized_path, repo_path=repo_path)
    )
    if language == "robotframework":
        return (
            suffix == ".robot"
            and basename
            not in {"resource.robot", "common.resource", "keywords.resource", "variables.resource"}
        )
    if language == "nextflow":
        return suffix == ".nf"
    if language == "webassembly" and suffix in {
        ".wat",
        ".wast",
    }:
        return True
    if _is_non_operational_profile_path_for_ecosystems(
        normalized_path,
        ecosystems={language},
        repo_path=repo_path,
    ):
        return False
    if language == "cmake" and basename in repository_service.cmake_adapter.CMAKE_CONFIG_BASENAMES:
        return True
    if language == "assembly" and suffix == ".inc":
        return False
    if language == "objectivec" and suffix in {
        ".h",
        ".pch",
    }:
        return False
    if language == "sml" and suffix == ".sig":
        return False
    if language == "rpg" and suffix in {
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
    if language == "vb6" and suffix in {".cls", ".ctl", ".vbp"}:
        return False
    if language == "labview" and suffix in {
        ".ctl",
        ".lvproj",
    }:
        return False
    if language == "tcl" and basename == "pkgindex.tcl":
        return False
    if language == "delphi" and suffix in {
        ".dfm",
        ".fmx",
    }:
        return False
    if language == "systemverilog" and suffix in {
        ".svh",
        ".vh",
    }:
        return False
    if language == "verilog" and suffix == ".vh":
        return False
    if language == "vhdl":
        if (
            _profile_path_tokens(normalized_path) & {"tb", "testbench"}
            or basename.endswith(("_tb.vhd", "_tb.vhdl", "_test.vhd", "_test.vhdl"))
        ):
            return False
    if language == "gdscript" and (basename.startswith("test_") or basename.endswith("_test.gd")):
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
