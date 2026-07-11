from __future__ import annotations

import tests.integration.connector_validation_catalog as catalog
from tests.integration.connector_validation_catalog import (
    ALL_CONNECTOR_VALIDATION_CASES,
    CONNECTOR_VALIDATION_MATRIX,
    CUSTOMER_CREDENTIAL_REQUIRED_CASES,
    PUBLIC_VALIDATION_CASES,
    THIRD_PARTY_TIER2_CASES,
)


def test_connector_validation_catalog_has_unique_case_ids() -> None:
    case_ids = [case.case_id for case in ALL_CONNECTOR_VALIDATION_CASES]
    assert len(case_ids) == len(set(case_ids))


def test_connector_validation_matrix_covers_all_three_tiers() -> None:
    assert set(CONNECTOR_VALIDATION_MATRIX) == {
        "public_no_auth",
        "credentialed_example",
        "customer_credentials_required",
    }
    assert CONNECTOR_VALIDATION_MATRIX["public_no_auth"] == PUBLIC_VALIDATION_CASES
    assert CONNECTOR_VALIDATION_MATRIX["credentialed_example"] == THIRD_PARTY_TIER2_CASES
    assert (
        CONNECTOR_VALIDATION_MATRIX["customer_credentials_required"]
        == CUSTOMER_CREDENTIAL_REQUIRED_CASES
    )


def test_public_connector_validation_cases_use_real_public_register_and_query_configs() -> None:
    assert PUBLIC_VALIDATION_CASES
    ecosystems = {case.ecosystem for case in PUBLIC_VALIDATION_CASES}
    assert ecosystems == {"cloud", "dlt", "fivetran", "pokeapi"}
    assert {
        "public_s3_source_registration",
        "public_gcs_source_registration",
        "public_azure_blob_source_registration",
        "fivetran_noaa_station_kilg",
        "fivetran_npi_registry_number",
        "dlt_pokeapi_pokemon",
        "pokeapi_color_pagination",
        "dlt_github_issues",
    } == {case.case_id for case in PUBLIC_VALIDATION_CASES}
    for case in PUBLIC_VALIDATION_CASES:
        assert case.tier == "public_no_auth"
        assert case.validation_mode == "register_and_exact_query"
        assert case.behavior_mode in {"immutable", "mutable_rest"}
        assert case.build_connection()["type"] == case.connector_type
        assert case.aggregation == "count"
        assert case.enabled_by_default is True
        assert case.required_env_vars == ()
        if case.behavior_mode == "immutable":
            assert case.value_drift_mode == "strict_sample_hash"
        else:
            assert case.value_drift_mode == "distribution_sketch"
        if case.docs_url:
            assert case.docs_url.startswith("https://")


def test_tier2_connector_validation_cases_require_fixture_credentials() -> None:
    assert THIRD_PARTY_TIER2_CASES
    for case in THIRD_PARTY_TIER2_CASES:
        assert case.tier == "credentialed_example"
        assert case.validation_mode == "register_and_exact_query"
        assert case.behavior_mode == "mutable_rest"
        assert case.connector_type == "rest_api"
        assert case.enabled_by_default is False
        assert case.required_env_vars
        assert case.negative_probe == "invalid_auth"
        assert case.value_drift_mode == "distribution_sketch"
        assert case.docs_url.startswith("https://")
        assert case.build_connection()["type"] == "rest_api"


