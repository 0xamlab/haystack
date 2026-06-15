from __future__ import annotations

import functools
import os
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _FileAnalysis,
    _Symbol,
    _SymbolReferenceCandidate,
)
from apps.api_server.services import repository_intelligence_telemetry as telemetry
from apps.api_server.services.repository_intelligence_file_content import (
    read_repository_text,
    repository_analysis_byte_size,
)

DependencyParser = Callable[[str, str, dict[str, str]], tuple[_Dependency, ...]]
FileParser = Callable[
    [str, str, dict[str, str]],
    tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]],
]


def _analyze_file_dependencies(
    *,
    root_path: Path,
    path: Path,
    module_index: dict[str, str],
    workspace_package_index: dict[str, tuple[str, ...]],
    workspace_go_module_index: dict[str, tuple[str, ...]] | None,
    max_file_size_bytes: int,
    path_is_indexable_repository_file: Callable[[Path], bool],
    language_for_path: Callable[..., str],
    registered_adapter_dependency_parsers: Mapping[str, DependencyParser],
    parse_r_dependencies_only: DependencyParser,
    parse_dart_dependencies_only: DependencyParser,
    parse_python_dependencies_only: DependencyParser,
    parse_c_family_dependencies_only: DependencyParser,
    parse_zig_dependencies_only: DependencyParser,
    parse_coffeescript_dependencies_only: DependencyParser,
    parse_vala_dependencies_only: DependencyParser,
    parse_mql5_dependencies_only: DependencyParser,
    parse_gams_dependencies_only: DependencyParser,
    parse_nix_dependencies_only: DependencyParser,
    parse_nushell_dependencies_only: DependencyParser,
    parse_fish_dependencies_only: DependencyParser,
    parse_openscad_dependencies_only: DependencyParser,
    parse_purescript_dependencies_only: DependencyParser,
    parse_gleam_dependencies_only: DependencyParser,
    parse_janet_dependencies_only: DependencyParser,
    parse_haxe_dependencies_only: DependencyParser,
    parse_autohotkey_dependencies_only: DependencyParser,
    parse_autoit_dependencies_only: DependencyParser,
    parse_squirrel_dependencies_only: DependencyParser,
    parse_starlark_dependencies_only: DependencyParser,
    parse_vimscript_dependencies_only: DependencyParser,
    parse_v_dependencies_only: DependencyParser,
    parse_smalltalk_dependencies_only: DependencyParser,
    parse_js_like_dependencies_only: Callable[
        [str, str, dict[str, str], dict[str, tuple[str, ...]]],
        tuple[_Dependency, ...],
    ],
    parse_go_dependencies_only: Callable[
        [str, str, dict[str, str], dict[str, tuple[str, ...]]],
        tuple[_Dependency, ...],
    ],
    parse_jvm_dependencies_only: Callable[
        [str, str, dict[str, str], str],
        tuple[_Dependency, ...],
    ],
    parse_rust_dependencies_only: DependencyParser,
    parse_mojo_dependencies_only: DependencyParser,
) -> tuple[_Dependency, ...]:
    if not path.is_file() or not path_is_indexable_repository_file(path):
        return ()
    if repository_analysis_byte_size(path) > max_file_size_bytes:
        return ()

    relative_path = str(path.relative_to(root_path))
    text = read_repository_text(path)
    language = language_for_path(path, text=text, repo_root=root_path)

    try:
        registered_parser = registered_adapter_dependency_parsers.get(language)
        if registered_parser is not None:
            return registered_parser(relative_path, text, module_index)
        if language == "r":
            return parse_r_dependencies_only(relative_path, text, module_index)
        if language == "dart":
            return parse_dart_dependencies_only(relative_path, text, module_index)
        if language == "python":
            return parse_python_dependencies_only(relative_path, text, module_index)
        if language in {"c", "cpp"}:
            return parse_c_family_dependencies_only(relative_path, text, module_index)
        if language == "zig":
            return parse_zig_dependencies_only(relative_path, text, module_index)
        if language == "coffeescript":
            return parse_coffeescript_dependencies_only(relative_path, text, module_index)
        if language == "vala":
            return parse_vala_dependencies_only(relative_path, text, module_index)
        if language == "mql5":
            return parse_mql5_dependencies_only(relative_path, text, module_index)
        if language == "gams":
            return parse_gams_dependencies_only(relative_path, text, module_index)
        if language == "nix":
            return parse_nix_dependencies_only(relative_path, text, module_index)
        if language == "nushell":
            return parse_nushell_dependencies_only(relative_path, text, module_index)
        if language == "fish":
            return parse_fish_dependencies_only(relative_path, text, module_index)
        if language == "openscad":
            return parse_openscad_dependencies_only(relative_path, text, module_index)
        if language == "purescript":
            return parse_purescript_dependencies_only(relative_path, text, module_index)
        if language == "gleam":
            return parse_gleam_dependencies_only(relative_path, text, module_index)
        if language == "janet":
            return parse_janet_dependencies_only(relative_path, text, module_index)
        if language == "haxe":
            return parse_haxe_dependencies_only(relative_path, text, module_index)
        if language == "autohotkey":
            return parse_autohotkey_dependencies_only(relative_path, text, module_index)
        if language == "autoit":
            return parse_autoit_dependencies_only(relative_path, text, module_index)
        if language == "squirrel":
            return parse_squirrel_dependencies_only(relative_path, text, module_index)
        if language == "starlark":
            return parse_starlark_dependencies_only(relative_path, text, module_index)
        if language == "vimscript":
            return parse_vimscript_dependencies_only(relative_path, text, module_index)
        if language == "v":
            return parse_v_dependencies_only(relative_path, text, module_index)
        if language == "smalltalk":
            return parse_smalltalk_dependencies_only(relative_path, text, module_index)
        if language in {"javascript", "typescript"}:
            return parse_js_like_dependencies_only(
                relative_path,
                text,
                module_index,
                workspace_package_index,
            )
        if language == "go":
            return parse_go_dependencies_only(
                relative_path,
                text,
                module_index,
                workspace_go_module_index or {},
            )
        if language in {"java", "kotlin", "kt", "kts", "scala", "groovy", "processing"}:
            return parse_jvm_dependencies_only(
                relative_path,
                text,
                module_index,
                language=language,
            )
        if language == "rust":
            return parse_rust_dependencies_only(relative_path, text, module_index)
        if language == "mojo":
            return parse_mojo_dependencies_only(relative_path, text, module_index)
    except SyntaxError:
        return ()
    return ()


