from __future__ import annotations

import pytest

from tests.go_live_matrix_status import (
    collect_matrix_status,
    collect_requirement_failures,
    filter_statuses_by_connectors,
    matrix_status_payload,
    parse_selected_connectors,
    parse_selected_tiers,
    render_matrix_status,
    summarize_operational_gaps,
)
from tests.integration.connector_validation_catalog import ALL_CONNECTOR_VALIDATION_CASES


def test_collect_matrix_status_reports_public_case_as_configured_without_envs(monkeypatch) -> None:
    for env_name in (
        "DE_TEST_FRED_API_KEY",
        "DE_TEST_GITHUB_TOKEN",
        "DE_TEST_REDIS_URL",
        "DE_TEST_CLICKHOUSE_URL",
        "DE_TEST_CLICKHOUSE_USER",
        "DE_TEST_CLICKHOUSE_PASSWORD",
        "DE_TEST_ELASTICSEARCH_URL",
        "DE_TEST_ELASTICSEARCH_API_KEY",
        "DE_TEST_NEO4J_URI",
        "DE_TEST_NEO4J_USERNAME",
        "DE_TEST_NEO4J_PASSWORD",
        "DE_TEST_SNOWFLAKE_ACCOUNT",
        "DE_TEST_SNOWFLAKE_USER",
        "DE_TEST_SNOWFLAKE_PASSWORD",
        "DE_TEST_SNOWFLAKE_WAREHOUSE",
        "DE_TEST_BIGQUERY_PROJECT_ID",
        "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON",
        "DE_TEST_ORACLE_USER",
        "DE_TEST_ORACLE_PASSWORD",
        "DE_TEST_ORACLE_DSN",
        "DE_TEST_ORACLE_HOST",
    ):
        monkeypatch.delenv(env_name, raising=False)

    statuses = {
        status.case_id: status for status in collect_matrix_status(ALL_CONNECTOR_VALIDATION_CASES)
    }

    public_s3 = statuses["public_s3_source_registration"]
    assert public_s3.configured is True
    assert public_s3.skip_reason is None
    assert public_s3.behavior_ready is True
    assert public_s3.behavior_upgrade_active is False

    redis_status = statuses["redis_customer_connector_test"]
    assert redis_status.configured is False
    assert redis_status.skip_reason == "required env not provided: DE_TEST_REDIS_URL"
    assert redis_status.effective_validation_mode == "connector_test_only"

    clickhouse = statuses["clickhouse_customer_connector_test"]
    assert clickhouse.configured is False
    assert (
        clickhouse.skip_reason
        == "required env not provided: DE_TEST_CLICKHOUSE_URL, DE_TEST_CLICKHOUSE_USER, DE_TEST_CLICKHOUSE_PASSWORD"
    )
    assert clickhouse.effective_validation_mode == "connector_test_only"

    elasticsearch = statuses["elasticsearch_customer_connector_test"]
    assert elasticsearch.configured is False
    assert (
        elasticsearch.skip_reason
        == "required env not provided: DE_TEST_ELASTICSEARCH_URL, DE_TEST_ELASTICSEARCH_API_KEY"
    )
    assert elasticsearch.effective_validation_mode == "connector_test_only"

    neo4j = statuses["neo4j_customer_connector_test"]
    assert neo4j.configured is False
    assert (
        neo4j.skip_reason
        == "required env not provided: DE_TEST_NEO4J_URI, DE_TEST_NEO4J_USERNAME, DE_TEST_NEO4J_PASSWORD"
    )
    assert neo4j.effective_validation_mode == "connector_test_only"

    snowflake = statuses["snowflake_customer_connector_test"]
    assert snowflake.configured is False
    assert (
        snowflake.skip_reason
        == "required env not provided: DE_TEST_SNOWFLAKE_ACCOUNT, DE_TEST_SNOWFLAKE_USER, DE_TEST_SNOWFLAKE_PASSWORD, DE_TEST_SNOWFLAKE_WAREHOUSE"
    )
    assert snowflake.effective_validation_mode == "connector_test_only"

    oracle = statuses["oracle_customer_connector_test"]
    assert oracle.configured is False
    assert oracle.skip_reason == (
        "required env not provided: DE_TEST_ORACLE_USER, DE_TEST_ORACLE_PASSWORD, "
        "DE_TEST_ORACLE_DSN"
    )
    assert oracle.effective_validation_mode == "connector_test_only"


