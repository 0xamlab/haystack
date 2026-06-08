from __future__ import annotations

from tests.integration import live_check_filter


def test_selected_live_check_filter_trims_and_omits_empty(monkeypatch) -> None:
    monkeypatch.delenv(live_check_filter.LIVE_CHECK_FILTER_ENV, raising=False)
    assert live_check_filter.selected_live_check_filter() is None

    monkeypatch.setenv(live_check_filter.LIVE_CHECK_FILTER_ENV, "  repository, graph  ")
    assert live_check_filter.selected_live_check_filter() == "repository, graph"


def test_live_check_filter_tokens_and_match_logic() -> None:
    tokens = live_check_filter.live_check_filter_tokens(" repository,graph ")
    assert tokens == ("repository", "graph")

    assert live_check_filter.should_run_live_check(
        "CLI repository intelligence surface",
        tokens,
    )
    assert live_check_filter.should_run_live_check(
        "Repository graph query path",
        tokens,
    )
    assert not live_check_filter.should_run_live_check(
        "LLM routing metadata surface",
        tokens,
    )


def test_filtered_live_check_reason_includes_env_name() -> None:
    assert (
        live_check_filter.filtered_live_check_reason("repository")
        == "filtered out by ALGENTA_LIVE_CHECK_FILTER=repository"
    )


def test_filtered_minimum_passed_uses_one_when_filter_is_active() -> None:
    assert live_check_filter.filtered_minimum_passed(2, ("repository",)) == 1
    assert live_check_filter.filtered_minimum_passed(2, "repository") == 1
    assert live_check_filter.filtered_minimum_passed(2, ()) == 2


def test_filtered_minimum_passed_rejects_invalid_default() -> None:
    try:
        live_check_filter.filtered_minimum_passed(True, ())
    except ValueError as exc:
        assert "integer" in str(exc)
    else:
        raise AssertionError("expected ValueError for boolean default")
