from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath


def _probe_module():
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    return probe_module


class _DeferredProbeAttr:
    def __init__(self, name: str) -> None:
        self._name = name

    def _resolve(self):
        return getattr(_probe_module(), self._name)

    def __call__(self, *args, **kwargs):
        return self._resolve()(*args, **kwargs)

    def __getattr__(self, attr: str):
        return getattr(self._resolve(), attr)

    def __iter__(self):
        return iter(self._resolve())

    def __contains__(self, item):
        return item in self._resolve()

    def __getitem__(self, key):
        return self._resolve()[key]

    def __len__(self) -> int:
        return len(self._resolve())

    def __bool__(self) -> bool:
        return bool(self._resolve())


repository_service = _DeferredProbeAttr('repository_service')
_is_non_operational_profile_path = _DeferredProbeAttr('_is_non_operational_profile_path')
_is_non_operational_project_path = _DeferredProbeAttr('_is_non_operational_project_path')
_probe_language_for_path = _DeferredProbeAttr('_probe_language_for_path')
from benchmarks.repository_intelligence_real_repo_probe_profile_scripting_runner_support import (
    _batchfile_profile_hints_from_candidates as _batchfile_profile_hints_from_candidates_support,
    _dockerfile_profile_hints_from_candidates as _dockerfile_profile_hints_from_candidates_support,
    _just_profile_hints_from_candidates as _just_profile_hints_from_candidates_support,
    _makefile_profile_hints_from_candidates as _makefile_profile_hints_from_candidates_support,
)


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
    allowed_suffixes = {".vi", ".vim", ".vit", ".lvclass", ".lvlib", ".ctl"}
    fallback_candidates: list[Path] = []
    for candidate_path in search_root.rglob("*"):
        if not candidate_path.is_file() or candidate_path.is_symlink():
            continue
        if candidate_path.suffix.lower() not in allowed_suffixes:
            continue
        fallback_candidates.append(candidate_path)
    for candidate_path in sorted(fallback_candidates):
        relative_path = repository_service._normalize_repository_relative_path(
            str(candidate_path.relative_to(repo_path))
        )
        if (
            not relative_path
            or repository_service._is_test_path(relative_path)
            or _is_non_operational_profile_path(relative_path)
        ):
            continue
        pure_relative_path = PurePosixPath(relative_path)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(pure_relative_path.parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
        if pure_relative_path.suffix.lower() == ".ctl":
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
    probe_module = _probe_module()
    _git_repo_relative_files = probe_module._git_repo_relative_files

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
    normalized_project_dir = repository_service._normalize_repository_relative_path(str(project_dir))
    puppet_source_roots = {
        source_root.lower()
        for source_root in repository_service.puppet_adapter._PUPPET_SOURCE_ROOTS
    }

    def _iter_candidate_paths() -> list[str]:
        git_relative_files = _git_repo_relative_files(repo_path)
        if git_relative_files is not None:
            return git_relative_files
        search_root = repo_path / project_dir
        try:
            return sorted(
                str(candidate.relative_to(repo_path)).replace("\\", "/")
                for candidate in search_root.rglob("*.pp")
                if candidate.is_file() and not candidate.is_symlink()
            )
        except OSError:
            return []

    project_dir_part_count = len(project_dir.parts)
    for raw_relative_path in _iter_candidate_paths():
        relative_path = repository_service._normalize_repository_relative_path(raw_relative_path)
        if (
            not relative_path
            or repository_service._is_test_path(relative_path)
            or _is_non_operational_profile_path(relative_path)
        ):
            continue
        if normalized_project_dir and not (
            relative_path == normalized_project_dir
            or relative_path.startswith(f"{normalized_project_dir}/")
        ):
            continue
        candidate = repo_path / relative_path
        if not candidate.is_file() or candidate.is_symlink():
            continue
        pure_relative_path = PurePosixPath(relative_path)
        if pure_relative_path.suffix.lower() != ".pp":
            continue
        relative_parts = pure_relative_path.parts[project_dir_part_count:]
        if not relative_parts:
            continue
        if (
            pure_relative_path.name.lower() == "site.pp"
            or relative_parts[0].lower() in puppet_source_roots
        ):
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


_batchfile_profile_hints_from_candidates = _batchfile_profile_hints_from_candidates_support
_makefile_profile_hints_from_candidates = _makefile_profile_hints_from_candidates_support
_just_profile_hints_from_candidates = _just_profile_hints_from_candidates_support
_dockerfile_profile_hints_from_candidates = _dockerfile_profile_hints_from_candidates_support