def _analyze_file_dependencies_cached(
    *,
    root_path: Path,
    path: Path,
    module_index: dict[str, str],
    workspace_package_index: dict[str, tuple[str, ...]],
    workspace_go_module_index: dict[str, tuple[str, ...]] | None,
    max_file_size_bytes: int,
    analysis_context_hash: str,
    engine_revision: str,
    hash_file: Callable[[Path], str],
    dependency_analysis_cache_key: Callable[..., str],
    dependency_analysis_cache_path: Callable[[str], Path],
    load_dependency_analysis_cache: Callable[[Path], tuple[_Dependency, ...] | None],
    serialize_dependency_analysis: Callable[..., dict[str, object]],
    write_json_atomic: Callable[[Path, dict[str, object]], None],
    analyze_file_dependencies: Callable[..., tuple[_Dependency, ...]],
    git_content_hashes: dict[str, str] | None = None,
) -> tuple[_Dependency, ...]:
    relative_path = str(path.relative_to(root_path))
    content_hash = (git_content_hashes or {}).get(relative_path) or hash_file(path)
    cache_key = dependency_analysis_cache_key(
        relative_path=relative_path,
        content_hash=content_hash,
        analysis_context_hash=analysis_context_hash,
        engine_revision=engine_revision,
    )
    cache_path = dependency_analysis_cache_path(cache_key)
    cached_dependencies = load_dependency_analysis_cache(cache_path)
    if cached_dependencies is not None:
        return cached_dependencies

    dependencies = analyze_file_dependencies(
        root_path=root_path,
        path=path,
        module_index=module_index,
        workspace_package_index=workspace_package_index,
        workspace_go_module_index=workspace_go_module_index,
        max_file_size_bytes=max_file_size_bytes,
    )
    write_json_atomic(
        cache_path,
        serialize_dependency_analysis(
            dependencies,
            engine_revision=engine_revision,
        ),
    )
    return dependencies


