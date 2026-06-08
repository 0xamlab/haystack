from __future__ import annotations

import pytest

from apps.operator_http.privacy import (
    resolve_operator_api_base_url,
    validate_operator_api_base_url,
)


def test_resolve_operator_api_base_url_requires_explicit_origin_in_private_profile() -> None:
    env = {"ALGENTA_DEPLOYMENT_MODE": "self_hosted"}

    with pytest.raises(ValueError, match="require an explicit self-hosted API origin"):
        resolve_operator_api_base_url(
            saved_base_url=None,
            env=env,
            surface="CLI",
        )


def test_resolve_operator_console_base_url_requires_explicit_origin_in_private_profile() -> None:
    from apps.operator_http.privacy import resolve_operator_console_base_url

    env = {"ALGENTA_DEPLOYMENT_MODE": "self_hosted"}

    with pytest.raises(ValueError, match="require an explicit self-hosted dashboard or API origin"):
        resolve_operator_console_base_url(
            env=env,
            surface="CLI dashboard",
        )


def test_validate_operator_api_base_url_rejects_algenta_cloud_for_private_profiles() -> None:
    env = {
        "ALGENTA_DEPLOYMENT_MODE": "self_hosted",
        "DE_BASE_URL": "https://api.algenta.ai",
    }

    with pytest.raises(
        ValueError,
        match="ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL",
    ):
        validate_operator_api_base_url(
            "https://api.algenta.ai",
            env=env,
            surface="CLI",
        )


def test_validate_operator_api_base_url_allows_internal_targets_without_allowlist() -> None:
    env = {"ALGENTA_DEPLOYMENT_MODE": "self_hosted"}

    assert (
        validate_operator_api_base_url(
            "http://api.internal:8000",
            env=env,
            surface="CLI",
        )
        == "http://api.internal:8000"
    )


def test_validate_operator_api_base_url_allows_corp_suffix_without_allowlist() -> None:
    env = {"ALGENTA_DEPLOYMENT_MODE": "self_hosted"}

    assert (
        validate_operator_api_base_url(
            "https://api.customer.corp",
            env=env,
            surface="CLI",
        )
        == "https://api.customer.corp"
    )


def test_validate_operator_api_base_url_allows_allowlisted_public_customer_origin() -> None:
    env = {
        "ALGENTA_DEPLOYMENT_MODE": "self_hosted",
        "ALGENTA_EGRESS_ALLOWLIST": "api.customer.example",
    }

    assert (
        validate_operator_api_base_url(
            "https://api.customer.example",
            env=env,
            surface="CLI",
        )
        == "https://api.customer.example"
    )


def test_validate_operator_api_base_url_rejects_unallowlisted_public_customer_origin() -> None:
    env = {"ALGENTA_DEPLOYMENT_MODE": "self_hosted"}

    with pytest.raises(ValueError, match="allowlisted customer origin"):
        validate_operator_api_base_url(
            "https://api.customer.example",
            env=env,
            surface="CLI",
        )
