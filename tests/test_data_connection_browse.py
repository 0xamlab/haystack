import pytest

from apps.api_server.config import get_settings
from apps.api_server.services import data_connection_browse as browse
from apps.api_server.services import data_connection_browse_sql as browse_sql
from apps.api_server.services import data_connection_specs as specs
from apps.api_server.services.egress_guard import EgressPolicyDeniedError


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_data_connection_browse_sql_leaf_builds_clickhouse_connection_string() -> None:
    connection_string = browse_sql._build_database_connection_string(
        "clickhouse",
        {
            "connection_string": "https://default:pass@clickhouse.example.com:8443/default",
        },
    )

    assert connection_string == (
        "clickhouse://default:pass@clickhouse.example.com:8443/default?secure=true"
    )


def test_data_connection_specs_reexports_browse_helpers() -> None:
    assert browse._build_database_connection_string is browse_sql._build_database_connection_string
    assert specs._build_database_connection_string is browse_sql._build_database_connection_string
    assert specs._browse_sql is browse_sql._browse_sql
    assert specs.browse_connector_real is browse.browse_connector_real
    assert specs.browse_connector_real_detailed is browse.browse_connector_real_detailed
    assert specs._clear_browse_result_cache is browse._clear_browse_result_cache


@pytest.mark.anyio
async def test_browse_sql_blocks_unallowlisted_postgres_target_in_self_hosted_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def _unexpected_create_engine(*args, **kwargs):
        create_calls.append((args, kwargs))
        raise AssertionError("create_engine should not run when browse egress is blocked")

    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_ALLOW_OUTBOUND_NETWORK", "0")
    monkeypatch.delenv("ALGENTA_EGRESS_ALLOWLIST", raising=False)
    monkeypatch.setattr("sqlalchemy.create_engine", _unexpected_create_engine)

    with pytest.raises(EgressPolicyDeniedError, match="privacy policy"):
        await browse_sql._browse_sql(
            {
                "connection_string": "postgresql://reader:secret@warehouse.customer.example:5432/analytics",
            },
            provider="postgres",
        )

    assert create_calls == []
