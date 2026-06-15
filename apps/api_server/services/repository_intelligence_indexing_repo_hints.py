# ruff: noqa: I001
from __future__ import annotations
from collections.abc import Iterator, Sequence
from pathlib import Path, PurePosixPath
from apps.api_server.services.repository_intelligence_indexing_paths import (
    _normalize_repository_relative_path,
)
from apps.api_server.services.repository_intelligence_indexing import (
    _AMBIGUOUS_C_HEADER_REPO_HINT_CACHE,
    _AMBIGUOUS_C_HEADER_REPO_HINT_CACHE_LIMIT,
    _AMBIGUOUS_C_HEADER_REPO_HINT_SAMPLE_LIMIT,
    _AMBIGUOUS_V_REPO_HINT_CACHE,
    _AMBIGUOUS_V_REPO_HINT_CACHE_LIMIT,
    _CLASSIC_VISUAL_BASIC_PROJECT_CONTEXT_CACHE,
    _CLASSIC_VISUAL_BASIC_PROJECT_CONTEXT_CACHE_LIMIT,
    _CLASSIC_VISUAL_BASIC_PROJECT_MEMBER_CACHE,
    _CLASSIC_VISUAL_BASIC_PROJECT_MEMBER_CACHE_LIMIT,
    _CPP_REPO_HINT_BASENAMES,
    _CPP_REPO_HINT_SUFFIXES,
    _FSHARP_PROJECT_CONTEXT_CACHE,
    _FSHARP_PROJECT_CONTEXT_CACHE_LIMIT,
    _FSHARP_PROJECT_ROOT_CACHE,
    _FSHARP_PROJECT_ROOT_CACHE_LIMIT,
    _OBJECTIVE_C_REPO_HINT_PART_SUFFIXES,
    _OBJECTIVE_C_REPO_HINT_SUFFIXES,
    abapcds_adapter,
    aidl_adapter,
    aiken_adapter,
    alloy_adapter,
    angelscript_adapter,
    answer_set_programming_adapter,
    apacheconf_adapter,
    asl_adapter,
    aspectj_adapter,
    aspnet_adapter,
    ats_adapter,
    brightscript_adapter,
    codeql_adapter,
    common_workflow_language_adapter,
    coq_adapter,
    cvb,
    dataweave_adapter,
    earthly_adapter,
    freemarker_adapter,
    gnuplot_adapter,
    graphql_adapter,
    mako_adapter,
    maven_adapter,
    nginx_adapter,
    objc_adapter,
    onec_enterprise_adapter,
    pkl_adapter,
    v_adapter,
    webassembly_adapter,
    xtend_adapter,
)
def _ranked_adapter_language_for_path(path: Path, *, text: str | None) -> str | None:
    basename = path.name.lower()
    suffix = path.suffix.lower()

    if basename in nginx_adapter.NGINX_INDEX_BASENAMES:
        if text is None:
            return "nginx"
        return "nginx" if nginx_adapter.is_probable_nginx_source(path=path, text=text) else "unknown"
    if basename in aiken_adapter.AIKEN_CONFIG_BASENAMES:
        if text is None:
            return "aiken"
        return "aiken" if aiken_adapter.is_probable_aiken_config(path=path, text=text) else "unknown"
    if basename in apacheconf_adapter.APACHECONF_INDEX_BASENAMES:
        if text is None:
            return "apacheconf"
        return "apacheconf" if apacheconf_adapter.is_probable_apacheconf_source(path=path, text=text) else "unknown"
    if text is not None and nginx_adapter.has_nginx_path_hints(path):
        return "nginx" if nginx_adapter.is_probable_nginx_source(path=path, text=text) else "unknown"
    if text is not None and apacheconf_adapter.has_apacheconf_path_hints(path):
        return "apacheconf" if apacheconf_adapter.is_probable_apacheconf_source(path=path, text=text) else "unknown"
    if suffix in abapcds_adapter.ABAPCDS_SUFFIXES:
        if text is None:
            return "abapcds"
        return "abapcds" if abapcds_adapter.is_probable_abapcds_source(path=path, text=text) else "unknown"
    if suffix in aidl_adapter.AIDL_SUFFIXES:
        if text is None:
            return "aidl"
        return "aidl" if aidl_adapter.is_probable_aidl_source(path=path, text=text) else "unknown"
    if suffix in aiken_adapter.AIKEN_SOURCE_SUFFIXES:
        if text is None:
            return "aiken"
        return "aiken" if aiken_adapter.is_probable_aiken_source(path=path, text=text) else "unknown"
    if suffix in alloy_adapter.ALLOY_SUFFIXES:
        if text is None:
            return "alloy"
        return "alloy" if alloy_adapter.is_probable_alloy_source(path=path, text=text) else "unknown"
    if suffix in answer_set_programming_adapter.ANSWER_SET_PROGRAMMING_SUFFIXES:
        if text is None:
            return "answer set programming"
        return (
            "answer set programming"
            if answer_set_programming_adapter.is_probable_answer_set_programming_source(
                path=path,
                text=text,
            )
            else "unknown"
        )
    if suffix == ".asl" or (text is not None and suffix == ".dsl"):
        if text is None:
            return "asl"
        return "asl" if asl_adapter.is_probable_asl_source(path=path, text=text) else "unknown"
    if suffix in aspectj_adapter.ASPECTJ_SUFFIXES:
        if text is None:
            return "aspectj"
        return "aspectj" if aspectj_adapter.is_probable_aspectj_source(path=path, text=text) else "unknown"
    if suffix in aspnet_adapter.ASPNET_SUFFIXES:
        if text is None:
            return "asp.net"
        return "asp.net" if aspnet_adapter.is_probable_aspnet_source(path=path, text=text) else "unknown"
    if suffix in ats_adapter.ATS_SUFFIXES:
        if text is None:
            return "ats"
        return "ats" if ats_adapter.is_probable_ats_source(path=path, text=text) else "unknown"
    if suffix in graphql_adapter.GRAPHQL_SUFFIXES:
        if text is None:
            return "graphql"
        return "graphql" if graphql_adapter.is_probable_graphql_source(path=path, text=text) else "unknown"
    if suffix in xtend_adapter.XTEND_SUFFIXES:
        if text is None:
            return "xtend"
        return "xtend" if xtend_adapter.is_probable_xtend_source(path=path, text=text) else "unknown"
    if suffix == ".bsl" or (text is not None and suffix == ".os"):
        if text is None:
            return "1centerprise"
        return (
            "1centerprise"
            if onec_enterprise_adapter.is_probable_onec_enterprise_source(path=path, text=text)
            else "unknown"
        )
    if suffix in freemarker_adapter.FREEMARKER_SUFFIXES:
        if text is None:
            return "freemarker"
        return (
            "freemarker"
            if freemarker_adapter.is_probable_freemarker_source(path=path, text=text)
            else "unknown"
        )
    if basename in maven_adapter.MAVEN_PROJECT_BASENAMES | maven_adapter.MAVEN_CONFIG_BASENAMES:
        if text is None:
            return "maven"
        return "maven" if maven_adapter.is_probable_maven_source(path=path, text=text) else "unknown"
    if basename in brightscript_adapter.BRIGHTSCRIPT_CONFIG_BASENAMES:
        if text is None:
            return "brightscript"
        return (
            "brightscript"
            if brightscript_adapter.is_probable_brightscript_config(path=path, text=text)
            else "unknown"
        )
    if suffix in brightscript_adapter.BRIGHTSCRIPT_SOURCE_SUFFIXES:
        if text is None:
            return "brightscript"
        return (
            "brightscript"
            if brightscript_adapter.is_probable_brightscript_source(path=path, text=text)
            else "unknown"
        )
    if suffix in common_workflow_language_adapter.COMMON_WORKFLOW_LANGUAGE_SUFFIXES:
        if text is None:
            return "common workflow language"
        return "common workflow language" if common_workflow_language_adapter.is_probable_common_workflow_language_source(path=path, text=text) else "unknown"
    if suffix in dataweave_adapter.DATAWEAVE_SUFFIXES:
        if text is None:
            return "dataweave"
        return "dataweave" if dataweave_adapter.is_probable_dataweave_source(path=path, text=text) else "unknown"
    if basename in earthly_adapter.EARTHLY_BASENAMES:
        if text is None:
            return "earthly"
        return "earthly" if earthly_adapter.is_probable_earthly_source(path=path, text=text) else "unknown"
    if suffix in gnuplot_adapter.GNUPLOT_SOURCE_SUFFIXES:
        if text is None:
            return "gnuplot" if suffix in gnuplot_adapter.GNUPLOT_CONFIDENT_SOURCE_SUFFIXES else None
        return "gnuplot" if gnuplot_adapter.is_probable_gnuplot_source(path=path, text=text) else "unknown"
    if basename in codeql_adapter.CODEQL_CONFIG_BASENAMES:
        if text is None:
            return "codeql"
        return (
            "codeql"
            if codeql_adapter.is_probable_codeql_config(path=path, text=text)
            else "unknown"
        )
    if suffix in codeql_adapter.CODEQL_SOURCE_SUFFIXES:
        if text is None:
            return "codeql"
        return (
            "codeql"
            if codeql_adapter.is_probable_codeql_source(path=path, text=text)
            else "unknown"
        )
    if suffix in mako_adapter.MAKO_SUFFIXES:
        if text is None:
            return "mako"
        return "mako" if mako_adapter.is_probable_mako_source(path=path, text=text) else "unknown"
    if basename in {"pklproject"}:
        if text is None:
            return "pkl"
        return "pkl" if pkl_adapter.is_probable_pkl_config(path=path, text=text) else "unknown"
    if text is not None and suffix in pkl_adapter.PKL_SUFFIXES:
        return "pkl" if pkl_adapter.is_probable_pkl_source(path=path, text=text) else "unknown"
    if suffix in webassembly_adapter.WEBASSEMBLY_SUFFIXES:
        if text is None:
            return "webassembly"
        return (
            "webassembly"
            if webassembly_adapter.is_probable_webassembly_source(path=path, text=text)
            else "unknown"
        )
    if suffix == ".as" and text is not None:
        if angelscript_adapter.is_probable_angelscript_source(path=path, text=text):
            return "angelscript"
        # `.as` is shared between AngelScript and ActionScript; when the source is
        # not probable AngelScript, fall through so the ActionScript classifier
        # (below) gets a chance instead of hard-classifying the file as unknown.
        return None
    return None

