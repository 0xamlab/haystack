"""Tests for repository_intelligence_service: module.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_module_index_lookup_cache_does_not_collide_when_object_ids_repeat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_indexing._MODULE_INDEX_LOOKUP_CACHE.clear()
    monkeypatch.setattr(repository_indexing, "id", lambda _value: 1, raising=False)
    first_module_index = {"MediatR": "src/MediatR/Mediator.cs"}
    second_module_index = {"MediatR": "src/MediatR/Handler.cs"}

    assert repository_indexing._resolve_suffix_match(
        module_index=first_module_index,
        suffixes=["src/MediatR/Mediator.cs"],
    ) == "src/MediatR/Mediator.cs"
    assert repository_indexing._resolve_suffix_match(
        module_index=second_module_index,
        suffixes=["src/MediatR/Handler.cs"],
    ) == "src/MediatR/Handler.cs"

    repository_indexing._MODULE_INDEX_LOOKUP_CACHE.clear()


