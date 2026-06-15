from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

RouteKind = Literal["registered_adapter", "workflow_special_case"]


@dataclass(frozen=True)
class RuntimeLanguageRoutePlane:
    route_kind: RouteKind
    route_family: str
    raw_language_keys: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_kind": self.route_kind,
            "route_family": self.route_family,
            "raw_language_keys": list(self.raw_language_keys),
        }


@dataclass(frozen=True)
class RepositoryRuntimeLanguageRoute:
    language: str
    file_plane: RuntimeLanguageRoutePlane
    dependency_plane: RuntimeLanguageRoutePlane

    @property
    def route_kind(self) -> str:
        if self.file_plane.route_kind == self.dependency_plane.route_kind:
            return self.file_plane.route_kind
        return f"{self.file_plane.route_kind}+{self.dependency_plane.route_kind}"

    @property
    def route_family(self) -> str:
        if self.file_plane.route_family == self.dependency_plane.route_family:
            return self.file_plane.route_family
        return f"{self.file_plane.route_family}+{self.dependency_plane.route_family}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "route_kind": self.route_kind,
            "route_family": self.route_family,
            "file_plane": self.file_plane.to_dict(),
            "dependency_plane": self.dependency_plane.to_dict(),
        }


@dataclass(frozen=True)
class RepositoryRuntimeLanguageSupportReport:
    supported_languages: tuple[str, ...]
    registered_adapter_languages: tuple[str, ...]
    workflow_special_case_languages: tuple[str, ...]
    runtime_routes: tuple[RepositoryRuntimeLanguageRoute, ...]
    missing_languages: tuple[str, ...]

    @property
    def supported_language_count(self) -> int:
        return len(self.supported_languages)

    @property
    def registered_adapter_language_count(self) -> int:
        return len(self.registered_adapter_languages)

    @property
    def workflow_special_case_language_count(self) -> int:
        return len(self.workflow_special_case_languages)

    @property
    def runtime_covered_language_count(self) -> int:
        return len(self.runtime_routes)

    @property
    def registered_adapter_progress_percent(self) -> float:
        return round(
            (self.registered_adapter_language_count / self.supported_language_count) * 100.0,
            2,
        )

    @property
    def runtime_coverage_percent(self) -> float:
        return round(
            (self.runtime_covered_language_count / self.supported_language_count) * 100.0,
            2,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "supported_languages": list(self.supported_languages),
            "supported_language_count": self.supported_language_count,
            "registered_adapter_languages": list(self.registered_adapter_languages),
            "registered_adapter_language_count": self.registered_adapter_language_count,
            "workflow_special_case_languages": list(self.workflow_special_case_languages),
            "workflow_special_case_language_count": self.workflow_special_case_language_count,
            "runtime_covered_language_count": self.runtime_covered_language_count,
            "registered_adapter_progress_percent": self.registered_adapter_progress_percent,
            "runtime_coverage_percent": self.runtime_coverage_percent,
            "missing_languages": list(self.missing_languages),
            "runtime_routes": [route.to_dict() for route in self.runtime_routes],
        }


_SPECIAL_CASE_ROUTE_FAMILIES: dict[str, str] = {
    "autohotkey": "autohotkey",
    "autoit": "autoit",
    "c": "c_family",
    "coffeescript": "coffeescript",
    "cpp": "c_family",
    "dart": "dart_language",
    "gams": "gams",
    "gleam": "gleam",
    "go": "go_language",
    "haxe": "haxe",
    "java": "jvm",
    "javascript": "js_like",
    "kotlin": "jvm",
    "processing": "jvm",
    "mojo": "mojo_language",
    "mql5": "mql5",
    "nix": "nix",
    "nushell": "nushell",
    "openscad": "openscad",
    "purescript": "purescript",
    "python": "python_language",
    "r": "r_language",
    "rust": "rust_language",
    "scala": "jvm",
    "smalltalk": "smalltalk",
    "squirrel": "squirrel",
    "starlark": "starlark",
    "typescript": "js_like",
    "v": "vlang",
    "vala": "vala",
    "vimscript": "vimscript",
    "zig": "zig",
}


@lru_cache(maxsize=1)
def _adapter_parser_dispatch_module() -> Any:
    from apps.api_server.services import (
        repository_intelligence_adapter_parser_dispatch as repository_adapter_parser_dispatch,
    )

    return repository_adapter_parser_dispatch


@lru_cache(maxsize=1)
def _repository_language_priority_module() -> Any:
    from apps.api_server.services import repository_language_priority

    return repository_language_priority


def _registered_adapter_file_parsers() -> Mapping[str, object]:
    return _adapter_parser_dispatch_module().REGISTERED_ADAPTER_FILE_PARSERS


def _registered_adapter_dependency_parsers() -> Mapping[str, object]:
    return _adapter_parser_dispatch_module().REGISTERED_ADAPTER_DEPENDENCY_PARSERS


def _canonical_repository_language(raw_language_key: str) -> str:
    return _repository_language_priority_module().canonical_repository_language(raw_language_key)


def _supported_repository_languages() -> tuple[str, ...]:
    return _repository_language_priority_module().supported_repository_languages()