def _candidate_repository_roots(*, root_path: Path, focus_paths: Sequence[str]) -> tuple[Path, ...]:
    if not focus_paths:
        return (root_path,)
    candidates: list[Path] = []
    for focus_path in focus_paths:
        if not focus_path:
            candidates.append(root_path)
            continue
        candidate = (root_path / focus_path).resolve()
        if candidate.exists() and (candidate == root_path or root_path in candidate.parents):
            candidates.append(candidate)
    return tuple(candidates or [root_path])
def _classic_visual_basic_project_members(repo_root: Path) -> frozenset[str]:
    normalized_root = str(repo_root)
    cached_members = _CLASSIC_VISUAL_BASIC_PROJECT_MEMBER_CACHE.get(normalized_root)
    if cached_members is not None:
        return cached_members
    project_members: set[str] = set()
    try:
        manifest_paths = sorted(repo_root.rglob("*.vbp"))
    except OSError:
        manifest_paths = []
    for manifest_path in manifest_paths:
        try:
            relative_manifest_path = _normalize_repository_relative_path(
                str(manifest_path.relative_to(repo_root))
            )
        except ValueError:
            continue
        try:
            text = manifest_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not cvb.is_probable_classic_visual_basic_source(
            path=Path(relative_manifest_path),
            text=text,
        ):
            continue
        project_members.add(relative_manifest_path.lower())
        for entry in cvb.project_component_entries(
            text,
            manifest_path=relative_manifest_path,
        ):
            entry_path = _normalize_repository_relative_path(str(entry.get("path") or ""))
            if entry_path:
                project_members.add(entry_path.lower())
    cached_result = frozenset(project_members)
    if len(_CLASSIC_VISUAL_BASIC_PROJECT_MEMBER_CACHE) >= (
        _CLASSIC_VISUAL_BASIC_PROJECT_MEMBER_CACHE_LIMIT
    ):
        oldest_key = next(iter(_CLASSIC_VISUAL_BASIC_PROJECT_MEMBER_CACHE))
        _CLASSIC_VISUAL_BASIC_PROJECT_MEMBER_CACHE.pop(oldest_key, None)
    _CLASSIC_VISUAL_BASIC_PROJECT_MEMBER_CACHE[normalized_root] = cached_result
    return cached_result
