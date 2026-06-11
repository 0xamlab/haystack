from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration import test_go_live_connectivity_real as connectivity


class _DummyProcess:
    def poll(self) -> None:
        return None


class _ExitedProcess:
    def __init__(self, exit_code: int, log_path: Path | None = None) -> None:
        self._exit_code = exit_code
        self.algenta_log_path = str(log_path) if log_path is not None else None

    def poll(self) -> int:
        return self._exit_code


def test_start_api_server_uses_de_mojo_workers_for_pool_size(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured_env: dict[str, str] = {}
    monkeypatch.delenv("ALGENTA_EGRESS_ALLOWLIST", raising=False)
    monkeypatch.delenv("ALGENTA_SOURCE_ARTIFACT_CACHE_DIR", raising=False)

    def fake_popen(*_args, **kwargs):
        nonlocal captured_env
        captured_env = kwargs["env"]
        return _DummyProcess()

    monkeypatch.setattr(connectivity.subprocess, "Popen", fake_popen)

    sources_dir = tmp_path / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)

    connectivity.start_api_server(
        50123,
        sources_dir,
        {"DE_MOJO_WORKERS": "4"},
    )

    assert captured_env["MOJO_POOL_SIZE"] == "4"
    assert captured_env["ALGENTA_SOURCES_DIR"] == str(sources_dir)
    assert captured_env["ALGENTA_EGRESS_ALLOWLIST"] == "127.0.0.1,localhost,::1"
    assert captured_env["ALGENTA_SOURCE_ARTIFACT_CACHE_DIR"] == str(
        sources_dir.parent / "artifact_cache"
    )
    assert captured_env["PYTHONPATH"] == str(connectivity.ROOT)


def test_start_api_server_preserves_explicit_mojo_pool_size(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured_env: dict[str, str] = {}

    def fake_popen(*_args, **kwargs):
        nonlocal captured_env
        captured_env = kwargs["env"]
        return _DummyProcess()

    monkeypatch.setattr(connectivity.subprocess, "Popen", fake_popen)

    sources_dir = tmp_path / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)

    connectivity.start_api_server(
        50124,
        sources_dir,
        {
            "DE_MOJO_WORKERS": "4",
            "MOJO_POOL_SIZE": "2",
        },
    )

    assert captured_env["MOJO_POOL_SIZE"] == "2"


def test_start_api_server_preserves_existing_allowlist_entries(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured_env: dict[str, str] = {}

    def fake_popen(*_args, **kwargs):
        nonlocal captured_env
        captured_env = kwargs["env"]
        return _DummyProcess()

    monkeypatch.setattr(connectivity.subprocess, "Popen", fake_popen)

    sources_dir = tmp_path / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)

    connectivity.start_api_server(
        50125,
        sources_dir,
        {"ALGENTA_EGRESS_ALLOWLIST": "fixtures.customer.internal"},
    )

    assert captured_env["ALGENTA_EGRESS_ALLOWLIST"] == (
        "fixtures.customer.internal,127.0.0.1,localhost,::1"
    )