def test_parse_selected_tiers_accepts_known_tiers_and_rejects_unknown() -> None:
    assert parse_selected_tiers("credentialed_example") == ("credentialed_example",)
    assert parse_selected_tiers("public_no_auth,credentialed_example") == (
        "public_no_auth",
        "credentialed_example",
    )
    with pytest.raises(ValueError, match="Unknown validation tiers"):
        parse_selected_tiers("invalid_tier")


def test_parse_selected_connectors_accepts_known_connectors_and_rejects_unknown() -> None:
    assert parse_selected_connectors("clickhouse") == ("clickhouse",)
    assert parse_selected_connectors("clickhouse,snowflake") == ("clickhouse", "snowflake")
    with pytest.raises(ValueError, match="Unknown connector types"):
        parse_selected_connectors("invalid_connector")


def test_filter_statuses_by_connectors_returns_only_requested_connector() -> None:
    statuses = collect_matrix_status(ALL_CONNECTOR_VALIDATION_CASES)
    filtered = filter_statuses_by_connectors(statuses, ("clickhouse",))

    assert filtered
    assert {status.connector_type for status in filtered} == {"clickhouse"}


def test_collect_matrix_status_upgrades_warehouse_behavior_only_with_selectors(monkeypatch) -> None:
    monkeypatch.setenv("DE_TEST_REDIS_URL", "redis://default:pass@redis.example.com:15638/0")
    monkeypatch.setenv("DE_TEST_CLICKHOUSE_URL", "https://clickhouse.example.com:8443")
    monkeypatch.setenv("DE_TEST_CLICKHOUSE_USER", "default")
    monkeypatch.setenv("DE_TEST_CLICKHOUSE_PASSWORD", "pass")
    monkeypatch.setenv("DE_TEST_CLICKHOUSE_TABLE", "fees_decisions")
    monkeypatch.setenv("DE_TEST_ELASTICSEARCH_URL", "https://elastic.example.com:443")
    monkeypatch.setenv("DE_TEST_ELASTICSEARCH_API_KEY", "elastic-key")
    monkeypatch.setenv("DE_TEST_NEO4J_URI", "neo4j+s://graph.example.com")
    monkeypatch.setenv("DE_TEST_NEO4J_USERNAME", "neo4j")
    monkeypatch.setenv("DE_TEST_NEO4J_PASSWORD", "pass")
    monkeypatch.setenv("DE_TEST_SNOWFLAKE_ACCOUNT", "acct")
    monkeypatch.setenv("DE_TEST_SNOWFLAKE_USER", "user")
    monkeypatch.setenv("DE_TEST_SNOWFLAKE_PASSWORD", "pass")
    monkeypatch.setenv("DE_TEST_SNOWFLAKE_WAREHOUSE", "wh")
    monkeypatch.setenv("DE_TEST_SNOWFLAKE_TABLE", "NATION")
    monkeypatch.setenv("DE_TEST_BIGQUERY_PROJECT_ID", "proj")
    monkeypatch.setenv(
        "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON",
        '{"type":"service_account","project_id":"proj"}',
    )
    monkeypatch.setenv("DE_TEST_BIGQUERY_DATASET", "samples")
    monkeypatch.setenv("DE_TEST_BIGQUERY_TABLE", "shakespeare")
    monkeypatch.setenv("DE_TEST_ORACLE_USER", "reader")
    monkeypatch.setenv("DE_TEST_ORACLE_PASSWORD", "pass")
    monkeypatch.setenv("DE_TEST_ORACLE_DSN", "oracle.example.com:1521/analytics")
    monkeypatch.setenv("DE_TEST_ORACLE_HOST", "oracle.example.com")
    monkeypatch.setenv("DE_TEST_ORACLE_TABLE", "REPORTING.FACTS")

    statuses = {
        status.case_id: status for status in collect_matrix_status(ALL_CONNECTOR_VALIDATION_CASES)
    }
    rendered = render_matrix_status(list(statuses.values()))

    redis_status = statuses["redis_customer_connector_test"]
    clickhouse = statuses["clickhouse_customer_connector_test"]
    elasticsearch = statuses["elasticsearch_customer_connector_test"]
    neo4j = statuses["neo4j_customer_connector_test"]
    snowflake = statuses["snowflake_customer_connector_test"]
    bigquery = statuses["bigquery_customer_connector_test"]
    oracle = statuses["oracle_customer_connector_test"]

    assert redis_status.configured is True
    assert redis_status.behavior_ready is True
    assert redis_status.behavior_upgrade_active is False
    assert redis_status.effective_validation_mode == "connector_test_only"
    assert clickhouse.configured is True
    assert clickhouse.behavior_ready is True
    assert clickhouse.behavior_upgrade_active is True
    assert clickhouse.effective_validation_mode == "register_and_exact_query"
    assert elasticsearch.configured is True
    assert elasticsearch.behavior_ready is True
    assert elasticsearch.behavior_upgrade_active is False
    assert elasticsearch.effective_validation_mode == "connector_test_only"
    assert neo4j.configured is True
    assert neo4j.behavior_ready is True
    assert neo4j.behavior_upgrade_active is False
    assert neo4j.effective_validation_mode == "connector_test_only"
    assert snowflake.configured is True
    assert snowflake.behavior_ready is True
    assert snowflake.behavior_upgrade_active is True
    assert snowflake.effective_validation_mode == "register_and_exact_query"
    assert bigquery.behavior_ready is True
    assert bigquery.behavior_upgrade_active is True
    assert bigquery.effective_validation_mode == "register_and_exact_query"
    assert oracle.configured is True
    assert oracle.behavior_ready is True
    assert oracle.behavior_upgrade_active is True
    assert oracle.effective_validation_mode == "register_and_exact_query"
    assert (
        "redis_customer_connector_test | customer_credentials_required | "
        "redis | configured | behavior=connector_test_only"
    ) in rendered
    assert (
        "clickhouse_customer_connector_test | customer_credentials_required | "
        "clickhouse | configured | behavior=register_and_exact_query"
    ) in rendered
    assert (
        "elasticsearch_customer_connector_test | customer_credentials_required | "
        "elasticsearch | configured | behavior=connector_test_only"
    ) in rendered
    assert (
        "neo4j_customer_connector_test | customer_credentials_required | "
        "neo4j | configured | behavior=connector_test_only"
    ) in rendered
    assert (
        "snowflake_customer_connector_test | customer_credentials_required | "
        "snowflake | configured | behavior=register_and_exact_query"
    ) in rendered
    assert (
        "bigquery_customer_connector_test | customer_credentials_required | "
        "bigquery | configured | behavior=register_and_exact_query"
    ) in rendered
    assert (
        "oracle_customer_connector_test | customer_credentials_required | "
        "oracle | configured | behavior=register_and_exact_query"
    ) in rendered