def test_tier3_connector_validation_cases_are_live_only_validations() -> None:
    assert CUSTOMER_CREDENTIAL_REQUIRED_CASES
    assert {
        "customer_s3_source_registration",
        "customer_gcs_source_registration",
        "customer_azure_blob_source_registration",
        "redis_customer_connector_test",
        "clickhouse_customer_connector_test",
        "elasticsearch_customer_connector_test",
        "neo4j_customer_connector_test",
        "oracle_customer_connector_test",
        "snowflake_customer_connector_test",
        "bigquery_customer_connector_test",
    } == {case.case_id for case in CUSTOMER_CREDENTIAL_REQUIRED_CASES}
    for case in CUSTOMER_CREDENTIAL_REQUIRED_CASES:
        assert case.tier == "customer_credentials_required"
        assert case.enabled_by_default is False
        assert case.required_env_vars or case.availability_check is not None
        if case.validation_mode == "connector_test_only":
            assert case.behavior_mode == "connector_test_only"
            assert case.build_connector_config()
            if case.connector_type == "redis":
                assert case.required_env_vars == ("DE_TEST_REDIS_URL",)
                assert case.behavior_validation_mode is None
            if case.connector_type == "neo4j":
                assert case.required_env_vars == (
                    "DE_TEST_NEO4J_URI",
                    "DE_TEST_NEO4J_USERNAME",
                    "DE_TEST_NEO4J_PASSWORD",
                )
                assert case.behavior_validation_mode is None
            if case.connector_type == "elasticsearch":
                assert case.required_env_vars == (
                    "DE_TEST_ELASTICSEARCH_URL",
                    "DE_TEST_ELASTICSEARCH_API_KEY",
                )
                assert case.behavior_validation_mode is None
            if case.behavior_validation_mode is not None:
                assert case.docs_url.startswith("https://")
        else:
            assert case.validation_mode == "register_and_exact_query"
            assert case.behavior_mode == "immutable"
            assert case.negative_probe == "invalid_path"
            assert case.build_connection()["type"] == case.connector_type


