from __future__ import annotations

import pytest

from apps.privacy_policy import (
    PrivacyConfigurationError,
    build_privacy_policy,
    evaluate_egress,
    policy_from_environment,
    redact_destination_host,
)


def test_self_hosted_defaults_to_private_local_audit_profile() -> None:
    policy = build_privacy_policy(deployment_mode="self_hosted")

    assert policy.deployment_mode == "self_hosted"
    assert policy.disable_cloud is True
    assert policy.disable_telemetry is True
    assert policy.telemetry_mode == "local_audit"
    assert policy.metering_mode == "local_audit"
    assert policy.allow_outbound_network is False
    assert policy.require_local_license is False
    assert policy.control_plane_url == ""


def test_privacy_policy_report_includes_canonical_registry() -> None:
    policy = build_privacy_policy(deployment_mode="self_hosted")

    report = policy.as_report_dict()

    assert report["algenta_owned_suffixes"] == list(policy.algenta_owned_suffixes)
    assert report["vendor_telemetry_hosts"] == list(policy.vendor_telemetry_hosts)
    assert report["private_host_suffixes"] == list(policy.private_host_suffixes)
    assert report["privacy_registry"] == {
        "algenta_owned_hosts": list(policy.algenta_owned_hosts),
        "algenta_owned_suffixes": list(policy.algenta_owned_suffixes),
        "vendor_telemetry_hosts": list(policy.vendor_telemetry_hosts),
        "private_host_suffixes": list(policy.private_host_suffixes),
    }


def test_air_gapped_forbids_control_plane_sync() -> None:
    with pytest.raises(PrivacyConfigurationError, match="air_gapped"):
        build_privacy_policy(
            deployment_mode="air_gapped",
            telemetry_mode="control_plane_sync",
            control_plane_url="https://control.customer.internal",
            egress_allowlist="control.customer.internal",
        )


def test_egress_policy_allows_explicit_allowlisted_customer_connector_targets() -> None:
    policy = build_privacy_policy(
        deployment_mode="self_hosted",
        egress_allowlist="postgres.internal:5432,*.customer.internal",
    )

    allow_exact = evaluate_egress(
        policy,
        "postgres.internal:5432",
        surface="connector_test",
        service_name="api-server",
        explicit_configured=True,
        egress_class="customer_connector",
    )
    allow_suffix = evaluate_egress(
        policy,
        "https://warehouse.customer.internal/query",
        surface="connector_test",
        service_name="api-server",
        explicit_configured=True,
        egress_class="customer_connector",
    )
    deny_public = evaluate_egress(
        policy,
        "https://example.com/report.csv",
        surface="connector_test",
        service_name="api-server",
        explicit_configured=True,
        egress_class="customer_connector",
    )
    deny_undeclared = evaluate_egress(
        policy,
        "https://example.com/report.csv",
        surface="connector_test",
        service_name="api-server",
        explicit_configured=False,
    )

    assert allow_exact.decision == "allow"
    assert allow_exact.reason == "destination_allowlisted"
    assert allow_suffix.decision == "allow"
    assert deny_public.decision == "deny"
    assert deny_public.reason == "destination_not_allowlisted"
    assert deny_undeclared.decision == "deny"
    assert deny_undeclared.reason == "undeclared_public_egress_disabled"


def test_allowlisted_customer_connector_takes_precedence_over_global_outbound_reason() -> None:
    policy = build_privacy_policy(
        deployment_mode="saas",
        allow_outbound_network=True,
        egress_allowlist="127.0.0.1,*.customer.internal",
    )

    allow_loopback = evaluate_egress(
        policy,
        "http://127.0.0.1:8765/fixture.csv",
        surface="connector_test",
        service_name="api-server",
        explicit_configured=True,
        egress_class="customer_connector",
    )
    allow_suffix = evaluate_egress(
        policy,
        "https://warehouse.customer.internal/query",
        surface="connector_test",
        service_name="api-server",
        explicit_configured=True,
        egress_class="customer_connector",
    )

    assert allow_loopback.decision == "allow"
    assert allow_loopback.reason == "destination_allowlisted"
    assert allow_suffix.decision == "allow"
    assert allow_suffix.reason == "destination_allowlisted"


def test_control_plane_sync_requires_permitted_control_plane_url() -> None:
    with pytest.raises(PrivacyConfigurationError, match="control_plane_sync"):
        build_privacy_policy(
            deployment_mode="vpc",
            allow_outbound_network=False,
            telemetry_mode="control_plane_sync",
            control_plane_url="https://control.customer.internal",
        )


def test_policy_from_environment_accepts_algenta_api_url_for_private_profiles() -> None:
    policy = policy_from_environment(
        {
            "ALGENTA_DEPLOYMENT_MODE": "self_hosted",
            "ALGENTA_API_URL": "https://decision.customer.internal",
        }
    )

    assert policy.control_plane_url == "https://decision.customer.internal"


def test_redact_destination_host_treats_home_arpa_as_internal() -> None:
    assert redact_destination_host("gateway.home.arpa") == "internal-host"