def _has_classic_visual_basic_project_context(*, path: Path, repo_root: Path | None) -> bool:
    if repo_root is None:
        return False
    normalized_root = str(repo_root)
    if path.is_absolute():
        try:
            relative_path = _normalize_repository_relative_path(str(path.relative_to(repo_root)))
        except ValueError:
            relative_path = _normalize_repository_relative_path(str(path))
    else:
        relative_path = _normalize_repository_relative_path(str(path))
    if not relative_path:
        return False
    cache_key = (normalized_root, relative_path.lower())
    cached_result = _CLASSIC_VISUAL_BASIC_PROJECT_CONTEXT_CACHE.get(cache_key)
    if cached_result is not None:
        return cached_result
    has_context = cache_key[1] in _classic_visual_basic_project_members(repo_root)
    if len(_CLASSIC_VISUAL_BASIC_PROJECT_CONTEXT_CACHE) >= (
        _CLASSIC_VISUAL_BASIC_PROJECT_CONTEXT_CACHE_LIMIT
    ):
        oldest_key = next(iter(_CLASSIC_VISUAL_BASIC_PROJECT_CONTEXT_CACHE))
        _CLASSIC_VISUAL_BASIC_PROJECT_CONTEXT_CACHE.pop(oldest_key, None)
    _CLASSIC_VISUAL_BASIC_PROJECT_CONTEXT_CACHE[cache_key] = has_context
    return has_context


