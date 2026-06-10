"""AR-OPT-8: content-hash parse cache hit/miss telemetry.

The per-file parse cache already short-circuits unchanged files (this is the
warm-snapshot speedup). This test pins the *measurement* of it: parsing the same
file twice in one telemetry scope must record exactly one miss (cold) then one
hit (warm), and the analyzer must run only on the miss.
"""
from __future__ import annotations

from pathlib import Path

from apps.api_server.services import (
    repository_intelligence_analysis_workflow as analysis_workflow,
)
from apps.api_server.services import repository_intelligence_telemetry as telemetry
from apps.api_server.services.repository_intelligence_contracts import _FileAnalysis


def _make_analysis(relative_path: str, content_hash: str) -> _FileAnalysis:
    return _FileAnalysis(
        file_path=relative_path,
        language="python",
        content_hash=content_hash,
        line_count=1,
        byte_size=1,
        token_estimate=1,
        symbols=(),
        dependencies=(),
        symbol_references=(),
    )


def _call(root_path: Path, path: Path, store: dict, analyze_calls: list) -> _FileAnalysis:
    relative_path = str(path.relative_to(root_path))

    def analyze_file(**_kwargs) -> _FileAnalysis:
        analyze_calls.append(relative_path)
        return _make_analysis(relative_path, "h1")

    return analysis_workflow._analyze_file_cached(
        root_path=root_path,
        path=path,
        module_index={},
        workspace_package_index={},
        workspace_go_module_index=None,
        max_file_size_bytes=1_000_000,
        analysis_context_hash="ctx",
        engine_revision="rev",
        hash_file=lambda _p: "h1",
        file_analysis_cache_key=lambda **_kw: "k1",
        file_analysis_cache_path=lambda key: Path(f"/cache/{key}"),
        load_file_analysis_cache=lambda cache_path: store.get(str(cache_path)),
        serialize_file_analysis=lambda analysis, *, engine_revision: analysis,
        write_json_atomic=lambda cache_path, data: store.__setitem__(str(cache_path), data),
        analyze_file=analyze_file,
    )


def test_parse_cache_miss_then_hit_telemetry(tmp_path: Path) -> None:
    root_path = tmp_path
    path = tmp_path / "a.py"
    store: dict = {}
    analyze_calls: list = []

    with telemetry.collect() as data:
        _call(root_path, path, store, analyze_calls)  # cold -> miss
        _call(root_path, path, store, analyze_calls)  # warm -> hit

    assert data["counters"]["parse_cache_misses"] == 1
    assert data["counters"]["parse_cache_hits"] == 1
    # The analyzer ran only on the miss; the hit reused the cached symbols.
    assert analyze_calls == ["a.py"]


def test_parse_cache_telemetry_noop_outside_scope(tmp_path: Path) -> None:
    # Default (no telemetry scope): caching still works, recording is a no-op.
    root_path = tmp_path
    path = tmp_path / "b.py"
    store: dict = {}
    analyze_calls: list = []

    first = _call(root_path, path, store, analyze_calls)
    second = _call(root_path, path, store, analyze_calls)

    assert first.file_path == "b.py"
    assert second is first  # cached object reused
    assert analyze_calls == ["b.py"]
    assert telemetry.current() is None
