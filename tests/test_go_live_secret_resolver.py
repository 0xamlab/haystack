from __future__ import annotations

from pathlib import Path

from tests import go_live_secret_resolver as resolver


def test_describe_go_live_env_resolution_reports_alias_backed_envs() -> None:
    description = resolver.describe_go_live_env_resolution("DE_TEST_REDIS_URL")

    assert description == {
        "canonical_name": "DE_TEST_REDIS_URL",
        "resolver_supported": True,
        "manual_only": False,
        "fallback_aliases": ["REDIS_URL"],
        "candidate_names": ["DE_TEST_REDIS_URL", "REDIS_URL"],
        "group_name": "redis",
    }


def test_describe_go_live_env_resolution_reports_manual_only_envs() -> None:
    description = resolver.describe_go_live_env_resolution("DE_ENABLE_SLOW_PUBLIC_REST_CASES")

    assert description == {
        "canonical_name": "DE_ENABLE_SLOW_PUBLIC_REST_CASES",
        "resolver_supported": False,
        "manual_only": True,
        "fallback_aliases": [],
        "candidate_names": ["DE_ENABLE_SLOW_PUBLIC_REST_CASES"],
        "group_name": None,
    }


def test_populate_go_live_test_env_from_keys_txt_uses_aliases_without_overriding_explicit_env(
    monkeypatch,
    tmp_path: Path,
) -> None:
    keys_path = tmp_path / "keys.txt"
    keys_path.write_text(
        "\n".join(
            [
                "FRED_API_KEY=fred-from-keys",
                "GITHUB_TOKEN=github-from-keys",
                "SNOWFLAKE_ACCOUNT=snow-account",
                "SNOWFLAKE_USER=snow-user",
                "SNOWFLAKE_PASSWORD=snow-pass",
                "SNOWFLAKE_WAREHOUSE=snow-wh",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DE_TEST_FRED_API_KEY", raising=False)
    monkeypatch.delenv("DE_TEST_SNOWFLAKE_ACCOUNT", raising=False)
    monkeypatch.delenv("DE_TEST_SNOWFLAKE_USER", raising=False)
    monkeypatch.delenv("DE_TEST_SNOWFLAKE_PASSWORD", raising=False)
    monkeypatch.delenv("DE_TEST_SNOWFLAKE_WAREHOUSE", raising=False)
    monkeypatch.setenv("DE_TEST_GITHUB_TOKEN", "explicit-gh")

    applied = resolver.populate_go_live_test_env_from_keys_txt(keys_path=keys_path)

    assert applied["DE_TEST_FRED_API_KEY"] == "fred-from-keys"
    assert applied["DE_TEST_SNOWFLAKE_ACCOUNT"] == "snow-account"
    assert "DE_TEST_GITHUB_TOKEN" not in applied
    assert resolver.os.environ["DE_TEST_GITHUB_TOKEN"] == "explicit-gh"
    assert resolver.os.environ["DE_TEST_SNOWFLAKE_WAREHOUSE"] == "snow-wh"


def test_populate_go_live_test_env_from_keys_txt_reads_file_backed_json_values(
    monkeypatch,
    tmp_path: Path,
) -> None:
    credentials_path = tmp_path / "service-account.json"
    credentials_path.write_text(
        '{"type":"service_account","project_id":"algenta-test"}',
        encoding="utf-8",
    )
    keys_path = tmp_path / "keys.txt"
    keys_path.write_text(
        f"GOOGLE_APPLICATION_CREDENTIALS={credentials_path}\nBIGQUERY_PROJECT_ID=algenta-test\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("DE_TEST_BIGQUERY_PROJECT_ID", raising=False)

    applied = resolver.populate_go_live_test_env_from_keys_txt(keys_path=keys_path)

    assert applied["DE_TEST_BIGQUERY_PROJECT_ID"] == "algenta-test"
    assert (
        applied["DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON"]
        == '{"type":"service_account","project_id":"algenta-test"}'
    )


def test_populate_go_live_test_env_from_keys_txt_requires_minimum_group_fields(
    monkeypatch,
    tmp_path: Path,
) -> None:
    keys_path = tmp_path / "keys.txt"
    keys_path.write_text(
        "\n".join(
            [
                "AWS_ACCESS_KEY_ID=aws-key",
                "AWS_SECRET_ACCESS_KEY=aws-secret",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DE_TEST_S3_BUCKET", raising=False)
    monkeypatch.delenv("DE_TEST_S3_KEY", raising=False)
    monkeypatch.delenv("DE_TEST_S3_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("DE_TEST_S3_SECRET_ACCESS_KEY", raising=False)

    applied = resolver.populate_go_live_test_env_from_keys_txt(keys_path=keys_path)

    assert "DE_TEST_S3_ACCESS_KEY_ID" not in applied
    assert "DE_TEST_S3_SECRET_ACCESS_KEY" not in applied


def test_populate_go_live_test_env_from_keys_txt_accepts_snowflake_pat_alias(
    monkeypatch,
    tmp_path: Path,
) -> None:
    keys_path = tmp_path / "keys.txt"
    keys_path.write_text(
        "\n".join(
            [
                "SNOWFLAKE_ACCOUNT=snow-account",
                "SNOWFLAKE_USER=snow-user",
                "SNOWFLAKE_PAT=snow-pat",
                "SNOWFLAKE_WAREHOUSE=compute_wh",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DE_TEST_SNOWFLAKE_ACCOUNT", raising=False)
    monkeypatch.delenv("DE_TEST_SNOWFLAKE_USER", raising=False)
    monkeypatch.delenv("DE_TEST_SNOWFLAKE_PASSWORD", raising=False)
    monkeypatch.delenv("DE_TEST_SNOWFLAKE_WAREHOUSE", raising=False)

    applied = resolver.populate_go_live_test_env_from_keys_txt(keys_path=keys_path)

    assert applied["DE_TEST_SNOWFLAKE_ACCOUNT"] == "snow-account"
    assert applied["DE_TEST_SNOWFLAKE_USER"] == "snow-user"
    assert applied["DE_TEST_SNOWFLAKE_PASSWORD"] == "snow-pat"
    assert applied["DE_TEST_SNOWFLAKE_WAREHOUSE"] == "compute_wh"


def test_populate_go_live_test_env_from_keys_txt_accepts_oracle_aliases(
    monkeypatch,
    tmp_path: Path,
) -> None:
    keys_path = tmp_path / "keys.txt"
    keys_path.write_text(
        "\n".join(
            [
                "ORACLE_USER=reader",
                "ORACLE_PASSWORD=oracle-pass",
                "ORACLE_DSN=analytics_low",
                "ORACLE_HOST=adb.example.oraclecloud.com",
                "ORACLE_PORT=1522",
                "TNS_ADMIN=/secure/oracle-wallet",
                "ORACLE_WALLET_LOCATION=/secure/oracle-wallet",
                "ORACLE_WALLET_PASSWORD=wallet-pass",
                "ORACLE_TABLE=REPORTING.FACTS",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    for name in resolver._GROUP_MEMBERS["oracle"]:
        monkeypatch.delenv(name, raising=False)

    applied = resolver.populate_go_live_test_env_from_keys_txt(keys_path=keys_path)

    assert applied["DE_TEST_ORACLE_USER"] == "reader"
    assert applied["DE_TEST_ORACLE_PASSWORD"] == "oracle-pass"
    assert applied["DE_TEST_ORACLE_DSN"] == "analytics_low"
    assert applied["DE_TEST_ORACLE_HOST"] == "adb.example.oraclecloud.com"
    assert applied["DE_TEST_ORACLE_CONFIG_DIR"] == "/secure/oracle-wallet"
    assert applied["DE_TEST_ORACLE_TABLE"] == "REPORTING.FACTS"


def test_populate_go_live_test_env_accepts_oracle_easy_connect_without_host(
    monkeypatch,
    tmp_path: Path,
) -> None:
    keys_path = tmp_path / "keys.txt"
    keys_path.write_text(
        "ORACLE_USER=reader\n"
        "ORACLE_PASSWORD=oracle-pass\n"
        "ORACLE_DSN=oracle.example.com:1521/analytics\n",
        encoding="utf-8",
    )
    for name in resolver._GROUP_MEMBERS["oracle"]:
        monkeypatch.delenv(name, raising=False)

    applied = resolver.populate_go_live_test_env_from_keys_txt(keys_path=keys_path)

    assert applied["DE_TEST_ORACLE_DSN"] == "oracle.example.com:1521/analytics"
    assert "DE_TEST_ORACLE_HOST" not in applied


def test_populate_go_live_test_env_from_keys_txt_accepts_clickhouse_aliases(
    monkeypatch,
    tmp_path: Path,
) -> None:
    keys_path = tmp_path / "keys.txt"
    keys_path.write_text(
        "\n".join(
            [
                "CLICKHOUSE_URL=https://clickhouse.example.com:8443",
                "CLICKHOUSE_USER=default",
                "CLICKHOUSE_PASSWORD=click-pass",
                "CLICKHOUSE_DATABASE=default",
                "CLICKHOUSE_TABLE=fees_decisions",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DE_TEST_CLICKHOUSE_URL", raising=False)
    monkeypatch.delenv("DE_TEST_CLICKHOUSE_USER", raising=False)
    monkeypatch.delenv("DE_TEST_CLICKHOUSE_PASSWORD", raising=False)
    monkeypatch.delenv("DE_TEST_CLICKHOUSE_DATABASE", raising=False)
    monkeypatch.delenv("DE_TEST_CLICKHOUSE_TABLE", raising=False)

    applied = resolver.populate_go_live_test_env_from_keys_txt(keys_path=keys_path)

    assert applied["DE_TEST_CLICKHOUSE_URL"] == "https://clickhouse.example.com:8443"
    assert applied["DE_TEST_CLICKHOUSE_USER"] == "default"
    assert applied["DE_TEST_CLICKHOUSE_PASSWORD"] == "click-pass"
    assert applied["DE_TEST_CLICKHOUSE_DATABASE"] == "default"
    assert applied["DE_TEST_CLICKHOUSE_TABLE"] == "fees_decisions"


def test_populate_go_live_test_env_from_keys_txt_accepts_redis_alias(
    monkeypatch,
    tmp_path: Path,
) -> None:
    keys_path = tmp_path / "keys.txt"
    keys_path.write_text(
        "REDIS_URL=redis://default:pass@redis.example.com:15638/0\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DE_TEST_REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)

    applied = resolver.populate_go_live_test_env_from_keys_txt(keys_path=keys_path)

    assert applied["DE_TEST_REDIS_URL"] == "redis://default:pass@redis.example.com:15638/0"


def test_populate_go_live_test_env_from_keys_txt_ignores_redis_alias_without_auth(
    monkeypatch,
    tmp_path: Path,
) -> None:
    keys_path = tmp_path / "keys.txt"
    keys_path.write_text(
        "REDIS_URL=redis://localhost:6379/0\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DE_TEST_REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)

    applied = resolver.populate_go_live_test_env_from_keys_txt(keys_path=keys_path)

    assert "DE_TEST_REDIS_URL" not in applied


def test_populate_go_live_test_env_from_keys_txt_accepts_elasticsearch_aliases(
    monkeypatch,
    tmp_path: Path,
) -> None:
    keys_path = tmp_path / "keys.txt"
    keys_path.write_text(
        "\n".join(
            [
                "ELASTICSEARCH_URL=https://elastic.example.com:443",
                "ELASTICSEARCH_API_KEY=elastic-key",
                "ELASTICSEARCH_INDEX=market_data_parts_aar",
                'ELASTICSEARCH_QUERY={"query":{"match_all":{}}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DE_TEST_ELASTICSEARCH_URL", raising=False)
    monkeypatch.delenv("DE_TEST_ELASTICSEARCH_API_KEY", raising=False)
    monkeypatch.delenv("DE_TEST_ELASTICSEARCH_INDEX", raising=False)
    monkeypatch.delenv("DE_TEST_ELASTICSEARCH_QUERY", raising=False)

    applied = resolver.populate_go_live_test_env_from_keys_txt(keys_path=keys_path)

    assert applied["DE_TEST_ELASTICSEARCH_URL"] == "https://elastic.example.com:443"
    assert applied["DE_TEST_ELASTICSEARCH_API_KEY"] == "elastic-key"
    assert applied["DE_TEST_ELASTICSEARCH_INDEX"] == "market_data_parts_aar"
    assert applied["DE_TEST_ELASTICSEARCH_QUERY"] == '{"query":{"match_all":{}}}'


def test_populate_go_live_test_env_from_keys_txt_accepts_neo4j_aliases(
    monkeypatch,
    tmp_path: Path,
) -> None:
    keys_path = tmp_path / "keys.txt"
    keys_path.write_text(
        "\n".join(
            [
                "NEO4J_URI=neo4j+s://graph.example.com",
                "NEO4J_USERNAME=neo4j",
                "NEO4J_PASSWORD=neo4j-pass",
                "NEO4J_DATABASE=neo4j",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DE_TEST_NEO4J_URI", raising=False)
    monkeypatch.delenv("DE_TEST_NEO4J_USERNAME", raising=False)
    monkeypatch.delenv("DE_TEST_NEO4J_PASSWORD", raising=False)
    monkeypatch.delenv("DE_TEST_NEO4J_DATABASE", raising=False)

    applied = resolver.populate_go_live_test_env_from_keys_txt(keys_path=keys_path)

    assert applied["DE_TEST_NEO4J_URI"] == "neo4j+s://graph.example.com"
    assert applied["DE_TEST_NEO4J_USERNAME"] == "neo4j"
    assert applied["DE_TEST_NEO4J_PASSWORD"] == "neo4j-pass"
    assert applied["DE_TEST_NEO4J_DATABASE"] == "neo4j"
