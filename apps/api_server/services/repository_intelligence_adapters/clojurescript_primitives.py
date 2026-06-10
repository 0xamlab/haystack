from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    clojure as repository_clojure_support,
)

StableIdentifier = repository_clojure_support.StableIdentifier
NormalizeRepositoryRelativePath = repository_clojure_support.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_clojure_support.ResolveSuffixMatch

CLOJURESCRIPT_SUFFIXES = frozenset({".cljs"})
CLOJURESCRIPT_CONFIG_NAMES = frozenset({"shadow-cljs.edn"})

extract_ns_form = repository_clojure_support.extract_ns_form
namespace_path = repository_clojure_support.namespace_path
resolve_import = repository_clojure_support.resolve_import


def has_clojurescript_path_hints(path: Path | PurePosixPath | str) -> bool:
    candidate = PurePosixPath(str(path).replace("\\", "/"))
    if candidate.suffix.lower() in CLOJURESCRIPT_SUFFIXES:
        return True
    if candidate.name.lower() in CLOJURESCRIPT_CONFIG_NAMES:
        return True
    normalized_parts = {part.lower() for part in candidate.parts}
    return "cljs" in normalized_parts or "clojurescript" in normalized_parts
