"""Tests for test_go_live_verify: misc_c.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_ad413055-70e-1/tests/test_go_live_verify.py during modularization.
"""
from __future__ import annotations

from tests._test_go_live_verify_helpers import *  # noqa: F401,F403


def test_checked_in_go_live_verify_summary_matches_expected_contract() -> None:
    payload = json.loads(Path("build/go_live_verify_summary.json").read_text())

    assert payload["generated_at"].endswith("Z")
    assert payload["python_executable"]
    assert Path(payload["output_path"]).resolve() == Path("build/go_live_verify_summary.json").resolve()
    assert payload["matrix_summary"] == {
        "total_cases": 19,
        "configured_cases": 8,
        "behavior_ready_cases": 8,
        "tiers": {
            "public_no_auth": {"total": 8, "configured": 7, "behavior_ready": 7},
            "credentialed_example": {"total": 2, "configured": 0, "behavior_ready": 0},
            "customer_credentials_required": {
                "total": 9,
                "configured": 1,
                "behavior_ready": 1,
            },
        },
    }
    assert payload["requirement_failures"] == []
    assert isinstance(payload["static_operational_gaps"], list)
    assert payload["static_operational_gaps"]
    assert payload["gap_source_summary"] == {
        "static_gap_count": 11,
        "live_skip_count": 12,
        "merged_gap_count": 12,
        "live_only_case_ids": ["snowflake_customer_connector_test"],
        "static_only_case_ids": [],
        "merged_case_ids": [
            "bigquery_customer_connector_test",
            "clickhouse_customer_connector_test",
            "customer_azure_blob_source_registration",
            "customer_gcs_source_registration",
            "customer_s3_source_registration",
            "dlt_github_issues",
            "dlt_github_issues_token",
            "elasticsearch_customer_connector_test",
            "fivetran_fred_gnpca",
            "neo4j_customer_connector_test",
            "redis_customer_connector_test",
            "snowflake_customer_connector_test",
        ],
        "static_gap_counts_by_tier": {
            "credentialed_example": 2,
            "customer_credentials_required": 8,
            "public_no_auth": 1,
        },
        "static_gap_counts_by_connector_type": {
            "azure_blob": 1,
            "bigquery": 1,
            "clickhouse": 1,
            "elasticsearch": 1,
            "gcs": 1,
            "neo4j": 1,
            "redis": 1,
            "rest_api": 3,
            "s3": 1,
        },
        "live_skip_counts_by_tier": {
            "credentialed_example": 2,
            "customer_credentials_required": 9,
            "public_no_auth": 1,
        },
        "live_skip_counts_by_connector_type": {
            "azure_blob": 1,
            "bigquery": 1,
            "clickhouse": 1,
            "elasticsearch": 1,
            "gcs": 1,
            "neo4j": 1,
            "redis": 1,
            "rest_api": 3,
            "s3": 1,
            "snowflake": 1,
        },
        "merged_gap_counts_by_tier": {
            "credentialed_example": 2,
            "customer_credentials_required": 9,
            "public_no_auth": 1,
        },
        "merged_gap_counts_by_connector_type": {
            "azure_blob": 1,
            "bigquery": 1,
            "clickhouse": 1,
            "elasticsearch": 1,
            "gcs": 1,
            "neo4j": 1,
            "redis": 1,
            "rest_api": 3,
            "s3": 1,
            "snowflake": 1,
        },
        "merged_gap_counts_by_source": {
            "live_connectivity": 1,
            "static_matrix+live_connectivity": 11,
        },
    }
    assert isinstance(payload["operational_gaps"], list)
    assert payload["operational_gaps"]
    assert isinstance(payload["live_connectivity_skips"], list)
    assert payload["live_connectivity_skips"]
    assert isinstance(payload["next_actions"], list)
    assert payload["next_actions"]
    static_gap_case_ids = [item["case_id"] for item in payload["static_operational_gaps"]]
    assert "snowflake_customer_connector_test" not in static_gap_case_ids
    live_skip_case_ids = [item["case_id"] for item in payload["live_connectivity_skips"]]
    assert "snowflake_customer_connector_test" in live_skip_case_ids
    operational_gap_index = {item["case_id"]: item for item in payload["operational_gaps"]}
    assert operational_gap_index["snowflake_customer_connector_test"]["source"] == "live_connectivity"
    assert operational_gap_index["snowflake_customer_connector_test"]["sources"] == [
        "live_connectivity"
    ]
    assert operational_gap_index["snowflake_customer_connector_test"]["static_reason"] is None
    assert operational_gap_index["snowflake_customer_connector_test"]["live_reason"] == (
        "Snowflake live validation blocked by account network policy; skipping external customer-credential case."
    )
    assert operational_gap_index["snowflake_customer_connector_test"]["action_codes"] == [
        "resolve_network_policy_blockers"
    ]
    assert operational_gap_index["dlt_github_issues"]["source"] == (
        "static_matrix+live_connectivity"
    )
    assert operational_gap_index["dlt_github_issues"]["sources"] == [
        "static_matrix",
        "live_connectivity",
    ]
    assert operational_gap_index["dlt_github_issues"]["action_codes"] == [
        "enable_opt_in_public_cases"
    ]
    next_action_codes = [item["code"] for item in payload["next_actions"]]
    assert next_action_codes == [
        "enable_opt_in_public_cases",
        "set_credentialed_example_envs",
        "set_customer_connector_envs",
        "resolve_network_policy_blockers",
        "rerun_strict_go_live_gate",
    ]
    assert payload["gap_action_summary"] == {
        "mapped_case_count": 12,
        "unmapped_case_ids": [],
        "action_case_counts": {
            "enable_opt_in_public_cases": 1,
            "resolve_network_policy_blockers": 1,
            "set_credentialed_example_envs": 2,
            "set_customer_connector_envs": 8,
        },
        "action_case_ids": {
            "enable_opt_in_public_cases": ["dlt_github_issues"],
            "resolve_network_policy_blockers": ["snowflake_customer_connector_test"],
            "set_credentialed_example_envs": [
                "dlt_github_issues_token",
                "fivetran_fred_gnpca",
            ],
            "set_customer_connector_envs": [
                "bigquery_customer_connector_test",
                "clickhouse_customer_connector_test",
                "customer_azure_blob_source_registration",
                "customer_gcs_source_registration",
                "customer_s3_source_registration",
                "elasticsearch_customer_connector_test",
                "neo4j_customer_connector_test",
                "redis_customer_connector_test",
            ],
        },
        "action_env_names": {
            "enable_opt_in_public_cases": ["DE_ENABLE_SLOW_PUBLIC_REST_CASES"],
            "set_credentialed_example_envs": [
                "DE_TEST_FRED_API_KEY",
                "DE_TEST_GITHUB_TOKEN",
            ],
            "set_customer_connector_envs": [
                "DE_TEST_AZURE_ACCOUNT_URL",
                "DE_TEST_AZURE_BLOB",
                "DE_TEST_AZURE_BLOB_URL",
                "DE_TEST_AZURE_CONNECTION_STRING",
                "DE_TEST_AZURE_CONTAINER",
                "DE_TEST_BIGQUERY_PROJECT_ID",
                "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON",
                "DE_TEST_CLICKHOUSE_PASSWORD",
                "DE_TEST_CLICKHOUSE_URL",
                "DE_TEST_CLICKHOUSE_USER",
                "DE_TEST_ELASTICSEARCH_API_KEY",
                "DE_TEST_ELASTICSEARCH_URL",
                "DE_TEST_GCS_BLOB",
                "DE_TEST_GCS_BUCKET",
                "DE_TEST_NEO4J_PASSWORD",
                "DE_TEST_NEO4J_URI",
                "DE_TEST_NEO4J_USERNAME",
                "DE_TEST_REDIS_URL",
                "DE_TEST_S3_BUCKET",
                "DE_TEST_S3_KEY",
            ],
        },
        "action_env_counts": {
            "enable_opt_in_public_cases": 1,
            "set_credentialed_example_envs": 2,
            "set_customer_connector_envs": 20,
        },
        "action_connector_types": {
            "enable_opt_in_public_cases": ["rest_api"],
            "resolve_network_policy_blockers": ["snowflake"],
            "set_credentialed_example_envs": ["rest_api"],
            "set_customer_connector_envs": [
                "azure_blob",
                "bigquery",
                "clickhouse",
                "elasticsearch",
                "gcs",
                "neo4j",
                "redis",
                "s3",
            ],
        },
        "action_connector_counts": {
            "enable_opt_in_public_cases": 1,
            "resolve_network_policy_blockers": 1,
            "set_credentialed_example_envs": 1,
            "set_customer_connector_envs": 8,
        },
        "terminal_action_codes": ["rerun_strict_go_live_gate"],
    }
    assert payload["gap_connector_summary"] == {
        "connector_action_codes": {
            "azure_blob": ["set_customer_connector_envs"],
            "bigquery": ["set_customer_connector_envs"],
            "clickhouse": ["set_customer_connector_envs"],
            "elasticsearch": ["set_customer_connector_envs"],
            "gcs": ["set_customer_connector_envs"],
            "neo4j": ["set_customer_connector_envs"],
            "redis": ["set_customer_connector_envs"],
            "rest_api": [
                "enable_opt_in_public_cases",
                "set_credentialed_example_envs",
            ],
            "s3": ["set_customer_connector_envs"],
            "snowflake": ["resolve_network_policy_blockers"],
        },
        "connector_case_counts": {
            "azure_blob": 1,
            "bigquery": 1,
            "clickhouse": 1,
            "elasticsearch": 1,
            "gcs": 1,
            "neo4j": 1,
            "redis": 1,
            "rest_api": 3,
            "s3": 1,
            "snowflake": 1,
        },
        "connector_case_ids": {
            "azure_blob": ["customer_azure_blob_source_registration"],
            "bigquery": ["bigquery_customer_connector_test"],
            "clickhouse": ["clickhouse_customer_connector_test"],
            "elasticsearch": ["elasticsearch_customer_connector_test"],
            "gcs": ["customer_gcs_source_registration"],
            "neo4j": ["neo4j_customer_connector_test"],
            "redis": ["redis_customer_connector_test"],
            "rest_api": [
                "dlt_github_issues",
                "dlt_github_issues_token",
                "fivetran_fred_gnpca",
            ],
            "s3": ["customer_s3_source_registration"],
            "snowflake": ["snowflake_customer_connector_test"],
        },
        "connector_env_counts": {
            "azure_blob": 5,
            "bigquery": 2,
            "clickhouse": 3,
            "elasticsearch": 2,
            "gcs": 2,
            "neo4j": 3,
            "redis": 1,
            "rest_api": 3,
            "s3": 2,
        },
        "connector_env_names": {
            "azure_blob": [
                "DE_TEST_AZURE_ACCOUNT_URL",
                "DE_TEST_AZURE_BLOB",
                "DE_TEST_AZURE_BLOB_URL",
                "DE_TEST_AZURE_CONNECTION_STRING",
                "DE_TEST_AZURE_CONTAINER",
            ],
            "bigquery": [
                "DE_TEST_BIGQUERY_PROJECT_ID",
                "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON",
            ],
            "clickhouse": [
                "DE_TEST_CLICKHOUSE_PASSWORD",
                "DE_TEST_CLICKHOUSE_URL",
                "DE_TEST_CLICKHOUSE_USER",
            ],
            "elasticsearch": [
                "DE_TEST_ELASTICSEARCH_API_KEY",
                "DE_TEST_ELASTICSEARCH_URL",
            ],
            "gcs": [
                "DE_TEST_GCS_BLOB",
                "DE_TEST_GCS_BUCKET",
            ],
            "neo4j": [
                "DE_TEST_NEO4J_PASSWORD",
                "DE_TEST_NEO4J_URI",
                "DE_TEST_NEO4J_USERNAME",
            ],
            "redis": ["DE_TEST_REDIS_URL"],
            "rest_api": [
                "DE_ENABLE_SLOW_PUBLIC_REST_CASES",
                "DE_TEST_FRED_API_KEY",
                "DE_TEST_GITHUB_TOKEN",
            ],
            "s3": [
                "DE_TEST_S3_BUCKET",
                "DE_TEST_S3_KEY",
            ],
        },
    }
    assert payload["gap_env_summary"] == {
        "env_total_count": 23,
        "shared_env_names": [],
        "tier_env_counts": {
            "credentialed_example": 2,
            "customer_credentials_required": 20,
            "public_no_auth": 1,
        },
        "env_case_counts": {
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES": 1,
            "DE_TEST_AZURE_ACCOUNT_URL": 1,
            "DE_TEST_AZURE_BLOB": 1,
            "DE_TEST_AZURE_BLOB_URL": 1,
            "DE_TEST_AZURE_CONNECTION_STRING": 1,
            "DE_TEST_AZURE_CONTAINER": 1,
            "DE_TEST_BIGQUERY_PROJECT_ID": 1,
            "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON": 1,
            "DE_TEST_CLICKHOUSE_PASSWORD": 1,
            "DE_TEST_CLICKHOUSE_URL": 1,
            "DE_TEST_CLICKHOUSE_USER": 1,
            "DE_TEST_ELASTICSEARCH_API_KEY": 1,
            "DE_TEST_ELASTICSEARCH_URL": 1,
            "DE_TEST_FRED_API_KEY": 1,
            "DE_TEST_GCS_BLOB": 1,
            "DE_TEST_GCS_BUCKET": 1,
            "DE_TEST_GITHUB_TOKEN": 1,
            "DE_TEST_NEO4J_PASSWORD": 1,
            "DE_TEST_NEO4J_URI": 1,
            "DE_TEST_NEO4J_USERNAME": 1,
            "DE_TEST_REDIS_URL": 1,
            "DE_TEST_S3_BUCKET": 1,
            "DE_TEST_S3_KEY": 1,
        },
        "env_case_ids": {
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES": ["dlt_github_issues"],
            "DE_TEST_AZURE_ACCOUNT_URL": ["customer_azure_blob_source_registration"],
            "DE_TEST_AZURE_BLOB": ["customer_azure_blob_source_registration"],
            "DE_TEST_AZURE_BLOB_URL": ["customer_azure_blob_source_registration"],
            "DE_TEST_AZURE_CONNECTION_STRING": ["customer_azure_blob_source_registration"],
            "DE_TEST_AZURE_CONTAINER": ["customer_azure_blob_source_registration"],
            "DE_TEST_BIGQUERY_PROJECT_ID": ["bigquery_customer_connector_test"],
            "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON": ["bigquery_customer_connector_test"],
            "DE_TEST_CLICKHOUSE_PASSWORD": ["clickhouse_customer_connector_test"],
            "DE_TEST_CLICKHOUSE_URL": ["clickhouse_customer_connector_test"],
            "DE_TEST_CLICKHOUSE_USER": ["clickhouse_customer_connector_test"],
            "DE_TEST_ELASTICSEARCH_API_KEY": ["elasticsearch_customer_connector_test"],
            "DE_TEST_ELASTICSEARCH_URL": ["elasticsearch_customer_connector_test"],
            "DE_TEST_FRED_API_KEY": ["fivetran_fred_gnpca"],
            "DE_TEST_GCS_BLOB": ["customer_gcs_source_registration"],
            "DE_TEST_GCS_BUCKET": ["customer_gcs_source_registration"],
            "DE_TEST_GITHUB_TOKEN": ["dlt_github_issues_token"],
            "DE_TEST_NEO4J_PASSWORD": ["neo4j_customer_connector_test"],
            "DE_TEST_NEO4J_URI": ["neo4j_customer_connector_test"],
            "DE_TEST_NEO4J_USERNAME": ["neo4j_customer_connector_test"],
            "DE_TEST_REDIS_URL": ["redis_customer_connector_test"],
            "DE_TEST_S3_BUCKET": ["customer_s3_source_registration"],
            "DE_TEST_S3_KEY": ["customer_s3_source_registration"],
        },
        "env_connector_types": {
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES": ["rest_api"],
            "DE_TEST_AZURE_ACCOUNT_URL": ["azure_blob"],
            "DE_TEST_AZURE_BLOB": ["azure_blob"],
            "DE_TEST_AZURE_BLOB_URL": ["azure_blob"],
            "DE_TEST_AZURE_CONNECTION_STRING": ["azure_blob"],
            "DE_TEST_AZURE_CONTAINER": ["azure_blob"],
            "DE_TEST_BIGQUERY_PROJECT_ID": ["bigquery"],
            "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON": ["bigquery"],
            "DE_TEST_CLICKHOUSE_PASSWORD": ["clickhouse"],
            "DE_TEST_CLICKHOUSE_URL": ["clickhouse"],
            "DE_TEST_CLICKHOUSE_USER": ["clickhouse"],
            "DE_TEST_ELASTICSEARCH_API_KEY": ["elasticsearch"],
            "DE_TEST_ELASTICSEARCH_URL": ["elasticsearch"],
            "DE_TEST_FRED_API_KEY": ["rest_api"],
            "DE_TEST_GCS_BLOB": ["gcs"],
            "DE_TEST_GCS_BUCKET": ["gcs"],
            "DE_TEST_GITHUB_TOKEN": ["rest_api"],
            "DE_TEST_NEO4J_PASSWORD": ["neo4j"],
            "DE_TEST_NEO4J_URI": ["neo4j"],
            "DE_TEST_NEO4J_USERNAME": ["neo4j"],
            "DE_TEST_REDIS_URL": ["redis"],
            "DE_TEST_S3_BUCKET": ["s3"],
            "DE_TEST_S3_KEY": ["s3"],
        },
        "env_connector_counts": {
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES": 1,
            "DE_TEST_AZURE_ACCOUNT_URL": 1,
            "DE_TEST_AZURE_BLOB": 1,
            "DE_TEST_AZURE_BLOB_URL": 1,
            "DE_TEST_AZURE_CONNECTION_STRING": 1,
            "DE_TEST_AZURE_CONTAINER": 1,
            "DE_TEST_BIGQUERY_PROJECT_ID": 1,
            "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON": 1,
            "DE_TEST_CLICKHOUSE_PASSWORD": 1,
            "DE_TEST_CLICKHOUSE_URL": 1,
            "DE_TEST_CLICKHOUSE_USER": 1,
            "DE_TEST_ELASTICSEARCH_API_KEY": 1,
            "DE_TEST_ELASTICSEARCH_URL": 1,
            "DE_TEST_FRED_API_KEY": 1,
            "DE_TEST_GCS_BLOB": 1,
            "DE_TEST_GCS_BUCKET": 1,
            "DE_TEST_GITHUB_TOKEN": 1,
            "DE_TEST_NEO4J_PASSWORD": 1,
            "DE_TEST_NEO4J_URI": 1,
            "DE_TEST_NEO4J_USERNAME": 1,
            "DE_TEST_REDIS_URL": 1,
            "DE_TEST_S3_BUCKET": 1,
            "DE_TEST_S3_KEY": 1,
        },
        "env_action_codes": {
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES": ["enable_opt_in_public_cases"],
            "DE_TEST_AZURE_ACCOUNT_URL": ["set_customer_connector_envs"],
            "DE_TEST_AZURE_BLOB": ["set_customer_connector_envs"],
            "DE_TEST_AZURE_BLOB_URL": ["set_customer_connector_envs"],
            "DE_TEST_AZURE_CONNECTION_STRING": ["set_customer_connector_envs"],
            "DE_TEST_AZURE_CONTAINER": ["set_customer_connector_envs"],
            "DE_TEST_BIGQUERY_PROJECT_ID": ["set_customer_connector_envs"],
            "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON": ["set_customer_connector_envs"],
            "DE_TEST_CLICKHOUSE_PASSWORD": ["set_customer_connector_envs"],
            "DE_TEST_CLICKHOUSE_URL": ["set_customer_connector_envs"],
            "DE_TEST_CLICKHOUSE_USER": ["set_customer_connector_envs"],
            "DE_TEST_ELASTICSEARCH_API_KEY": ["set_customer_connector_envs"],
            "DE_TEST_ELASTICSEARCH_URL": ["set_customer_connector_envs"],
            "DE_TEST_FRED_API_KEY": ["set_credentialed_example_envs"],
            "DE_TEST_GCS_BLOB": ["set_customer_connector_envs"],
            "DE_TEST_GCS_BUCKET": ["set_customer_connector_envs"],
            "DE_TEST_GITHUB_TOKEN": ["set_credentialed_example_envs"],
            "DE_TEST_NEO4J_PASSWORD": ["set_customer_connector_envs"],
            "DE_TEST_NEO4J_URI": ["set_customer_connector_envs"],
            "DE_TEST_NEO4J_USERNAME": ["set_customer_connector_envs"],
            "DE_TEST_REDIS_URL": ["set_customer_connector_envs"],
            "DE_TEST_S3_BUCKET": ["set_customer_connector_envs"],
            "DE_TEST_S3_KEY": ["set_customer_connector_envs"],
        },
        "env_action_counts": {
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES": 1,
            "DE_TEST_AZURE_ACCOUNT_URL": 1,
            "DE_TEST_AZURE_BLOB": 1,
            "DE_TEST_AZURE_BLOB_URL": 1,
            "DE_TEST_AZURE_CONNECTION_STRING": 1,
            "DE_TEST_AZURE_CONTAINER": 1,
            "DE_TEST_BIGQUERY_PROJECT_ID": 1,
            "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON": 1,
            "DE_TEST_CLICKHOUSE_PASSWORD": 1,
            "DE_TEST_CLICKHOUSE_URL": 1,
            "DE_TEST_CLICKHOUSE_USER": 1,
            "DE_TEST_ELASTICSEARCH_API_KEY": 1,
            "DE_TEST_ELASTICSEARCH_URL": 1,
            "DE_TEST_FRED_API_KEY": 1,
            "DE_TEST_GCS_BLOB": 1,
            "DE_TEST_GCS_BUCKET": 1,
            "DE_TEST_GITHUB_TOKEN": 1,
            "DE_TEST_NEO4J_PASSWORD": 1,
            "DE_TEST_NEO4J_URI": 1,
            "DE_TEST_NEO4J_USERNAME": 1,
            "DE_TEST_REDIS_URL": 1,
            "DE_TEST_S3_BUCKET": 1,
            "DE_TEST_S3_KEY": 1,
        },
        "env_tiers": {
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES": ["public_no_auth"],
            "DE_TEST_AZURE_ACCOUNT_URL": ["customer_credentials_required"],
            "DE_TEST_AZURE_BLOB": ["customer_credentials_required"],
            "DE_TEST_AZURE_BLOB_URL": ["customer_credentials_required"],
            "DE_TEST_AZURE_CONNECTION_STRING": ["customer_credentials_required"],
            "DE_TEST_AZURE_CONTAINER": ["customer_credentials_required"],
            "DE_TEST_BIGQUERY_PROJECT_ID": ["customer_credentials_required"],
            "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON": ["customer_credentials_required"],
            "DE_TEST_CLICKHOUSE_PASSWORD": ["customer_credentials_required"],
            "DE_TEST_CLICKHOUSE_URL": ["customer_credentials_required"],
            "DE_TEST_CLICKHOUSE_USER": ["customer_credentials_required"],
            "DE_TEST_ELASTICSEARCH_API_KEY": ["customer_credentials_required"],
            "DE_TEST_ELASTICSEARCH_URL": ["customer_credentials_required"],
            "DE_TEST_FRED_API_KEY": ["credentialed_example"],
            "DE_TEST_GCS_BLOB": ["customer_credentials_required"],
            "DE_TEST_GCS_BUCKET": ["customer_credentials_required"],
            "DE_TEST_GITHUB_TOKEN": ["credentialed_example"],
            "DE_TEST_NEO4J_PASSWORD": ["customer_credentials_required"],
            "DE_TEST_NEO4J_URI": ["customer_credentials_required"],
            "DE_TEST_NEO4J_USERNAME": ["customer_credentials_required"],
            "DE_TEST_REDIS_URL": ["customer_credentials_required"],
            "DE_TEST_S3_BUCKET": ["customer_credentials_required"],
            "DE_TEST_S3_KEY": ["customer_credentials_required"],
        },
    }
    assert payload["gap_env_resolution_summary"] == {
        "resolver_supported_count": 22,
        "manual_only_count": 1,
        "resolver_supported_env_names": [
            "DE_TEST_AZURE_ACCOUNT_URL",
            "DE_TEST_AZURE_BLOB",
            "DE_TEST_AZURE_BLOB_URL",
            "DE_TEST_AZURE_CONNECTION_STRING",
            "DE_TEST_AZURE_CONTAINER",
            "DE_TEST_BIGQUERY_PROJECT_ID",
            "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON",
            "DE_TEST_CLICKHOUSE_PASSWORD",
            "DE_TEST_CLICKHOUSE_URL",
            "DE_TEST_CLICKHOUSE_USER",
            "DE_TEST_ELASTICSEARCH_API_KEY",
            "DE_TEST_ELASTICSEARCH_URL",
            "DE_TEST_FRED_API_KEY",
            "DE_TEST_GCS_BLOB",
            "DE_TEST_GCS_BUCKET",
            "DE_TEST_GITHUB_TOKEN",
            "DE_TEST_NEO4J_PASSWORD",
            "DE_TEST_NEO4J_URI",
            "DE_TEST_NEO4J_USERNAME",
            "DE_TEST_REDIS_URL",
            "DE_TEST_S3_BUCKET",
            "DE_TEST_S3_KEY",
        ],
        "manual_only_env_names": ["DE_ENABLE_SLOW_PUBLIC_REST_CASES"],
        "env_candidate_names": {
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES": ["DE_ENABLE_SLOW_PUBLIC_REST_CASES"],
            "DE_TEST_AZURE_ACCOUNT_URL": [
                "DE_TEST_AZURE_ACCOUNT_URL",
                "AZURE_ACCOUNT_URL",
            ],
            "DE_TEST_AZURE_BLOB": ["DE_TEST_AZURE_BLOB", "AZURE_BLOB"],
            "DE_TEST_AZURE_BLOB_URL": ["DE_TEST_AZURE_BLOB_URL", "AZURE_BLOB_URL"],
            "DE_TEST_AZURE_CONNECTION_STRING": [
                "DE_TEST_AZURE_CONNECTION_STRING",
                "AZURE_CONNECTION_STRING",
            ],
            "DE_TEST_AZURE_CONTAINER": ["DE_TEST_AZURE_CONTAINER", "AZURE_CONTAINER"],
            "DE_TEST_BIGQUERY_PROJECT_ID": [
                "DE_TEST_BIGQUERY_PROJECT_ID",
                "BIGQUERY_PROJECT_ID",
                "GOOGLE_CLOUD_PROJECT",
                "GCP_PROJECT_ID",
            ],
            "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON": [
                "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON",
                "BIGQUERY_SERVICE_ACCOUNT_JSON",
                "GOOGLE_APPLICATION_CREDENTIALS_JSON",
                "GCP_SERVICE_ACCOUNT_JSON",
                "GOOGLE_APPLICATION_CREDENTIALS",
            ],
            "DE_TEST_CLICKHOUSE_PASSWORD": [
                "DE_TEST_CLICKHOUSE_PASSWORD",
                "CLICKHOUSE_PASSWORD",
            ],
            "DE_TEST_CLICKHOUSE_URL": ["DE_TEST_CLICKHOUSE_URL", "CLICKHOUSE_URL"],
            "DE_TEST_CLICKHOUSE_USER": ["DE_TEST_CLICKHOUSE_USER", "CLICKHOUSE_USER"],
            "DE_TEST_ELASTICSEARCH_API_KEY": [
                "DE_TEST_ELASTICSEARCH_API_KEY",
                "ELASTICSEARCH_API_KEY",
                "ELASTIC_API_KEY",
            ],
            "DE_TEST_ELASTICSEARCH_URL": [
                "DE_TEST_ELASTICSEARCH_URL",
                "ELASTICSEARCH_URL",
                "ELASTIC_URL",
            ],
            "DE_TEST_FRED_API_KEY": ["DE_TEST_FRED_API_KEY", "FRED_API_KEY"],
            "DE_TEST_GCS_BLOB": ["DE_TEST_GCS_BLOB", "GCS_BLOB"],
            "DE_TEST_GCS_BUCKET": ["DE_TEST_GCS_BUCKET", "GCS_BUCKET"],
            "DE_TEST_GITHUB_TOKEN": [
                "DE_TEST_GITHUB_TOKEN",
                "GITHUB_TOKEN",
                "GH_TOKEN",
            ],
            "DE_TEST_NEO4J_PASSWORD": ["DE_TEST_NEO4J_PASSWORD", "NEO4J_PASSWORD"],
            "DE_TEST_NEO4J_URI": [
                "DE_TEST_NEO4J_URI",
                "NEO4J_URI",
                "NEO4J_URL",
            ],
            "DE_TEST_NEO4J_USERNAME": [
                "DE_TEST_NEO4J_USERNAME",
                "NEO4J_USERNAME",
                "NEO4J_USER",
            ],
            "DE_TEST_REDIS_URL": ["DE_TEST_REDIS_URL", "REDIS_URL"],
            "DE_TEST_S3_BUCKET": ["DE_TEST_S3_BUCKET", "S3_BUCKET"],
            "DE_TEST_S3_KEY": ["DE_TEST_S3_KEY", "S3_KEY"],
        },
        "env_group_names": {
            "DE_TEST_AZURE_ACCOUNT_URL": "azure_blob",
            "DE_TEST_AZURE_BLOB": "azure_blob",
            "DE_TEST_AZURE_BLOB_URL": "azure_blob",
            "DE_TEST_AZURE_CONNECTION_STRING": "azure_blob",
            "DE_TEST_AZURE_CONTAINER": "azure_blob",
            "DE_TEST_BIGQUERY_PROJECT_ID": "bigquery",
            "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON": "bigquery",
            "DE_TEST_CLICKHOUSE_PASSWORD": "clickhouse",
            "DE_TEST_CLICKHOUSE_URL": "clickhouse",
            "DE_TEST_CLICKHOUSE_USER": "clickhouse",
            "DE_TEST_ELASTICSEARCH_API_KEY": "elasticsearch",
            "DE_TEST_ELASTICSEARCH_URL": "elasticsearch",
            "DE_TEST_GCS_BLOB": "gcs",
            "DE_TEST_GCS_BUCKET": "gcs",
            "DE_TEST_NEO4J_PASSWORD": "neo4j",
            "DE_TEST_NEO4J_URI": "neo4j",
            "DE_TEST_NEO4J_USERNAME": "neo4j",
            "DE_TEST_REDIS_URL": "redis",
            "DE_TEST_S3_BUCKET": "s3",
            "DE_TEST_S3_KEY": "s3",
        },
        "group_env_counts": {
            "azure_blob": 5,
            "bigquery": 2,
            "clickhouse": 3,
            "elasticsearch": 2,
            "gcs": 2,
            "neo4j": 3,
            "redis": 1,
            "s3": 2,
        },
    }
    assert payload["gap_env_template_summary"] == {
        "gap_env_total_count": 23,
        "all_templates_cover_all_gap_envs": True,
        "template_paths": {
            "go_live_validation_env_example": "tests/integration/go_live_validation.env.example",
            "root_env_example": ".env.example",
        },
        "template_documented_counts": {
            "go_live_validation_env_example": 23,
            "root_env_example": 23,
        },
        "template_missing_counts": {
            "go_live_validation_env_example": 0,
            "root_env_example": 0,
        },
        "template_missing_env_names": {
            "go_live_validation_env_example": [],
            "root_env_example": [],
        },
        "templates_with_missing_envs": [],
        "missing_in_any_template": [],
    }
    assert payload["filters"] == {"tiers": [], "connectors": []}
    assert payload["options"] == {
        "include_full_real": True,
        "include_pytest": True,
        "require_all_configured": False,
        "require_all_behavior_ready": False,
        "strict": False,
    }
    planned_names = [item["name"] for item in payload["planned_steps"]]
    executed_names = [item["name"] for item in payload["step_results"]]

    assert planned_names == ["connectivity", "full_real", "pytest"]
    assert payload["planned_steps"][0]["command"][:2] == [payload["python_executable"], "-u"]
    assert executed_names == payload["completed_steps"] + payload["failed_steps"]
    assert executed_names
    assert all(float(item["duration_s"]) > 0.0 for item in payload["step_results"])
    for item in payload["step_results"]:
        if item["name"] in payload["completed_steps"]:
            assert item["returncode"] == 0
        else:
            assert item["name"] in payload["failed_steps"]
            assert item["returncode"] != 0