def test_wait_for_http_reports_process_exit_and_log_tail(
    monkeypatch,
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "api.log"
    log_path.write_text("booting\nfatal startup error", encoding="utf-8")

    monkeypatch.setattr(connectivity.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        connectivity.httpx,
        "get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("connection refused")),
    )

    monotonic_values = iter([0.0, 0.01])
    monkeypatch.setattr(connectivity.time, "monotonic", lambda: next(monotonic_values))

    with pytest.raises(RuntimeError, match="Process exited with code 7"):
        connectivity.wait_for_http(
            "http://127.0.0.1:59999/v1/health",
            timeout=1.0,
            proc=_ExitedProcess(7, log_path),
        )


def test_wait_for_http_includes_log_tail_on_timeout(
    monkeypatch,
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "api.log"
    log_path.write_text("still starting", encoding="utf-8")

    monkeypatch.setattr(connectivity.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        connectivity.httpx,
        "get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("connection refused")),
    )

    monotonic_values = iter([0.0, 0.5, 1.1])
    monkeypatch.setattr(connectivity.time, "monotonic", lambda: next(monotonic_values))

    with pytest.raises(RuntimeError, match="still starting"):
        connectivity.wait_for_http(
            "http://127.0.0.1:59999/v1/health",
            timeout=1.0,
            log_path=log_path,
        )


def test_parse_selected_tiers_accepts_known_values_and_rejects_unknown() -> None:
    assert connectivity.parse_selected_tiers("credentialed_example") == ("credentialed_example",)
    assert connectivity.parse_selected_tiers("public_no_auth,credentialed_example") == (
        "public_no_auth",
        "credentialed_example",
    )
    with pytest.raises(ValueError, match="Unknown validation tiers"):
        connectivity.parse_selected_tiers("unknown_tier")


def test_parse_selected_connectors_accepts_known_values_and_rejects_unknown() -> None:
    cases = (
        type("Case", (), {"connector_type": "clickhouse"})(),
        type("Case", (), {"connector_type": "snowflake"})(),
    )

    assert connectivity.parse_selected_connectors("clickhouse", cases) == ("clickhouse",)
    assert connectivity.parse_selected_connectors("clickhouse,snowflake", cases) == (
        "clickhouse",
        "snowflake",
    )
    with pytest.raises(ValueError, match="Unknown connector types"):
        connectivity.parse_selected_connectors("bigquery", cases)


def test_filter_validation_cases_by_tiers_returns_only_requested_tiers() -> None:
    cases = (
        type("Case", (), {"tier": "public_no_auth", "case_id": "public"})(),
        type("Case", (), {"tier": "credentialed_example", "case_id": "tier2"})(),
        type("Case", (), {"tier": "customer_credentials_required", "case_id": "tier3"})(),
    )

    selected = connectivity.filter_validation_cases_by_tiers(
        cases,
        ("credentialed_example", "customer_credentials_required"),
    )

    assert tuple(case.case_id for case in selected) == ("tier2", "tier3")


def test_filter_validation_cases_by_connectors_returns_only_requested_connector() -> None:
    cases = (
        type("Case", (), {"connector_type": "clickhouse", "case_id": "clickhouse"})(),
        type("Case", (), {"connector_type": "snowflake", "case_id": "snowflake"})(),
    )

    selected = connectivity.filter_validation_cases_by_connectors(cases, ("clickhouse",))

    assert tuple(case.case_id for case in selected) == ("clickhouse",)


def test_select_external_validation_cases_respects_local_only_mode() -> None:
    cases = (
        type(
            "Case",
            (),
            {"tier": "public_no_auth", "case_id": "public", "connector_type": "s3"},
        )(),
        type(
            "Case",
            (),
            {"tier": "credentialed_example", "case_id": "tier2", "connector_type": "clickhouse"},
        )(),
    )

    assert (
        connectivity.select_external_validation_cases(
            cases,
            selected_tiers=None,
            selected_connectors=None,
            skip_external_validation=True,
        )
        == ()
    )
    assert tuple(
        case.case_id
        for case in connectivity.select_external_validation_cases(
            cases,
            selected_tiers=("credentialed_example",),
            selected_connectors=None,
            skip_external_validation=False,
        )
    ) == ("tier2",)
    assert tuple(
        case.case_id
        for case in connectivity.select_external_validation_cases(
            cases,
            selected_tiers=None,
            selected_connectors=("clickhouse",),
            skip_external_validation=False,
        )
    ) == ("tier2",)


def test_fetch_budget_key_uses_clickhouse_specific_cloud_budget() -> None:
    clickhouse_case = type("Case", (), {"connector_type": "clickhouse"})()
    snowflake_case = type("Case", (), {"connector_type": "snowflake"})()

    assert (
        connectivity._fetch_budget_key(clickhouse_case, {"type": "sql"})
        == "fetch_ms.clickhouse_cloud_fixture"
    )
    assert (
        connectivity._fetch_budget_key(snowflake_case, {"type": "sql"})
        == "fetch_ms.warehouse_fixture"
    )


def test_run_behavior_validation_case_surfaces_structured_connector_failure(monkeypatch) -> None:
    class _Case:
        case_id = "snowflake_customer_connector_test"
        label = "Snowflake connector /test"
        tier = "customer_credentials_required"
        connector_type = "snowflake"
        negative_probe = "none"

        @staticmethod
        def effective_validation_mode() -> str:
            return "connector_test_only"

        @staticmethod
        def effective_behavior_mode() -> str:
            return "connector_test_only"

        @staticmethod
        def build_connector_config() -> dict[str, str]:
            return {"account": "acct"}

    def _fake_timed_api_request(*_args, **_kwargs):
        return (
            None,
            {
                "success": False,
                "status": "error",
                "error_type": "permission",
                "recoverable": True,
                "message": "Snowflake error: Network policy is required.",
            },
        ), 12.3

    monkeypatch.setattr(connectivity, "timed_api_request", _fake_timed_api_request)

    with pytest.raises(
        connectivity.ValidationSkipError,
        match=r"Snowflake live validation blocked by account network policy; skipping external customer-credential case\.",
    ):
        connectivity.run_behavior_validation_case(
            client=None,
            api_key="test-key",
            case=_Case(),
            create_connector=lambda *_args, **_kwargs: "connector-id",
        )


def test_run_behavior_validation_case_preserves_dataset_scope_for_resolved_plan_queries(
    monkeypatch,
) -> None:
    class _Case:
        case_id = "public_s3_source_registration"
        label = "Live S3 source registration"
        tier = "public_no_auth"
        connector_type = "s3"
        aggregation = "sum"
        negative_probe = "none"
        identity_columns = ("id",)
        row_count_tolerance = 0.0
        value_drift_mode = "strict_sample_hash"

        @staticmethod
        def effective_validation_mode() -> str:
            return "register_and_exact_query"

        @staticmethod
        def effective_behavior_mode() -> str:
            return "register_and_exact_query"

        @staticmethod
        def build_runtime_connection() -> dict[str, str]:
            return {"type": "s3"}

        @staticmethod
        def load_runtime_records_for_connection(_connection: dict[str, str]) -> list[dict[str, float]]:
            return [{"id": 1.0, "value": 3.0}]

    query_payloads: list[dict[str, object]] = []
    monkeypatch.setattr(connectivity, "behavior_case_summaries", [])
    monkeypatch.setattr(connectivity, "behavior_p1_failures", [])
    monkeypatch.setattr(connectivity, "_warm_behavior_connection", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(connectivity, "_warm_server_connector_case", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(connectivity, "_warm_server_registration_case", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        connectivity,
        "_schema_columns_from_connection",
        lambda *_args, **_kwargs: [{"name": "id"}, {"name": "value"}],
    )
    monkeypatch.setattr(connectivity, "schema_fingerprint", lambda _columns: "fp")
    monkeypatch.setattr(connectivity, "within_row_count_tolerance", lambda *_args, **_kwargs: (True, "ok"))
    monkeypatch.setattr(connectivity, "ensure_no_identity_duplicates", lambda *_args, **_kwargs: (True, "ok"))
    monkeypatch.setattr(connectivity, "strict_sample_hash", lambda *_args, **_kwargs: "stable")
    monkeypatch.setattr(connectivity, "choose_metric_column", lambda *_args, **_kwargs: "value")
    monkeypatch.setattr(connectivity, "_schema_column_role", lambda *_args, **_kwargs: "metric")
    monkeypatch.setattr(connectivity, "compute_expected_aggregate", lambda *_args, **_kwargs: 3.0)
    monkeypatch.setattr(connectivity, "_assert_registered_schema_has_physical_types", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(connectivity, "_fetch_budget_key", lambda *_args, **_kwargs: "fetch_ms.rest_single_dataset")
    monkeypatch.setattr(connectivity, "_run_rate_limit_probe", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        connectivity,
        "api_request",
        lambda *_args, **_kwargs: (200, {}),
    )

    def _fake_timed_api_request(
        _client,
        method: str,
        path: str,
        *,
        api_key: str,
        json_body: dict[str, object] | None = None,
        expected_status: int,
    ):
        del api_key, expected_status
        if method == "POST" and path == "/v1/sources/register":
            return ((200, {"source_id": "source-123"}), 1.0)
        if method == "GET" and path == "/v1/sources/source-123":
            return ((200, {"schema": {"columns": [{"name": "id"}, {"name": "value"}], "row_count": 1}}), 1.0)
        if method == "POST" and path == "/v1/resolve":
            return (
                (
                    200,
                    {
                        "resolved_plan": {
                            "schema_revision": "source-rev",
                            "source_name": _Case.case_id,
                            "metric_column": "value",
                            "aggregation": "sum",
                        },
                        "latency_ms": 1.0,
                    },
                ),
                1.0,
            )
        if method == "POST" and path == "/v1/query":
            assert json_body is not None
            query_payloads.append(dict(json_body))
            return ((200, {"result": 3.0, "latency_ms": 1.0}), 1.0)
        raise AssertionError((method, path, json_body))

    monkeypatch.setattr(connectivity, "timed_api_request", _fake_timed_api_request)

    summary = connectivity.run_behavior_validation_case(
        client=None,
        api_key="test-key",
        case=_Case(),
        create_connector=lambda *_args, **_kwargs: "connector-id",
    )

    assert summary["metrics"]["query_ms"] == 1.0
    assert len(query_payloads) == 2
    assert query_payloads[0]["dataset_id"] == "source-123"
    assert query_payloads[1]["dataset_id"] == "source-123"
    assert isinstance(query_payloads[0]["resolved_plan"], dict)
