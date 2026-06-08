from __future__ import annotations

import json

from apps.api_server.services.connectors.tester import ConnectorTestOutcome
from tests import go_live_connector_probe as probe
from tests.integration.connector_validation_catalog import ConnectorValidationCase


def _probe_case() -> ConnectorValidationCase:
    return ConnectorValidationCase(
        case_id="snowflake_customer_connector_test",
        label="Snowflake connector /test",
        ecosystem="core",
        example_name="snowflake_customer_live",
        connector_type="snowflake",
        tier="customer_credentials_required",
        validation_mode="connector_test_only",
        behavior_mode="connector_test_only",
        connector_config={"account": "acct"},
        behavior_validation_mode="register_and_exact_query",
        behavior_mode_override="immutable",
        behavior_connection_factory=lambda: {"type": "sql"},
    )


def test_select_probe_case_returns_connector_test_case(monkeypatch) -> None:
    monkeypatch.setattr(probe, "ALL_CONNECTOR_VALIDATION_CASES", (_probe_case(),))

    case = probe._select_probe_case("snowflake")

    assert case.case_id == "snowflake_customer_connector_test"


def test_main_prints_probe_json_and_returns_zero_on_success(monkeypatch, capsys) -> None:
    monkeypatch.setattr(probe, "ALL_CONNECTOR_VALIDATION_CASES", (_probe_case(),))

    async def _test_connector_real_detailed(connector_type: str, config: dict[str, object]):
        assert connector_type == "snowflake"
        assert config == {"account": "acct"}
        return ConnectorTestOutcome(
            success=True,
            message="Snowflake connection successful",
            latency_ms=42,
            status="live",
            error_type=None,
            recoverable=None,
        )

    monkeypatch.setattr(probe, "test_connector_real_detailed", _test_connector_real_detailed)

    assert probe.main(["--connector", "snowflake", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["configured"] is True
    assert payload["behavior_ready"] is True
    assert payload["probe"]["status"] == "live"
    assert payload["probe"]["success"] is True


def test_main_fails_closed_without_running_probe_when_connector_is_unconfigured(
    monkeypatch,
    capsys,
) -> None:
    case = ConnectorValidationCase(
        case_id="snowflake_customer_connector_test",
        label="Snowflake connector /test",
        ecosystem="core",
        example_name="snowflake_customer_live",
        connector_type="snowflake",
        tier="customer_credentials_required",
        validation_mode="connector_test_only",
        behavior_mode="connector_test_only",
        connector_config={"account": "acct"},
        required_env_vars=("DE_TEST_SNOWFLAKE_ACCOUNT",),
    )
    monkeypatch.setattr(probe, "ALL_CONNECTOR_VALIDATION_CASES", (case,))
    monkeypatch.delenv("DE_TEST_SNOWFLAKE_ACCOUNT", raising=False)

    async def _boom(*_args, **_kwargs):
        raise AssertionError("probe should not run when connector is unconfigured")

    monkeypatch.setattr(probe, "test_connector_real_detailed", _boom)

    assert probe.main(["--connector", "snowflake"]) == 1

    rendered = capsys.readouterr().out
    assert "configured=False" in rendered
    assert "skip_reason=required env not provided: DE_TEST_SNOWFLAKE_ACCOUNT" in rendered


def test_main_returns_non_zero_and_surfaces_structured_failure(monkeypatch, capsys) -> None:
    monkeypatch.setattr(probe, "ALL_CONNECTOR_VALIDATION_CASES", (_probe_case(),))

    async def _test_connector_real_detailed(_connector_type: str, _config: dict[str, object]):
        return ConnectorTestOutcome(
            success=False,
            message="Snowflake error: Network policy is required.",
            latency_ms=91,
            status="error",
            error_type="permission",
            recoverable=True,
        )

    monkeypatch.setattr(probe, "test_connector_real_detailed", _test_connector_real_detailed)

    assert probe.main(["--connector", "snowflake"]) == 1

    rendered = capsys.readouterr().out
    assert "probe_status=error" in rendered
    assert "error_type=permission" in rendered
    assert "recoverable=True" in rendered
    assert "Network policy is required." in rendered


def test_main_marks_configured_connector_test_only_case_as_behavior_ready(
    monkeypatch,
    capsys,
) -> None:
    case = ConnectorValidationCase(
        case_id="redis_customer_connector_test",
        label="Redis connector /test",
        ecosystem="core",
        example_name="redis_customer_live",
        connector_type="redis",
        tier="customer_credentials_required",
        validation_mode="connector_test_only",
        behavior_mode="connector_test_only",
        connector_config={"url": "redis://default:pass@redis.example.com:15638/0"},
        required_env_vars=("DE_TEST_REDIS_URL",),
    )
    monkeypatch.setattr(probe, "ALL_CONNECTOR_VALIDATION_CASES", (case,))
    monkeypatch.setenv("DE_TEST_REDIS_URL", "redis://default:pass@redis.example.com:15638/0")

    async def _test_connector_real_detailed(_connector_type: str, _config: dict[str, object]):
        return ConnectorTestOutcome(
            success=True,
            message="Redis connection successful",
            latency_ms=19,
            status="live",
            error_type=None,
            recoverable=None,
        )

    monkeypatch.setattr(probe, "test_connector_real_detailed", _test_connector_real_detailed)

    assert probe.main(["--connector", "redis"]) == 0

    rendered = capsys.readouterr().out
    assert "behavior_ready=True" in rendered
