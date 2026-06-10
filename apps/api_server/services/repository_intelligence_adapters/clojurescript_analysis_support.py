from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    clojure as repository_clojure_support,
)
from apps.api_server.services.repository_intelligence_adapters.clojurescript_primitives import (
    CLOJURESCRIPT_CONFIG_NAMES,
    CLOJURESCRIPT_SUFFIXES,
    StableIdentifier,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)


def is_probable_clojurescript_source(*, path: Path | PurePosixPath | str, text: str) -> bool:
    candidate = PurePosixPath(str(path).replace("\\", "/"))
    if candidate.name.lower() in CLOJURESCRIPT_CONFIG_NAMES:
        return "shadow-cljs" in text
    if candidate.suffix.lower() not in CLOJURESCRIPT_SUFFIXES:
        return False
    if not text.strip():
        return False
    return bool(
        repository_clojure_support.NS_RE.search(text)
        or repository_clojure_support.DEF_DECL_RE.search(text)
        or "(ns " in text
    )


def module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    if PurePosixPath(file_path).suffix.lower() not in CLOJURESCRIPT_SUFFIXES:
        return set()
    return repository_clojure_support.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
    )


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import,
) -> tuple[_Dependency, ...]:
    candidate = PurePosixPath(file_path)
    if candidate.suffix.lower() not in CLOJURESCRIPT_SUFFIXES:
        return ()
    if not is_probable_clojurescript_source(path=candidate, text=text):
        return ()
    return repository_clojure_support.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
    )


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    candidate = PurePosixPath(file_path)
    if candidate.suffix.lower() not in CLOJURESCRIPT_SUFFIXES:
        return (), (), ()
    if not is_probable_clojurescript_source(path=candidate, text=text):
        return (), (), ()
    return repository_clojure_support.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
    )