def _analyze_file(
    *,
    root_path: Path,
    path: Path,
    module_index: dict[str, str],
    workspace_package_index: dict[str, tuple[str, ...]],
    workspace_go_module_index: dict[str, tuple[str, ...]] | None,
    max_file_size_bytes: int,
    hash_file: Callable[[Path], str],
    path_is_indexable_repository_file: Callable[[Path], bool],
    language_for_path: Callable[..., str],
    estimate_tokens: Callable[[str], int],
    registered_adapter_file_parsers: Mapping[str, FileParser],
    parse_r_file: FileParser,
    parse_dart_file: FileParser,
    parse_python_file: FileParser,
    parse_c_family_file: FileParser,
    parse_zig_file: FileParser,
    parse_rust_file: FileParser,
    parse_mojo_file: FileParser,
    parse_coffeescript_file: FileParser,
    parse_vala_file: FileParser,
    parse_mql5_file: FileParser,
    parse_gams_file: FileParser,
    parse_nix_file: FileParser,
    parse_nushell_file: FileParser,
    parse_fish_file: FileParser,
    parse_openscad_file: FileParser,
    parse_purescript_file: FileParser,
    parse_gleam_file: FileParser,
    parse_janet_file: FileParser,
    parse_haxe_file: FileParser,
    parse_autohotkey_file: FileParser,
    parse_autoit_file: FileParser,
    parse_squirrel_file: FileParser,
    parse_starlark_file: FileParser,
    parse_vimscript_file: FileParser,
    parse_v_file: FileParser,
    parse_smalltalk_file: FileParser,
    parse_js_like_file: Callable[
        [str, str, dict[str, str], dict[str, tuple[str, ...]]],
        tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]],
    ],
    parse_go_file: Callable[
        [str, str, dict[str, str], dict[str, tuple[str, ...]]],
        tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]],
    ],
    parse_jvm_file: Callable[
        [str, str, dict[str, str], str],
        tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]],
    ],
    content_hash: str | None = None,
) -> _FileAnalysis:
    relative_path = str(path.relative_to(root_path))
    byte_size = repository_analysis_byte_size(path)
    resolved_content_hash = content_hash or hash_file(path)
    if byte_size > max_file_size_bytes or not path_is_indexable_repository_file(path):
        return _FileAnalysis(
            file_path=relative_path,
            language=language_for_path(path, repo_root=root_path),
            content_hash=resolved_content_hash,
            line_count=0,
            byte_size=byte_size,
            token_estimate=0,
            symbols=(),
            dependencies=(),
            symbol_references=(),
        )

    text = read_repository_text(path)
    language = language_for_path(path, text=text, repo_root=root_path)
    line_count = text.count("\n") + (1 if text else 0)
    token_estimate = estimate_tokens(text)

    try:
        registered_parser = registered_adapter_file_parsers.get(language)
        if registered_parser is not None:
            symbols, dependencies, symbol_references = registered_parser(
                relative_path,
                text,
                module_index,
            )
        elif language == "r":
            symbols, dependencies, symbol_references = parse_r_file(
                relative_path,
                text,
                module_index,
            )
        elif language == "dart":
            symbols, dependencies, symbol_references = parse_dart_file(
                relative_path,
                text,
                module_index,
            )
        elif language == "python":
            symbols, dependencies, symbol_references = parse_python_file(
                relative_path,
                text,
                module_index,
            )
        elif language in {"c", "cpp"}:
            symbols, dependencies, symbol_references = parse_c_family_file(
                relative_path,
                text,
                module_index,
            )
        elif language == "zig":
            symbols, dependencies, symbol_references = parse_zig_file(
                relative_path,
                text,
                module_index,
            )
        elif language == "coffeescript":
            symbols, dependencies, symbol_references = parse_coffeescript_file(
                relative_path,
                text,
                module_index,
            )
        elif language == "vala":
            symbols, dependencies, symbol_references = parse_vala_file(
                relative_path,
                text,
                module_index,
            )
        elif language == "mql5":
            symbols, dependencies, symbol_references = parse_mql5_file(
                relative_path,
                text,
                module_index,
            )
        elif language == "gams":
            symbols, dependencies, symbol_references = parse_gams_file(
                relative_path,
                text,
                module_index,
            )
        elif language == "nix":
            symbols, dependencies, symbol_references = parse_nix_file(
                relative_path,
                text,
                module_index,
            )
        elif language == "nushell":
            symbols, dependencies, symbol_references = parse_nushell_file(
                relative_path,
                text,
                module_index,
            )
        elif language == "fish":
            symbols, dependencies, symbol_references = parse_fish_file(
                relative_path,
                text,
                module_index,
            )
        elif language == "openscad":
            symbols, dependencies, symbol_references = parse_openscad_file(
                relative_path,
                text,
                module_index,
            )
        elif language == "purescript":
            symbols, dependencies, symbol_references = parse_purescript_file(
                relative_path,
                text,
                module_index,
            )
        elif language == "gleam":
            symbols, dependencies, symbol_references = parse_gleam_file(
                relative_path,
                text,
                module_index,
            )
        elif language == "janet":
            symbols, dependencies, symbol_references = parse_janet_file(
                relative_path,
                text,
                module_index,
            )
        elif language == "haxe":
            symbols, dependencies, symbol_references = parse_haxe_file(
                relative_path,
                text,
                module_index,
            )
        elif language == "autohotkey":
            symbols, dependencies, symbol_references = parse_autohotkey_file(
                relative_path,
                text,
                module_index,
            )
        elif language == "autoit":
            symbols, dependencies, symbol_references = parse_autoit_file(
                relative_path,
                text,
                module_index,
            )
        elif language == "squirrel":
            symbols, dependencies, symbol_references = parse_squirrel_file(
                relative_path,
                text,
                module_index,
            )
        elif language == "starlark":
            symbols, dependencies, symbol_references = parse_starlark_file(
                relative_path,
                text,
                module_index,
            )
        elif language == "vimscript":
            symbols, dependencies, symbol_references = parse_vimscript_file(
                relative_path,
                text,
                module_index,
            )
        elif language == "v":
            symbols, dependencies, symbol_references = parse_v_file(
                relative_path,
                text,
                module_index,
            )
        elif language == "smalltalk":
            symbols, dependencies, symbol_references = parse_smalltalk_file(
                relative_path,
                text,
                module_index,
            )
        elif language == "rust":
            symbols, dependencies, symbol_references = parse_rust_file(
                relative_path,
                text,
                module_index,
            )
        elif language == "go":
            symbols, dependencies, symbol_references = parse_go_file(
                relative_path,
                text,
                module_index,
                workspace_go_module_index or {},
            )
        elif language in {"java", "kotlin", "kt", "kts", "scala", "groovy", "processing"}:
            symbols, dependencies, symbol_references = parse_jvm_file(
                relative_path,
                text,
                module_index,
                language=language,
            )
        elif language in {"javascript", "typescript"}:
            symbols, dependencies, symbol_references = parse_js_like_file(
                relative_path,
                text,
                module_index,
                workspace_package_index,
            )
        elif language == "mojo":
            symbols, dependencies, symbol_references = parse_mojo_file(
                relative_path,
                text,
                module_index,
            )
        else:
            symbols, dependencies, symbol_references = (), (), ()
    except SyntaxError:
        symbols, dependencies, symbol_references = (), (), ()

    return _FileAnalysis(
        file_path=relative_path,
        language=language,
        content_hash=resolved_content_hash,
        line_count=line_count,
        byte_size=byte_size,
        token_estimate=token_estimate,
        symbols=symbols,
        dependencies=dependencies,
        symbol_references=symbol_references,
    )


