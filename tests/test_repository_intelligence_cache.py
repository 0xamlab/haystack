from __future__ import annotations

import pytest

from apps.api_server.services import (
    repository_intelligence_cache as repository_cache,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _FileAnalysis,
    _Symbol,
    _SymbolReferenceCandidate,
)


def test_file_analysis_context_hash_is_scoped_by_repository_root(tmp_path) -> None:
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()

    context_a = repository_cache._file_analysis_context_hash(
        module_index={"main": "main.mo"},
        workspace_package_index={},
        workspace_go_module_index=None,
        max_file_size_bytes=1024,
        engine_revision="rev",
        repository_root=repo_a,
    )
    context_b = repository_cache._file_analysis_context_hash(
        module_index={"main": "main.mo"},
        workspace_package_index={},
        workspace_go_module_index=None,
        max_file_size_bytes=1024,
        engine_revision="rev",
        repository_root=repo_b,
    )

    assert context_a != context_b


def test_file_analysis_context_hash_tracks_parser_implementation_revision(
    tmp_path, monkeypatch
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.setattr(
        repository_cache,
        "_analysis_implementation_fingerprint",
        lambda: "fingerprint-a",
    )
    context_a = repository_cache._file_analysis_context_hash(
        module_index={"main": "main.mo"},
        workspace_package_index={},
        workspace_go_module_index=None,
        max_file_size_bytes=1024,
        engine_revision="rev",
        repository_root=repo_root,
    )

    monkeypatch.setattr(
        repository_cache,
        "_analysis_implementation_fingerprint",
        lambda: "fingerprint-b",
    )
    context_b = repository_cache._file_analysis_context_hash(
        module_index={"main": "main.mo"},
        workspace_package_index={},
        workspace_go_module_index=None,
        max_file_size_bytes=1024,
        engine_revision="rev",
        repository_root=repo_root,
    )

    assert context_a != context_b


def test_analysis_implementation_fingerprint_is_cached_until_cleared(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_count = {"value": 0}

    def _fake_compute_analysis_implementation_fingerprint() -> str:
        call_count["value"] += 1
        return f"fingerprint-{call_count['value']}"

    repository_cache.clear_analysis_implementation_fingerprint_cache()
    monkeypatch.setattr(
        repository_cache,
        "_compute_analysis_implementation_fingerprint",
        _fake_compute_analysis_implementation_fingerprint,
    )

    try:
        first = repository_cache._analysis_implementation_fingerprint()
        second = repository_cache._analysis_implementation_fingerprint()
        repository_cache.clear_analysis_implementation_fingerprint_cache()
        third = repository_cache._analysis_implementation_fingerprint()

        assert first == "fingerprint-1"
        assert second == "fingerprint-1"
        assert third == "fingerprint-2"
        assert call_count["value"] == 2
    finally:
        # This test caches a *fake* fingerprint in a module-global; clear it so the stale
        # value does not leak into later snapshot/analysis cache keys in the same session.
        repository_cache.clear_analysis_implementation_fingerprint_cache()


def test_serialize_file_analysis_preserves_cache_payload_shape() -> None:
    analysis = _FileAnalysis(
        file_path="src/main.mojo",
        language="mojo",
        content_hash="hash-1",
        line_count=7,
        byte_size=128,
        token_estimate=42,
        symbols=(
            _Symbol(
                symbol_id="sym-1",
                symbol_name="main",
                symbol_kind="function",
                start_line=1,
                end_line=3,
                parent_symbol_id=None,
                signature="fn main()",
            ),
        ),
        dependencies=(
            _Dependency(
                dependency_edge_id="dep-1",
                source_file="src/main.mojo",
                target_file="src/lib.mojo",
                target_symbol="lib.main",
                dependency_type="import",
            ),
        ),
        symbol_references=(
            _SymbolReferenceCandidate(
                reference_edge_id="ref-1",
                source_symbol_id="sym-1",
                source_file="src/main.mojo",
                target_symbol_id="sym-2",
                target_file="src/lib.mojo",
                target_names=("lib.main",),
                reference_type="call",
            ),
        ),
    )

    payload = repository_cache._serialize_file_analysis(
        analysis,
        engine_revision="rev-1",
    )

    assert payload == {
        "schema_version": "repository-file-analysis-v1",
        "engine_revision": "rev-1",
        "analysis": {
            "file_path": "src/main.mojo",
            "language": "mojo",
            "content_hash": "hash-1",
            "line_count": 7,
            "byte_size": 128,
            "token_estimate": 42,
            "symbols": [
                {
                    "symbol_id": "sym-1",
                    "symbol_name": "main",
                    "symbol_kind": "function",
                    "start_line": 1,
                    "end_line": 3,
                    "parent_symbol_id": None,
                    "signature": "fn main()",
                }
            ],
            "dependencies": [
                {
                    "dependency_edge_id": "dep-1",
                    "source_file": "src/main.mojo",
                    "target_file": "src/lib.mojo",
                    "target_symbol": "lib.main",
                    "dependency_type": "import",
                }
            ],
            "symbol_references": [
                {
                    "reference_edge_id": "ref-1",
                    "source_symbol_id": "sym-1",
                    "source_file": "src/main.mojo",
                    "target_symbol_id": "sym-2",
                    "target_file": "src/lib.mojo",
                    "target_names": ("lib.main",),
                    "reference_type": "call",
                }
            ],
        },
    }


def test_serialize_dependency_analysis_preserves_cache_payload_shape() -> None:
    dependencies = (
        _Dependency(
            dependency_edge_id="dep-1",
            source_file="src/main.mojo",
            target_file="src/lib.mojo",
            target_symbol="lib.main",
            dependency_type="import",
        ),
    )

    payload = repository_cache._serialize_dependency_analysis(
        dependencies,
        engine_revision="rev-1",
    )

    assert payload == {
        "schema_version": "repository-dependency-analysis-v1",
        "engine_revision": "rev-1",
        "dependencies": [
            {
                "dependency_edge_id": "dep-1",
                "source_file": "src/main.mojo",
                "target_file": "src/lib.mojo",
                "target_symbol": "lib.main",
                "dependency_type": "import",
            }
        ],
    }