def test_matrix_status_payload_is_machine_readable(monkeypatch) -> None:
    monkeypatch.delenv("DE_TEST_FRED_API_KEY", raising=False)
    monkeypatch.delenv("DE_ENABLE_SLOW_PUBLIC_REST_CASES", raising=False)
    statuses = collect_matrix_status(ALL_CONNECTOR_VALIDATION_CASES)
    payload = matrix_status_payload(statuses)

    assert payload["summary"]["total_cases"] == len(ALL_CONNECTOR_VALIDATION_CASES)
    assert payload["summary"]["tiers"]["public_no_auth"]["total"] == 8
    assert payload["summary"]["tiers"]["public_no_auth"]["behavior_ready"] == 7
    case_ids = {case["case_id"] for case in payload["cases"]}
    assert "public_s3_source_registration" in case_ids
    assert "clickhouse_customer_connector_test" in case_ids
    assert "elasticsearch_customer_connector_test" in case_ids
    assert "neo4j_customer_connector_test" in case_ids
    assert "snowflake_customer_connector_test" in case_ids
    assert "oracle_customer_connector_test" in case_ids
    assert any(gap["case_id"] == "dlt_github_issues" for gap in payload["operational_gaps"])


def test_summarize_operational_gaps_reports_non_repo_blockers(monkeypatch) -> None:
    monkeypatch.delenv("DE_ENABLE_SLOW_PUBLIC_REST_CASES", raising=False)
    monkeypatch.delenv("DE_TEST_FRED_API_KEY", raising=False)
    monkeypatch.delenv("DE_TEST_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("DE_TEST_REDIS_URL", raising=False)

    gaps = summarize_operational_gaps(collect_matrix_status(ALL_CONNECTOR_VALIDATION_CASES))
    gap_index = {gap["case_id"]: gap for gap in gaps}

    assert gap_index["dlt_github_issues"]["gap_type"] == "not_configured"
    assert "disabled by default" in gap_index["dlt_github_issues"]["reason"]
    assert gap_index["fivetran_fred_gnpca"]["tier"] == "credentialed_example"
    assert gap_index["redis_customer_connector_test"]["connector_type"] == "redis"


def test_collect_requirement_failures_reports_missing_cases_for_strict_mode(monkeypatch) -> None:
    monkeypatch.delenv("DE_ENABLE_SLOW_PUBLIC_REST_CASES", raising=False)
    monkeypatch.delenv("DE_TEST_FRED_API_KEY", raising=False)
    monkeypatch.delenv("DE_TEST_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("DE_TEST_REDIS_URL", raising=False)
    monkeypatch.delenv("DE_TEST_CLICKHOUSE_URL", raising=False)
    monkeypatch.delenv("DE_TEST_CLICKHOUSE_USER", raising=False)
    monkeypatch.delenv("DE_TEST_CLICKHOUSE_PASSWORD", raising=False)
    monkeypatch.delenv("DE_TEST_ELASTICSEARCH_URL", raising=False)
    monkeypatch.delenv("DE_TEST_ELASTICSEARCH_API_KEY", raising=False)
    monkeypatch.delenv("DE_TEST_NEO4J_URI", raising=False)
    monkeypatch.delenv("DE_TEST_NEO4J_USERNAME", raising=False)
    monkeypatch.delenv("DE_TEST_NEO4J_PASSWORD", raising=False)
    monkeypatch.delenv("DE_TEST_SNOWFLAKE_ACCOUNT", raising=False)
    monkeypatch.delenv("DE_TEST_SNOWFLAKE_USER", raising=False)
    monkeypatch.delenv("DE_TEST_SNOWFLAKE_PASSWORD", raising=False)
    monkeypatch.delenv("DE_TEST_SNOWFLAKE_WAREHOUSE", raising=False)
    monkeypatch.delenv("DE_TEST_BIGQUERY_PROJECT_ID", raising=False)
    monkeypatch.delenv("DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("DE_TEST_ORACLE_USER", raising=False)
    monkeypatch.delenv("DE_TEST_ORACLE_PASSWORD", raising=False)
    monkeypatch.delenv("DE_TEST_ORACLE_DSN", raising=False)
    monkeypatch.delenv("DE_TEST_ORACLE_HOST", raising=False)

    failures = collect_requirement_failures(
        collect_matrix_status(ALL_CONNECTOR_VALIDATION_CASES),
        require_all_configured=True,
        require_all_behavior_ready=True,
    )
    failure_index = {(failure.requirement, failure.case_id): failure.reason for failure in failures}

    assert ("all_configured", "fivetran_fred_gnpca") in failure_index
    assert ("all_configured", "redis_customer_connector_test") in failure_index
    assert ("all_configured", "elasticsearch_customer_connector_test") in failure_index
    assert ("all_configured", "neo4j_customer_connector_test") in failure_index
    assert ("all_behavior_ready", "redis_customer_connector_test") in failure_index
    assert ("all_behavior_ready", "elasticsearch_customer_connector_test") in failure_index
    assert ("all_behavior_ready", "neo4j_customer_connector_test") in failure_index
    assert ("all_behavior_ready", "clickhouse_customer_connector_test") in failure_index
    assert ("all_behavior_ready", "snowflake_customer_connector_test") in failure_index
    assert ("all_configured", "oracle_customer_connector_test") in failure_index
    assert ("all_behavior_ready", "oracle_customer_connector_test") in failure_index
    assert ("all_configured", "fivetran_noaa_station_kilg") not in failure_index
    assert ("all_configured", "dlt_github_issues") in failure_index


def test_collect_requirement_failures_is_empty_when_all_cases_are_enabled(monkeypatch) -> None:
    monkeypatch.setenv("DE_ENABLE_SLOW_PUBLIC_REST_CASES", "1")
    monkeypatch.setenv("DE_TEST_FRED_API_KEY", "fred-key")
    monkeypatch.setenv("DE_TEST_GITHUB_TOKEN", "gh-token")
    monkeypatch.setenv("DE_TEST_S3_BUCKET", "bucket")
    monkeypatch.setenv("DE_TEST_S3_KEY", "path/data.csv")
    monkeypatch.setenv("DE_TEST_GCS_BUCKET", "bucket")
    monkeypatch.setenv("DE_TEST_GCS_BLOB", "path/data.csv")
    monkeypatch.setenv(
        "DE_TEST_AZURE_BLOB_URL", "https://example.blob.core.windows.net/c/container/blob.csv"
    )
    monkeypatch.setenv("DE_TEST_REDIS_URL", "redis://default:pass@redis.example.com:15638/0")
    monkeypatch.setenv("DE_TEST_CLICKHOUSE_URL", "https://clickhouse.example.com:8443")
    monkeypatch.setenv("DE_TEST_CLICKHOUSE_USER", "default")
    monkeypatch.setenv("DE_TEST_CLICKHOUSE_PASSWORD", "pass")
    monkeypatch.setenv("DE_TEST_CLICKHOUSE_TABLE", "fees_decisions")
    monkeypatch.setenv("DE_TEST_ELASTICSEARCH_URL", "https://elastic.example.com:443")
    monkeypatch.setenv("DE_TEST_ELASTICSEARCH_API_KEY", "elastic-key")
    monkeypatch.setenv("DE_TEST_NEO4J_URI", "neo4j+s://graph.example.com")
    monkeypatch.setenv("DE_TEST_NEO4J_USERNAME", "neo4j")
    monkeypatch.setenv("DE_TEST_NEO4J_PASSWORD", "pass")
    monkeypatch.setenv("DE_TEST_SNOWFLAKE_ACCOUNT", "acct")
    monkeypatch.setenv("DE_TEST_SNOWFLAKE_USER", "user")
    monkeypatch.setenv("DE_TEST_SNOWFLAKE_PASSWORD", "pass")
    monkeypatch.setenv("DE_TEST_SNOWFLAKE_WAREHOUSE", "wh")
    monkeypatch.setenv("DE_TEST_SNOWFLAKE_TABLE", "NATION")
    monkeypatch.setenv("DE_TEST_BIGQUERY_PROJECT_ID", "proj")
    monkeypatch.setenv(
        "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON",
        '{"type":"service_account","project_id":"proj"}',
    )
    monkeypatch.setenv("DE_TEST_BIGQUERY_DATASET", "samples")
    monkeypatch.setenv("DE_TEST_BIGQUERY_TABLE", "shakespeare")
    monkeypatch.setenv("DE_TEST_ORACLE_USER", "reader")
    monkeypatch.setenv("DE_TEST_ORACLE_PASSWORD", "pass")
    monkeypatch.setenv("DE_TEST_ORACLE_DSN", "oracle.example.com:1521/analytics")
    monkeypatch.setenv("DE_TEST_ORACLE_HOST", "oracle.example.com")
    monkeypatch.setenv("DE_TEST_ORACLE_TABLE", "REPORTING.FACTS")

    failures = collect_requirement_failures(
        collect_matrix_status(ALL_CONNECTOR_VALIDATION_CASES),
        require_all_configured=True,
        require_all_behavior_ready=True,
    )

    assert failures == []