def _fsharp_project_roots(repo_root: Path) -> frozenset[str]:
    normalized_root = str(repo_root)
    cached_roots = _FSHARP_PROJECT_ROOT_CACHE.get(normalized_root)
    if cached_roots is not None:
        return cached_roots
    project_roots: set[str] = set()
    try:
        manifest_paths = sorted(repo_root.rglob("*.fsproj"))
    except OSError:
        manifest_paths = []
    for manifest_path in manifest_paths:
        try:
            relative_root = _normalize_repository_relative_path(
                str(manifest_path.parent.relative_to(repo_root))
            )
        except ValueError:
            continue
        project_roots.add((relative_root or "").lower())
    cached_result = frozenset(project_roots)
    if len(_FSHARP_PROJECT_ROOT_CACHE) >= _FSHARP_PROJECT_ROOT_CACHE_LIMIT:
        oldest_key = next(iter(_FSHARP_PROJECT_ROOT_CACHE))
        _FSHARP_PROJECT_ROOT_CACHE.pop(oldest_key, None)
    _FSHARP_PROJECT_ROOT_CACHE[normalized_root] = cached_result
    return cached_result


def _has_fsharp_project_context(*, path: Path, repo_root: Path | None) -> bool:
    if repo_root is None or path.suffix.lower() != ".fs":
        return False
    normalized_root = str(repo_root)
    if path.is_absolute():
        try:
            relative_path = _normalize_repository_relative_path(str(path.relative_to(repo_root)))
        except ValueError:
            relative_path = _normalize_repository_relative_path(str(path))
    else:
        relative_path = _normalize_repository_relative_path(str(path))
    if not relative_path:
        return False
    cache_key = (normalized_root, relative_path.lower())
    cached_result = _FSHARP_PROJECT_CONTEXT_CACHE.get(cache_key)
    if cached_result is not None:
        return cached_result
    project_roots = _fsharp_project_roots(repo_root)
    parent_parts = list(PurePosixPath(cache_key[1]).parent.parts)
    has_context = False
    while True:
        candidate_root = "/".join(parent_parts)
        if candidate_root in project_roots:
            has_context = True
            break
        if not parent_parts:
            break
        parent_parts.pop()
    if len(_FSHARP_PROJECT_CONTEXT_CACHE) >= _FSHARP_PROJECT_CONTEXT_CACHE_LIMIT:
        oldest_key = next(iter(_FSHARP_PROJECT_CONTEXT_CACHE))
        _FSHARP_PROJECT_CONTEXT_CACHE.pop(oldest_key, None)
    _FSHARP_PROJECT_CONTEXT_CACHE[cache_key] = has_context
    return has_context


