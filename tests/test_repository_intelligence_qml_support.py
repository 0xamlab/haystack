from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters import (
    qml_primitives as repository_qml_primitives,
)


def test_qml_strip_comments_reuse_cached_results() -> None:
    repository_qml_primitives._strip_comments_cached.cache_clear()
    source_text = (
        "import QtQuick 2.15\n"
        "// comment\n"
        "Rectangle {\n"
        "    /* block */\n"
        "    id: root\n"
        "}\n"
    )

    first_result = repository_qml_primitives.strip_comments(source_text)
    first_cache_info = repository_qml_primitives._strip_comments_cached.cache_info()
    second_result = repository_qml_primitives.strip_comments(source_text)
    second_cache_info = repository_qml_primitives._strip_comments_cached.cache_info()

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1
