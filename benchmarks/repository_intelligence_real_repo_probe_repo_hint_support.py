from __future__ import annotations

from pathlib import Path, PurePosixPath

_AMBIGUOUS_V_REPO_HINT_CACHE_LIMIT = 256
_AMBIGUOUS_V_REPO_HINT_CACHE: dict[str, str] = {}
_AMBIGUOUS_AS_REPO_HINT_CACHE_LIMIT = 256
_AMBIGUOUS_AS_REPO_HINT_CACHE: dict[str, str] = {}
_AMBIGUOUS_AS_REPO_HINT_SAMPLE_LIMIT = 12
_AMBIGUOUS_C_HEADER_REPO_HINT_CACHE_LIMIT = 256
_AMBIGUOUS_C_HEADER_REPO_HINT_CACHE: dict[str, str] = {}
_AMBIGUOUS_C_HEADER_REPO_HINT_SAMPLE_LIMIT = 12
_CPP_REPO_HINT_SUFFIXES = frozenset(
    {
        ".c",
        ".cc",
        ".cpp",
        ".cxx",
        ".h",
        ".hh",
        ".hpp",
        ".hxx",
        ".inl",
        ".ipp",
    }
)
_CPP_REPO_HINT_BASENAMES = frozenset({"cmakelists.txt", "meson.build", "meson_options.txt"})
_OBJECTIVE_C_REPO_HINT_SUFFIXES = frozenset({".mm", ".pch"})
_OBJECTIVE_C_REPO_HINT_PART_SUFFIXES = (".xcodeproj", ".xcworkspace")


def _probe_module():
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    return probe_module


def clear_ambiguous_v_repo_hint_cache() -> None:
    _AMBIGUOUS_V_REPO_HINT_CACHE.clear()


def clear_ambiguous_as_repo_hint_cache() -> None:
    _AMBIGUOUS_AS_REPO_HINT_CACHE.clear()


def clear_ambiguous_c_header_repo_hint_cache() -> None:
    _AMBIGUOUS_C_HEADER_REPO_HINT_CACHE.clear()


def probe_ambiguous_v_repo_hint_language(repo_path: Path) -> str:
    from benchmarks import repository_intelligence_real_repo_probe_collection_support as collection_support

    cache_key = collection_support._repo_cache_key(repo_path)
    cached_language = _AMBIGUOUS_V_REPO_HINT_CACHE.get(cache_key)
    if cached_language is not None:
        return cached_language

    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    tracked_relative_paths = collection_support._git_repo_relative_files(repo_path)
    if tracked_relative_paths is None:
        tracked_relative_paths = collection_support._materialized_repository_relative_files(repo_path)
    if tracked_relative_paths is None:
        language = repository_service._ambiguous_v_repo_hint_language(repo_path)
    else:
        has_v_manifest = False
        has_coq_manifest = False
        has_verilog_headers = False
        has_systemverilog_sources = False
        v_manifest_paths: list[str] = []
        coq_manifest_paths: list[str] = []

        for relative_path in tracked_relative_paths:
            normalized_path = PurePosixPath(relative_path)
            basename = normalized_path.name.lower()
            suffix = normalized_path.suffix.lower()
            if basename == "v.mod":
                v_manifest_paths.append(relative_path)
                continue
            if basename in repository_service.coq_adapter.COQ_CONFIG_BASENAMES:
                coq_manifest_paths.append(relative_path)
                continue
            if suffix == ".vh":
                has_verilog_headers = True
                continue
            if suffix in {".sv", ".svh"}:
                has_systemverilog_sources = True

        for relative_path in v_manifest_paths:
            try:
                manifest_text = (repo_path / relative_path).read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError:
                continue
            if repository_service.v_adapter.is_probable_v_manifest(Path("v.mod"), manifest_text):
                has_v_manifest = True
                break

        for relative_path in sorted(coq_manifest_paths):
            try:
                manifest_text = (repo_path / relative_path).read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError:
                continue
            stripped_text = repository_service.coq_adapter.strip_comments(manifest_text)
            if repository_service.coq_adapter.is_probable_coq_source(
                path=Path(PurePosixPath(relative_path).name),
                text=manifest_text,
                stripped_text=stripped_text,
            ):
                has_coq_manifest = True
                break

        if has_v_manifest and not has_coq_manifest:
            language = "v"
        elif has_coq_manifest and not has_v_manifest:
            language = "coq"
        elif has_systemverilog_sources and not (has_v_manifest or has_coq_manifest):
            language = "systemverilog"
        elif has_verilog_headers and not (has_systemverilog_sources or has_v_manifest or has_coq_manifest):
            language = "verilog"
        else:
            language = "unknown"

    if len(_AMBIGUOUS_V_REPO_HINT_CACHE) >= _AMBIGUOUS_V_REPO_HINT_CACHE_LIMIT:
        oldest_key = next(iter(_AMBIGUOUS_V_REPO_HINT_CACHE))
        _AMBIGUOUS_V_REPO_HINT_CACHE.pop(oldest_key, None)
    _AMBIGUOUS_V_REPO_HINT_CACHE[cache_key] = language
    return language