def _iter_repository_glob_matches(repo_root: Path, pattern: str) -> Iterator[Path]:
    try:
        for candidate in repo_root.rglob(pattern):
            try:
                if candidate.is_file() and not candidate.is_symlink():
                    yield candidate
            except OSError:
                continue
    except OSError:
        return


def _ambiguous_v_repo_hint_language(repo_root: Path | None) -> str:
    if repo_root is None:
        return "unknown"
    normalized_root = str(repo_root.resolve())
    cached_language = _AMBIGUOUS_V_REPO_HINT_CACHE.get(normalized_root)
    if cached_language is not None:
        return cached_language

    def _remember(language: str) -> str:
        if len(_AMBIGUOUS_V_REPO_HINT_CACHE) >= _AMBIGUOUS_V_REPO_HINT_CACHE_LIMIT:
            oldest_key = next(iter(_AMBIGUOUS_V_REPO_HINT_CACHE))
            _AMBIGUOUS_V_REPO_HINT_CACHE.pop(oldest_key, None)
        _AMBIGUOUS_V_REPO_HINT_CACHE[normalized_root] = language
        return language

    has_v_manifest = False
    has_coq_manifest = False
    has_verilog_headers = False
    has_systemverilog_sources = False

    for manifest_path in _iter_repository_glob_matches(repo_root, "v.mod"):
        try:
            manifest_text = manifest_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if v_adapter.is_probable_v_manifest(Path("v.mod"), manifest_text):
            has_v_manifest = True
            break

    for basename in sorted(coq_adapter.COQ_CONFIG_BASENAMES):
        for manifest_path in _iter_repository_glob_matches(repo_root, basename):
            try:
                manifest_text = manifest_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if coq_adapter.is_probable_coq_source(path=Path(basename), text=manifest_text):
                has_coq_manifest = True
                break
        if has_coq_manifest:
            break

    has_verilog_headers = next(_iter_repository_glob_matches(repo_root, "*.vh"), None) is not None
    has_systemverilog_sources = (
        next(_iter_repository_glob_matches(repo_root, "*.sv"), None) is not None
        or next(_iter_repository_glob_matches(repo_root, "*.svh"), None) is not None
    )

    if has_v_manifest and not has_coq_manifest:
        return _remember("v")
    if has_coq_manifest and not has_v_manifest:
        return _remember("coq")
    if has_systemverilog_sources and not (has_v_manifest or has_coq_manifest):
        return _remember("systemverilog")
    if has_verilog_headers and not (has_systemverilog_sources or has_v_manifest or has_coq_manifest):
        return _remember("verilog")
    return _remember("unknown")


def _ambiguous_c_header_repo_hint_language(repo_root: Path | None) -> str:
    if repo_root is None:
        return "unknown"
    normalized_root = str(repo_root.resolve())
    cached_language = _AMBIGUOUS_C_HEADER_REPO_HINT_CACHE.get(normalized_root)
    if cached_language is not None:
        return cached_language

    def _remember(language: str) -> str:
        if len(_AMBIGUOUS_C_HEADER_REPO_HINT_CACHE) >= _AMBIGUOUS_C_HEADER_REPO_HINT_CACHE_LIMIT:
            oldest_key = next(iter(_AMBIGUOUS_C_HEADER_REPO_HINT_CACHE))
            _AMBIGUOUS_C_HEADER_REPO_HINT_CACHE.pop(oldest_key, None)
        _AMBIGUOUS_C_HEADER_REPO_HINT_CACHE[normalized_root] = language
        return language

    has_cpp_signal = False
    has_objective_c_signal = False
    ambiguous_m_paths: list[Path] = []

    for relative_path in _iter_repository_glob_matches(repo_root, "*"):
        suffix = relative_path.suffix.lower()
        basename = relative_path.name.lower()
        path_parts = tuple(part.lower() for part in relative_path.parts)

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
        for candidate in ambiguous_m_paths[:_AMBIGUOUS_C_HEADER_REPO_HINT_SAMPLE_LIMIT]:
            try:
                text = candidate.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if objc_adapter.is_probable_objective_c_source(path=candidate, text=text):
                has_objective_c_signal = True
                break

    if has_cpp_signal and not has_objective_c_signal:
        return _remember("cpp")
    if has_objective_c_signal and not has_cpp_signal:
        return _remember("objectivec")
    return _remember("unknown")

