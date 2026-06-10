from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath

def _agda_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    repository_service = probe_module.repository_service
    _is_operational_profile_entrypoint_candidate = probe_module._is_operational_profile_entrypoint_candidate
    _probe_language_for_path = probe_module._probe_language_for_path

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
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    repository_service = probe_module.repository_service
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
    _is_operational_profile_entrypoint_candidate = probe_module._is_operational_profile_entrypoint_candidate
    _probe_language_for_path = probe_module._probe_language_for_path

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
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    repository_service = probe_module.repository_service
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
    _is_operational_profile_entrypoint_candidate = probe_module._is_operational_profile_entrypoint_candidate
    _probe_language_for_path = probe_module._probe_language_for_path

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
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    repository_service = probe_module.repository_service
    _is_operational_profile_entrypoint_candidate = probe_module._is_operational_profile_entrypoint_candidate
    _probe_language_for_path = probe_module._probe_language_for_path

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
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    repository_service = probe_module.repository_service
    _probe_language_for_path = probe_module._probe_language_for_path

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
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    repository_service = probe_module.repository_service
    _is_operational_profile_entrypoint_candidate = probe_module._is_operational_profile_entrypoint_candidate
    _probe_language_for_path = probe_module._probe_language_for_path

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
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    repository_service = probe_module.repository_service
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
    _probe_language_for_path = probe_module._probe_language_for_path

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
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    repository_service = probe_module.repository_service
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
    _probe_language_for_path = probe_module._probe_language_for_path

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
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    repository_service = probe_module.repository_service
    lua_rockspec_module_re = probe_module._LUA_ROCKSPEC_MODULE_RE
    lua_rockspec_package_re = probe_module._LUA_ROCKSPEC_PACKAGE_RE

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
    package_match = lua_rockspec_package_re.search(text)
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
    for match in lua_rockspec_module_re.finditer(text):
        module_path = repository_service._normalize_repository_relative_path(
            str(project_dir / match.group("path"))
        )
        if module_path:
            entrypoint_paths.add(module_path)
    return entrypoint_paths, support_roots, config_paths