def probe_ambiguous_as_repo_hint_language(repo_path: Path) -> str:
    from benchmarks import repository_intelligence_real_repo_probe_collection_support as collection_support

    cache_key = collection_support._repo_cache_key(repo_path)
    cached_language = _AMBIGUOUS_AS_REPO_HINT_CACHE.get(cache_key)
    if cached_language is not None:
        return cached_language

    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    tracked_relative_paths = collection_support._git_repo_relative_files(repo_path)
    if tracked_relative_paths is None:
        tracked_relative_paths = collection_support._materialized_repository_relative_files(repo_path)
    actionscript_source_paths = [
        relative_path
        for relative_path in tracked_relative_paths
        if PurePosixPath(relative_path).suffix.lower() == ".as"
    ]

    language = "unknown"
    if any(
        PurePosixPath(relative_path).name.lower() == "asconfig.json"
        for relative_path in tracked_relative_paths
    ):
        language = "actionscript"
    elif actionscript_source_paths:
        actionscript_votes = 0
        angelscript_votes = 0
        for relative_path in actionscript_source_paths[:_AMBIGUOUS_AS_REPO_HINT_SAMPLE_LIMIT]:
            candidate_path = PurePosixPath(relative_path)
            candidate_file = repo_path / relative_path
            try:
                text = candidate_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            # AngelScript is the more specific check (it excludes ActionScript-conflict
            # markers), and ActionScript over-claims through shared path hints like
            # ``main.as`` / a ``scripts/`` directory. Mirror the service classifier's
            # AngelScript-before-ActionScript order so genuine AngelScript content is not
            # out-voted by an ActionScript path-hint match.
            if repository_service.angelscript_adapter.is_probable_angelscript_source(
                path=candidate_path,
                text=text,
            ):
                angelscript_votes += 1
                continue
            if repository_service.actionscript_adapter.is_probable_actionscript_source(
                path=candidate_path,
                text=text,
            ):
                actionscript_votes += 1
        if actionscript_votes > 0 and angelscript_votes == 0:
            language = "actionscript"
        elif angelscript_votes > 0 and actionscript_votes == 0:
            language = "angelscript"

    if len(_AMBIGUOUS_AS_REPO_HINT_CACHE) >= _AMBIGUOUS_AS_REPO_HINT_CACHE_LIMIT:
        oldest_key = next(iter(_AMBIGUOUS_AS_REPO_HINT_CACHE))
        _AMBIGUOUS_AS_REPO_HINT_CACHE.pop(oldest_key, None)
    _AMBIGUOUS_AS_REPO_HINT_CACHE[cache_key] = language
    return language


def probe_ambiguous_c_header_repo_hint_language(repo_path: Path) -> str:
    from benchmarks import repository_intelligence_real_repo_probe_collection_support as collection_support

    cache_key = collection_support._repo_cache_key(repo_path)
    cached_language = _AMBIGUOUS_C_HEADER_REPO_HINT_CACHE.get(cache_key)
    if cached_language is not None:
        return cached_language

    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    tracked_relative_paths = collection_support._git_repo_relative_files(repo_path)
    if tracked_relative_paths is None:
        tracked_relative_paths = collection_support._materialized_repository_relative_files(repo_path)

    has_cpp_signal = False
    has_objective_c_signal = False
    ambiguous_m_paths: list[str] = []
    for relative_path in tracked_relative_paths:
        candidate_path = PurePosixPath(relative_path)
        basename = candidate_path.name.lower()
        suffix = candidate_path.suffix.lower()
        path_parts = tuple(part.lower() for part in candidate_path.parts)

        if basename in _CPP_REPO_HINT_BASENAMES or suffix in _CPP_REPO_HINT_SUFFIXES:
            has_cpp_signal = True
        if suffix in _OBJECTIVE_C_REPO_HINT_SUFFIXES or any(
            part.endswith(_OBJECTIVE_C_REPO_HINT_PART_SUFFIXES) for part in path_parts
        ):
            has_objective_c_signal = True
            break
        if suffix == ".m":
            ambiguous_m_paths.append(relative_path)

    if not has_objective_c_signal:
        for relative_path in ambiguous_m_paths[:_AMBIGUOUS_C_HEADER_REPO_HINT_SAMPLE_LIMIT]:
            candidate_file = repo_path / relative_path
            try:
                text = candidate_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if repository_service.objc_adapter.is_probable_objective_c_source(
                path=PurePosixPath(relative_path),
                text=text,
            ):
                has_objective_c_signal = True
                break

    language = "cpp" if has_cpp_signal and not has_objective_c_signal else "unknown"
    if len(_AMBIGUOUS_C_HEADER_REPO_HINT_CACHE) >= _AMBIGUOUS_C_HEADER_REPO_HINT_CACHE_LIMIT:
        oldest_key = next(iter(_AMBIGUOUS_C_HEADER_REPO_HINT_CACHE))
        _AMBIGUOUS_C_HEADER_REPO_HINT_CACHE.pop(oldest_key, None)
    _AMBIGUOUS_C_HEADER_REPO_HINT_CACHE[cache_key] = language
    return language
