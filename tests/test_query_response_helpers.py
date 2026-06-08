from __future__ import annotations

from apps.api_server.routers import query_response_helpers as qrh


def _build_response(*, log_response: bool = True) -> None:
    qrh._build_query_response(
        query_id="query_123",
        request_id="req_123",
        result={"value": 2},
        result_type="scalar",
        confidence=0.95,
        plan=["Result cache HIT [deadbeef]"],
        resolved_column="amount",
        resolved_role="derived_measure",
        resolved_source="Orders",
        row_count=1,
        candidates=[],
        source_scores={},
        ambiguous=False,
        exact_spec=True,
        explanation=["Count rows in Orders."],
        latency_ms=0.1,
        decision_path="exact_spec",
        schema_revision="schema_rev_1",
        validated=True,
        confidence_source="exact_spec_validation",
        plan_basis={"source_name": "Orders", "metric_column": "amount"},
        log_response=log_response,
    )


def test_build_query_response_logs_by_default(monkeypatch) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    monkeypatch.setattr(qrh.logger, "info", lambda *args, **kwargs: calls.append((args, kwargs)))

    _build_response()

    assert calls
    assert calls[0][0] == ("query_response",)
    assert calls[0][1]["query_id"] == "query_123"


def test_build_query_response_can_skip_hot_path_info_log(monkeypatch) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    monkeypatch.setattr(qrh.logger, "info", lambda *args, **kwargs: calls.append((args, kwargs)))

    _build_response(log_response=False)

    assert calls == []
