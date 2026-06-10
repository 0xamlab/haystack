from __future__ import annotations

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


repository_service = _DeferredProbeAttr("repository_service")
_is_non_operational_profile_path = _DeferredProbeAttr("_is_non_operational_profile_path")
_is_operational_profile_entrypoint_candidate = _DeferredProbeAttr(
    "_is_operational_profile_entrypoint_candidate"
)
_safe_load_toml_dict = _DeferredProbeAttr("_safe_load_toml_dict")


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
    patterns.extend(["**/*", "*"])
    return list(dict.fromkeys(patterns))


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
    package_match = re.search(r"^\s*name:\s*(?P<name>[A-Za-z0-9_.-]+)\s*$", text, re.MULTILINE)
    package_name = str(package_match.group("name") or "").strip() if package_match else ""
    if package_name:
        normalized_name = re.sub(r"[^a-z0-9_]+", "_", package_name.lower()).strip("_")
        if normalized_name:
            entrypoint_paths.add(f"{root_prefix}src/{normalized_name}.cr")
    main_match = re.search(r"^\s*main:\s*(?P<path>[^\s#]+)\s*$", text, re.MULTILINE)
    if main_match:
        main_path = str(main_match.group("path") or "").strip()
        if main_path:
            normalized_main = repository_service._normalize_repository_relative_path(
                str(project_dir / main_path)
            )
            if normalized_main and _is_operational_profile_entrypoint_candidate(
                normalized_main,
                repo_path=repo_path,
            ):
                entrypoint_paths.add(normalized_main)
    return entrypoint_paths, support_roots, config_paths