def _analyze_file_cached(
    *,
    root_path: Path,
    path: Path,
    module_index: dict[str, str],
    workspace_package_index: dict[str, tuple[str, ...]],
    workspace_go_module_index: dict[str, tuple[str, ...]] | None,
    max_file_size_bytes: int,
    analysis_context_hash: str,
    engine_revision: str,
    hash_file: Callable[[Path], str],
    file_analysis_cache_key: Callable[..., str],
    file_analysis_cache_path: Callable[[str], Path],
    load_file_analysis_cache: Callable[[Path], _FileAnalysis | None],
    serialize_file_analysis: Callable[..., dict[str, object]],
    write_json_atomic: Callable[[Path, dict[str, object]], None],
    analyze_file: Callable[..., _FileAnalysis],
    git_content_hashes: dict[str, str] | None = None,
) -> _FileAnalysis:
    relative_path = str(path.relative_to(root_path))
    content_hash = (git_content_hashes or {}).get(relative_path) or hash_file(path)
    cache_key = file_analysis_cache_key(
        relative_path=relative_path,
        content_hash=content_hash,
        analysis_context_hash=analysis_context_hash,
        engine_revision=engine_revision,
    )
    cache_path = file_analysis_cache_path(cache_key)
    cached_analysis = load_file_analysis_cache(cache_path)
    if (
        cached_analysis is not None
        and cached_analysis.file_path == relative_path
        and cached_analysis.content_hash == content_hash
    ):
        # AR-OPT-8: content-hash parse cache hit — unchanged file reused, not re-parsed
        # (the warm-snapshot speedup). Telemetry makes the hit rate measurable.
        telemetry.record("parse_cache_hits", 1)
        return cached_analysis

    telemetry.record("parse_cache_misses", 1)
    analysis = analyze_file(
        root_path=root_path,
        path=path,
        module_index=module_index,
        workspace_package_index=workspace_package_index,
        workspace_go_module_index=workspace_go_module_index,
        max_file_size_bytes=max_file_size_bytes,
        content_hash=content_hash,
    )
    write_json_atomic(
        cache_path,
        serialize_file_analysis(
            analysis,
            engine_revision=engine_revision,
        ),
    )
    return analysis


