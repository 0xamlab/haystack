from apps.api_server.pagination import PaginationEnvelope, paginate_sequence


def test_paginate_sequence_returns_expected_window_metadata() -> None:
    response = paginate_sequence(["a", "b", "c"], page=2, limit=1)

    assert isinstance(response, PaginationEnvelope)
    assert response.items == ["b"]
    assert response.total == 3
    assert response.page == 2
    assert response.limit == 1
    assert response.pages == 3
