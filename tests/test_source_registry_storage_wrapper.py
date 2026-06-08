from __future__ import annotations

from pathlib import Path

import pytest

from apps.api_server.services import (
    source_registry as reg,
)
from apps.api_server.services import (
    source_registry_ids,
    source_registry_nodes,
    source_registry_storage,
)


def test_source_registry_storage_wrappers_follow_patched_sources_dir(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(reg, "_SOURCES_DIR", tmp_path / "sources")

    expected = source_registry_storage.org_dir(tmp_path / "sources", "org_wrapper")
    assert reg._org_dir("org_wrapper") == expected


def test_source_registry_storage_wrappers_preserve_cache_fingerprint_shape(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(reg, "_SOURCES_DIR", tmp_path / "sources")
    reg._SOURCE_META_CACHE.clear()
    reg._SOURCE_ENTRY_CACHE.clear()

    org_dir = reg._org_dir("org_cache_wrapper")
    meta_path = org_dir / "src.meta.json"
    index_path = org_dir / "index.json"
    reg._write_json(meta_path, {"columns": []})
    reg._write_json(index_path, {"src": {"id": "src"}})

    reg._set_source_meta_cache("org_cache_wrapper", "src", {"columns": []})
    reg._set_source_entry_cache("org_cache_wrapper", "src", {"id": "src"})

    meta_cache = reg._SOURCE_META_CACHE[("org_cache_wrapper", "src")]
    entry_cache = reg._SOURCE_ENTRY_CACHE[("org_cache_wrapper", "src")]

    assert meta_cache[0] == (reg._path_fingerprint(meta_path),)
    assert meta_cache[1] == {"columns": []}
    assert entry_cache[0] == (reg._path_fingerprint(index_path),)
    assert entry_cache[1] == {"id": "src"}

    reg._clear_source_meta_cache("org_cache_wrapper", "src")
    reg._clear_source_entry_cache("org_cache_wrapper", "src")

    assert ("org_cache_wrapper", "src") not in reg._SOURCE_META_CACHE
    assert ("org_cache_wrapper", "src") not in reg._SOURCE_ENTRY_CACHE


def test_source_registry_source_id_wrapper_preserves_deterministic_export() -> None:
    assert reg.source_id_for("abc123") == source_registry_ids.source_id_for("abc123")


def test_source_registry_node_wrapper_preserves_role_normalization() -> None:
    column = {
        "name": "unit_price",
        "role": "metric",
        "mean": 12.75,
        "is_numeric": True,
        "magnitude": "medium",
    }

    wrapped = reg._dict_to_node(column)
    direct = source_registry_nodes.dict_to_node(column)

    assert wrapped.role == "unit_measure"
    assert wrapped.role == direct.role
    assert wrapped.confidence == direct.confidence


def test_source_registry_org_dir_falls_back_when_implicit_home_path_is_unwritable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    implicit_sources_dir = Path("/implicit-default-sources")
    monkeypatch.delenv("ALGENTA_SOURCES_DIR", raising=False)
    monkeypatch.setattr(reg, "_SOURCES_DIR", implicit_sources_dir)
    monkeypatch.setattr(reg, "_IMPLICIT_FALLBACK_SOURCES_DIR", tmp_path / "algenta-sources")
    monkeypatch.setattr(reg, "_WRITABLE_SOURCE_DIRS", set())

    real_org_dir = source_registry_storage.org_dir

    def _fake_org_dir(base: Path, org_id: str) -> Path:
        if base == implicit_sources_dir:
            raise PermissionError(1, "Operation not permitted", str(base / org_id))
        return real_org_dir(base, org_id)

    monkeypatch.setattr(reg._storage, "org_dir", _fake_org_dir)

    resolved = reg._org_dir("org_fallback")

    assert resolved == tmp_path / "algenta-sources" / "org_fallback"
    assert reg._SOURCES_DIR == tmp_path / "algenta-sources"


def test_source_registry_org_dir_preserves_explicit_env_failures(
    monkeypatch,
) -> None:
    explicit_sources_dir = Path("/explicit-configured-sources")
    monkeypatch.setenv("ALGENTA_SOURCES_DIR", str(explicit_sources_dir))
    monkeypatch.setattr(reg, "_SOURCES_DIR", explicit_sources_dir)
    monkeypatch.setattr(reg, "_WRITABLE_SOURCE_DIRS", set())

    def _fake_org_dir(base: Path, org_id: str) -> Path:
        raise PermissionError(1, "Operation not permitted", str(base / org_id))

    monkeypatch.setattr(reg._storage, "org_dir", _fake_org_dir)

    with pytest.raises(PermissionError):
        reg._org_dir("org_explicit")