def _normalize_route_family(module_name: str) -> str:
    normalized = module_name.rsplit(".", 1)[-1]
    prefix = "repository_intelligence_"
    if normalized.startswith(prefix):
        normalized = normalized[len(prefix) :]
    for suffix in ("_parser_dispatch", "_dispatch"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break
    return normalized or "unknown"


def _build_registered_route_plane_index(
    registered_parsers: Mapping[str, object],
    *,
    supported_language_set: set[str],
) -> dict[str, RuntimeLanguageRoutePlane]:
    families_by_language: dict[str, str] = {}
    raw_keys_by_language: dict[str, set[str]] = {}
    for raw_language_key, parser in registered_parsers.items():
        canonical_language = _canonical_repository_language(raw_language_key)
        if canonical_language not in supported_language_set:
            continue
        route_family = _normalize_route_family(getattr(parser, "__module__", ""))
        existing_family = families_by_language.get(canonical_language)
        if existing_family is not None and existing_family != route_family:
            raise ValueError(
                "registered parser route family mismatch for "
                f"{canonical_language!r}: {existing_family!r} != {route_family!r}"
            )
        families_by_language[canonical_language] = route_family
        raw_keys_by_language.setdefault(canonical_language, set()).add(raw_language_key)
    return {
        language: RuntimeLanguageRoutePlane(
            route_kind="registered_adapter",
            route_family=families_by_language[language],
            raw_language_keys=tuple(sorted(raw_keys_by_language[language])),
        )
        for language in sorted(families_by_language)
    }


def _build_special_case_route_plane_index(
    *,
    supported_language_set: set[str],
) -> dict[str, RuntimeLanguageRoutePlane]:
    unsupported_special_cases = set(_SPECIAL_CASE_ROUTE_FAMILIES) - supported_language_set
    if unsupported_special_cases:
        raise ValueError(
            "workflow special-case inventory includes unsupported languages: "
            f"{sorted(unsupported_special_cases)}"
        )
    return {
        language: RuntimeLanguageRoutePlane(
            route_kind="workflow_special_case",
            route_family=route_family,
            raw_language_keys=(language,),
        )
        for language, route_family in sorted(_SPECIAL_CASE_ROUTE_FAMILIES.items())
    }


def build_repository_runtime_language_support_report() -> (
    RepositoryRuntimeLanguageSupportReport
):
    supported_languages = _supported_repository_languages()
    supported_language_set = set(supported_languages)
    supported_rank = {language: index for index, language in enumerate(supported_languages)}

    registered_file_planes = _build_registered_route_plane_index(
        _registered_adapter_file_parsers(),
        supported_language_set=supported_language_set,
    )
    registered_dependency_planes = _build_registered_route_plane_index(
        _registered_adapter_dependency_parsers(),
        supported_language_set=supported_language_set,
    )
    if set(registered_file_planes) != set(registered_dependency_planes):
        raise ValueError(
            "registered parser file/dependency coverage mismatch: "
            f"file_only={sorted(set(registered_file_planes) - set(registered_dependency_planes))} "
            f"dependency_only={sorted(set(registered_dependency_planes) - set(registered_file_planes))}"
        )

    registered_adapter_languages = tuple(
        language for language in supported_languages if language in registered_file_planes
    )
    registered_adapter_language_set = set(registered_adapter_languages)
    special_case_planes = _build_special_case_route_plane_index(
        supported_language_set=supported_language_set,
    )
    missing_from_registered = supported_language_set - registered_adapter_language_set
    unexpected_missing_special_cases = missing_from_registered - set(special_case_planes)
    stale_special_case_languages = set(special_case_planes) - missing_from_registered
    if unexpected_missing_special_cases or stale_special_case_languages:
        raise ValueError(
            "workflow special-case inventory drifted from runtime coverage: "
            f"missing_special_cases={sorted(unexpected_missing_special_cases)} "
            f"stale_special_cases={sorted(stale_special_case_languages)}"
        )

    workflow_special_case_languages = tuple(
        language
        for language in supported_languages
        if language in special_case_planes and language not in registered_adapter_language_set
    )
    runtime_routes: list[RepositoryRuntimeLanguageRoute] = []
    missing_languages: list[str] = []
    for language in supported_languages:
        file_plane = registered_file_planes.get(language) or special_case_planes.get(language)
        dependency_plane = registered_dependency_planes.get(language) or special_case_planes.get(
            language
        )
        if file_plane is None or dependency_plane is None:
            missing_languages.append(language)
            continue
        runtime_routes.append(
            RepositoryRuntimeLanguageRoute(
                language=language,
                file_plane=file_plane,
                dependency_plane=dependency_plane,
            )
        )

    ordered_runtime_routes = tuple(
        sorted(runtime_routes, key=lambda route: supported_rank[route.language])
    )
    return RepositoryRuntimeLanguageSupportReport(
        supported_languages=supported_languages,
        registered_adapter_languages=registered_adapter_languages,
        workflow_special_case_languages=workflow_special_case_languages,
        runtime_routes=ordered_runtime_routes,
        missing_languages=tuple(missing_languages),
    )


def repository_runtime_language_route_index() -> dict[str, RepositoryRuntimeLanguageRoute]:
    report = build_repository_runtime_language_support_report()
    return {route.language: route for route in report.runtime_routes}
