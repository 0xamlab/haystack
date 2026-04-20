from __future__ import annotations

from tests.integration.connector_validation_catalog import THIRD_PARTY_PUBLIC_CASES


def test_third_party_connector_validation_catalog_has_unique_case_ids() -> None:
    case_ids = [case.case_id for case in THIRD_PARTY_PUBLIC_CASES]
    assert len(case_ids) == len(set(case_ids))


def test_third_party_connector_validation_catalog_covers_expected_ecosystems() -> None:
    ecosystems = {case.ecosystem for case in THIRD_PARTY_PUBLIC_CASES}
    assert ecosystems == {"dlt", "fivetran"}


def test_third_party_connector_validation_catalog_uses_real_public_register_and_query_cases() -> None:
    assert THIRD_PARTY_PUBLIC_CASES
    for case in THIRD_PARTY_PUBLIC_CASES:
        assert case.tier == "public_no_auth"
        assert case.validation_mode == "register_and_exact_query"
        assert case.connector_type == "rest_api"
        assert case.connection["type"] == "rest_api"
        assert case.aggregation == "count"
        assert case.docs_url.startswith("https://")