def test_tier3_warehouse_cases_upgrade_to_behavior_validation_when_fixture_envs_exist(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DE_TEST_CLICKHOUSE_URL", "https://clickhouse.example.com:8443")
    monkeypatch.setenv("DE_TEST_CLICKHOUSE_USER", "default")
    monkeypatch.setenv("DE_TEST_CLICKHOUSE_PASSWORD", "pass")
    monkeypatch.setenv("DE_TEST_CLICKHOUSE_TABLE", "fees_decisions")
    monkeypatch.setenv("DE_TEST_SNOWFLAKE_ACCOUNT", "acct")
    monkeypatch.setenv("DE_TEST_SNOWFLAKE_USER", "user")
    monkeypatch.setenv("DE_TEST_SNOWFLAKE_PASSWORD", "pass")
    monkeypatch.setenv("DE_TEST_SNOWFLAKE_WAREHOUSE", "wh")
    monkeypatch.setenv(
        "DE_TEST_SNOWFLAKE_QUERY",
        "SELECT N_NATIONKEY, N_NAME, N_REGIONKEY FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.NATION ORDER BY N_NATIONKEY",
    )
    monkeypatch.setenv("DE_TEST_BIGQUERY_PROJECT_ID", "proj")
    monkeypatch.setenv(
        "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON",
        '{"type":"service_account","project_id":"proj"}',
    )
    monkeypatch.setenv(
        "DE_TEST_BIGQUERY_QUERY",
        "SELECT word, word_count, corpus FROM `bigquery-public-data.samples.shakespeare` ORDER BY word, corpus LIMIT 100",
    )

    cases_by_id = {case.case_id: case for case in CUSTOMER_CREDENTIAL_REQUIRED_CASES}
    clickhouse_case = cases_by_id["clickhouse_customer_connector_test"]
    snowflake_case = cases_by_id["snowflake_customer_connector_test"]
    bigquery_case = cases_by_id["bigquery_customer_connector_test"]

    assert clickhouse_case.supports_behavior_validation() is True
    assert clickhouse_case.effective_validation_mode() == "register_and_exact_query"
    assert clickhouse_case.effective_behavior_mode() == "immutable"
    clickhouse_connection = clickhouse_case.build_runtime_connection()
    assert clickhouse_connection["type"] == "sql"
    assert clickhouse_connection["connection_string"].startswith("clickhouse://")
    assert clickhouse_connection["query"] == (
        "SELECT * FROM `default`.`fees_decisions` ORDER BY 1 LIMIT 100"
    )

    assert snowflake_case.supports_behavior_validation() is True
    assert snowflake_case.effective_validation_mode() == "register_and_exact_query"
    assert snowflake_case.effective_behavior_mode() == "immutable"
    snowflake_connection = snowflake_case.build_runtime_connection()
    assert snowflake_connection["type"] == "sql"
    assert snowflake_connection["connection_string"].startswith("snowflake://")
    assert "SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.NATION" in snowflake_connection["query"]

    assert bigquery_case.supports_behavior_validation() is True
    assert bigquery_case.effective_validation_mode() == "register_and_exact_query"
    assert bigquery_case.effective_behavior_mode() == "immutable"
    bigquery_connection = bigquery_case.build_runtime_connection()
    assert bigquery_connection["type"] == "sql"
    assert bigquery_connection["connection_string"] == "bigquery://proj"
    assert "bigquery-public-data.samples.shakespeare" in bigquery_connection["query"]
    assert snowflake_case.docs_url == "https://docs.snowflake.com/en/user-guide/sample-data-tpch"
    assert bigquery_case.docs_url == "https://cloud.google.com/bigquery/public-data"


def test_tier3_warehouse_cases_remain_connector_test_only_without_fixture_selectors(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DE_TEST_CLICKHOUSE_URL", "https://clickhouse.example.com:8443")
    monkeypatch.setenv("DE_TEST_CLICKHOUSE_USER", "default")
    monkeypatch.setenv("DE_TEST_CLICKHOUSE_PASSWORD", "pass")
    monkeypatch.delenv("DE_TEST_CLICKHOUSE_QUERY", raising=False)
    monkeypatch.delenv("DE_TEST_CLICKHOUSE_TABLE", raising=False)
    monkeypatch.setenv("DE_TEST_SNOWFLAKE_ACCOUNT", "acct")
    monkeypatch.setenv("DE_TEST_SNOWFLAKE_USER", "user")
    monkeypatch.setenv("DE_TEST_SNOWFLAKE_PASSWORD", "pass")
    monkeypatch.setenv("DE_TEST_SNOWFLAKE_WAREHOUSE", "wh")
    monkeypatch.delenv("DE_TEST_SNOWFLAKE_QUERY", raising=False)
    monkeypatch.delenv("DE_TEST_SNOWFLAKE_TABLE", raising=False)
    monkeypatch.setenv("DE_TEST_BIGQUERY_PROJECT_ID", "proj")
    monkeypatch.setenv(
        "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON",
        '{"type":"service_account","project_id":"proj"}',
    )
    monkeypatch.delenv("DE_TEST_BIGQUERY_QUERY", raising=False)
    monkeypatch.delenv("DE_TEST_BIGQUERY_DATASET", raising=False)
    monkeypatch.delenv("DE_TEST_BIGQUERY_TABLE", raising=False)

    cases_by_id = {case.case_id: case for case in CUSTOMER_CREDENTIAL_REQUIRED_CASES}
    clickhouse_case = cases_by_id["clickhouse_customer_connector_test"]
    snowflake_case = cases_by_id["snowflake_customer_connector_test"]
    bigquery_case = cases_by_id["bigquery_customer_connector_test"]

    assert clickhouse_case.supports_behavior_validation() is False
    assert clickhouse_case.effective_validation_mode() == "connector_test_only"
    assert (
        clickhouse_case.behavior_skip_reason()
        == "behavior fixture selector not provided: DE_TEST_CLICKHOUSE_QUERY or DE_TEST_CLICKHOUSE_TABLE"
    )

    assert snowflake_case.supports_behavior_validation() is False
    assert snowflake_case.effective_validation_mode() == "connector_test_only"
    assert (
        snowflake_case.behavior_skip_reason()
        == "behavior fixture selector not provided: DE_TEST_SNOWFLAKE_QUERY or DE_TEST_SNOWFLAKE_TABLE"
    )

    assert bigquery_case.supports_behavior_validation() is False
    assert bigquery_case.effective_validation_mode() == "connector_test_only"
    assert (
        bigquery_case.behavior_skip_reason()
        == "behavior fixture selector not provided: DE_TEST_BIGQUERY_QUERY or DE_TEST_BIGQUERY_DATASET + DE_TEST_BIGQUERY_TABLE"
    )


def test_tier3_warehouse_cases_build_queries_from_table_selectors(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DE_TEST_CLICKHOUSE_URL", "https://clickhouse.example.com:8443")
    monkeypatch.setenv("DE_TEST_CLICKHOUSE_USER", "default")
    monkeypatch.setenv("DE_TEST_CLICKHOUSE_PASSWORD", "pass")
    monkeypatch.setenv("DE_TEST_CLICKHOUSE_TABLE", "fees_decisions")
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

    cases_by_id = {case.case_id: case for case in CUSTOMER_CREDENTIAL_REQUIRED_CASES}
    clickhouse_case = cases_by_id["clickhouse_customer_connector_test"]
    snowflake_case = cases_by_id["snowflake_customer_connector_test"]
    bigquery_case = cases_by_id["bigquery_customer_connector_test"]

    clickhouse_connection = clickhouse_case.build_runtime_connection()
    assert (
        clickhouse_connection["query"]
        == "SELECT * FROM `default`.`fees_decisions` ORDER BY 1 LIMIT 100"
    )

    snowflake_connection = snowflake_case.build_runtime_connection()
    assert (
        snowflake_connection["query"]
        == "SELECT * FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.NATION ORDER BY 1"
    )

    bigquery_connection = bigquery_case.build_runtime_connection()
    assert (
        bigquery_connection["query"]
        == "SELECT * FROM `proj.samples.shakespeare` ORDER BY 1 LIMIT 100"
    )


def test_tier3_oracle_case_builds_wallet_behavior_connection(monkeypatch) -> None:
    wallet_dir = "/secure/oracle-wallet"
    monkeypatch.setenv("DE_TEST_ORACLE_USER", "reader")
    monkeypatch.setenv("DE_TEST_ORACLE_PASSWORD", "database-pass")
    monkeypatch.setenv("DE_TEST_ORACLE_DSN", "analytics_low")
    monkeypatch.setenv("DE_TEST_ORACLE_HOST", "adb.example.oraclecloud.com")
    monkeypatch.setenv("DE_TEST_ORACLE_PORT", "1522")
    monkeypatch.setenv("DE_TEST_ORACLE_CONFIG_DIR", wallet_dir)
    monkeypatch.setenv("DE_TEST_ORACLE_WALLET_LOCATION", wallet_dir)
    monkeypatch.setenv("DE_TEST_ORACLE_WALLET_PASSWORD", "wallet-pass")
    monkeypatch.setenv("DE_TEST_ORACLE_TABLE", "REPORTING.FACTS")

    cases_by_id = {case.case_id: case for case in CUSTOMER_CREDENTIAL_REQUIRED_CASES}
    oracle_case = cases_by_id["oracle_customer_connector_test"]

    assert oracle_case.supports_behavior_validation() is True
    assert oracle_case.effective_validation_mode() == "register_and_exact_query"
    assert oracle_case.build_runtime_connection() == {
        "type": "oracle",
        "user": "reader",
        "password": "database-pass",
        "dsn": "analytics_low",
        "host": "adb.example.oraclecloud.com",
        "port": 1522,
        "config_dir": wallet_dir,
        "wallet_location": wallet_dir,
        "wallet_password": "wallet-pass",
        "query": 'SELECT * FROM "REPORTING"."FACTS" ORDER BY 1',
        "limit": 100,
    }


def test_tier3_oracle_case_rejects_incomplete_wallet_configuration(monkeypatch) -> None:
    monkeypatch.setenv("DE_TEST_ORACLE_USER", "reader")
    monkeypatch.setenv("DE_TEST_ORACLE_PASSWORD", "database-pass")
    monkeypatch.setenv("DE_TEST_ORACLE_DSN", "analytics_low")
    monkeypatch.setenv("DE_TEST_ORACLE_HOST", "adb.example.oraclecloud.com")
    monkeypatch.setenv("DE_TEST_ORACLE_WALLET_LOCATION", "/secure/oracle-wallet")
    monkeypatch.delenv("DE_TEST_ORACLE_WALLET_PASSWORD", raising=False)

    cases_by_id = {case.case_id: case for case in CUSTOMER_CREDENTIAL_REQUIRED_CASES}
    oracle_case = cases_by_id["oracle_customer_connector_test"]

    assert oracle_case.is_configured() is False
    assert oracle_case.skip_reason() == (
        "DE_TEST_ORACLE_WALLET_LOCATION and DE_TEST_ORACLE_WALLET_PASSWORD "
        "must be provided together"
    )


def test_tier3_oracle_case_infers_host_from_easy_connect_dsn(monkeypatch) -> None:
    monkeypatch.setenv("DE_TEST_ORACLE_USER", "reader")
    monkeypatch.setenv("DE_TEST_ORACLE_PASSWORD", "database-pass")
    monkeypatch.setenv("DE_TEST_ORACLE_DSN", "oracle.example.com:1521/analytics")
    monkeypatch.delenv("DE_TEST_ORACLE_HOST", raising=False)

    cases_by_id = {case.case_id: case for case in CUSTOMER_CREDENTIAL_REQUIRED_CASES}
    oracle_case = cases_by_id["oracle_customer_connector_test"]

    assert oracle_case.is_configured() is True
    assert oracle_case.skip_reason() is None


def test_tier3_oracle_case_requires_host_for_tns_alias(monkeypatch) -> None:
    monkeypatch.setenv("DE_TEST_ORACLE_USER", "reader")
    monkeypatch.setenv("DE_TEST_ORACLE_PASSWORD", "database-pass")
    monkeypatch.setenv("DE_TEST_ORACLE_DSN", "analytics_low")
    monkeypatch.setenv("DE_TEST_ORACLE_CONFIG_DIR", "/secure/oracle-wallet")
    monkeypatch.delenv("DE_TEST_ORACLE_HOST", raising=False)

    cases_by_id = {case.case_id: case for case in CUSTOMER_CREDENTIAL_REQUIRED_CASES}
    oracle_case = cases_by_id["oracle_customer_connector_test"]

    assert oracle_case.is_configured() is False
    assert oracle_case.skip_reason() == (
        "TNS alias DSNs require DE_TEST_ORACLE_HOST for egress validation"
    )


def test_load_sql_records_uses_clickhouse_sync_path(monkeypatch) -> None:
    from apps.api_server.connectors.sql_connector import SQLConnector

    captured: dict[str, object] = {}

    def _fake_fetch(
        connection_string: str, query_body: str, limit: int | None
    ) -> list[dict[str, object]]:
        captured["connection_string"] = connection_string
        captured["query_body"] = query_body
        captured["limit"] = limit
        return [{"ok": True}]

    monkeypatch.setattr(
        SQLConnector,
        "_fetch_clickhouse_sync",
        staticmethod(_fake_fetch),
        raising=False,
    )

    records = catalog._load_sql_records(
        {
            "connection_string": "clickhouse://default:secret@clickhouse.example.com:8443/default?secure=true",
            "query": "SELECT trace_id FROM `default`.`execution_outcome_events` ORDER BY trace_id LIMIT 100",
            "limit": 100,
        }
    )

    assert records == [{"ok": True}]
    assert captured["connection_string"]
    assert "execution_outcome_events" in str(captured["query_body"])
    assert captured["limit"] == 100


def test_load_sql_records_uses_snowflake_sync_path(monkeypatch) -> None:
    from apps.api_server.connectors.sql_connector import SQLConnector

    captured: dict[str, object] = {}

    def _fake_fetch(
        connection_string: str, query_body: str, limit: int | None
    ) -> list[dict[str, object]]:
        captured["connection_string"] = connection_string
        captured["query_body"] = query_body
        captured["limit"] = limit
        return [{"ok": True}]

    monkeypatch.setattr(
        SQLConnector,
        "_fetch_snowflake_sync",
        staticmethod(_fake_fetch),
        raising=False,
    )

    records = catalog._load_sql_records(
        {
            "connection_string": "snowflake://user:secret@acct/SNOWFLAKE_SAMPLE_DATA/TPCH_SF1?warehouse=WH",
            "query": "SELECT * FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.NATION ORDER BY 1",
            "limit": 100,
        }
    )

    assert records == [{"ok": True}]
    assert captured["connection_string"]
    assert "TPCH_SF1.NATION" in str(captured["query_body"])
    assert captured["limit"] == 100
