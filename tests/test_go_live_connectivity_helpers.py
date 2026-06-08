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