def _snapshot_analysis_max_workers(file_count: int) -> int:
    if file_count <= 1:
        return 1
    if file_count < 4096:
        return 1
    return max(2, min(4, os.cpu_count() or 4))


# AR-OPT-3: per-file parsing is CPU-bound; the thread pool is GIL-limited. The
# ALGENTA_REPOSITORY_PARSE_EXECUTOR flag opts into a ProcessPool. Default stays
# "thread" (a kill switch reproducing the prior behavior exactly) until the
# process path proves byte-parity on the fixture corpus.
_PARSE_EXECUTOR_ENV = "ALGENTA_REPOSITORY_PARSE_EXECUTOR"
_PARSE_EXECUTOR_MODES = ("thread", "process", "sequential")
_PROCESS_WORKER_CAP = 8


def _parse_executor_mode() -> str:
    mode = os.environ.get(_PARSE_EXECUTOR_ENV, "thread").strip().lower()
    return mode if mode in _PARSE_EXECUTOR_MODES else "thread"


def _process_batch_size(file_count: int) -> int:
    # Aim for ~4 batches per worker (load balancing) while keeping each batch large
    # enough that worker IPC/startup is amortized. Lower bound 1 keeps tiny corpora
    # correct; the upper clamp avoids pathologically huge batches on large repos.
    target_batches = max(1, (os.cpu_count() or 2) * 4)
    size = -(-file_count // target_batches)  # ceil division
    return max(1, min(256, size))


def _process_worker_count(batch_count: int) -> int:
    return max(1, min(_PROCESS_WORKER_CAP, os.cpu_count() or 2, batch_count))


def _chunk_paths(paths: Sequence[Path], size: int) -> list[list[Path]]:
    return [list(paths[index : index + size]) for index in range(0, len(paths), size)]


def _analyze_file_batch(
    paths: Sequence[Path],
    *,
    analyze_file_cached: Callable[..., _FileAnalysis],
    root_path: Path,
    module_index: dict[str, str],
    workspace_package_index: dict[str, tuple[str, ...]],
    workspace_go_module_index: dict[str, tuple[str, ...]] | None,
    max_file_size_bytes: int,
    analysis_context_hash: str,
    git_content_hashes: dict[str, str] | None,
) -> list[_FileAnalysis]:
    """Parse one batch of files. Module-level (picklable) so it can run in a worker
    process; ``analyze_file_cached`` must likewise be a top-level callable in process
    mode (production binds ``repository_intelligence_core._analyze_file_cached``, which
    is). Order within the batch is preserved."""
    return [
        analyze_file_cached(
            root_path=root_path,
            path=path,
            module_index=module_index,
            workspace_package_index=workspace_package_index,
            workspace_go_module_index=workspace_go_module_index,
            max_file_size_bytes=max_file_size_bytes,
            analysis_context_hash=analysis_context_hash,
            git_content_hashes=git_content_hashes,
        )
        for path in paths
    ]


def _analyze_snapshot_files(
    *,
    root_path: Path,
    files: Sequence[Path],
    module_index: dict[str, str],
    workspace_package_index: dict[str, tuple[str, ...]],
    workspace_go_module_index: dict[str, tuple[str, ...]] | None,
    max_file_size_bytes: int,
    analysis_context_hash: str,
    analyze_file_cached: Callable[..., _FileAnalysis],
    git_content_hashes: dict[str, str] | None = None,
    max_workers: int | None = None,
    executor: str | None = None,
) -> list[_FileAnalysis]:
    file_list = list(files)
    mode = executor or _parse_executor_mode()

    def _analyze_path(path: Path) -> _FileAnalysis:
        return analyze_file_cached(
            root_path=root_path,
            path=path,
            module_index=module_index,
            workspace_package_index=workspace_package_index,
            workspace_go_module_index=workspace_go_module_index,
            max_file_size_bytes=max_file_size_bytes,
            analysis_context_hash=analysis_context_hash,
            git_content_hashes=git_content_hashes,
        )

    with telemetry.span("snapshot_parse_ms"):
        if mode == "process" and len(file_list) > 1:
            batches = _chunk_paths(file_list, _process_batch_size(len(file_list)))
            batch_worker = functools.partial(
                _analyze_file_batch,
                analyze_file_cached=analyze_file_cached,
                root_path=root_path,
                module_index=module_index,
                workspace_package_index=workspace_package_index,
                workspace_go_module_index=workspace_go_module_index,
                max_file_size_bytes=max_file_size_bytes,
                analysis_context_hash=analysis_context_hash,
                git_content_hashes=git_content_hashes,
            )
            with ProcessPoolExecutor(
                max_workers=_process_worker_count(len(batches))
            ) as pool:
                # map preserves batch order; flatten preserves overall file order.
                return [
                    analysis
                    for batch_result in pool.map(batch_worker, batches)
                    for analysis in batch_result
                ]
        if mode == "sequential":
            return [_analyze_path(path) for path in file_list]
        # "thread" (default): preserve prior behavior exactly — sequential for small
        # repos, bounded ThreadPool otherwise (the AR-OPT-3 kill switch).
        worker_count = max_workers or _snapshot_analysis_max_workers(len(file_list))
        if worker_count <= 1:
            return [_analyze_path(path) for path in file_list]
        with ThreadPoolExecutor(max_workers=worker_count) as thread_pool:
            return list(thread_pool.map(_analyze_path, file_list))
