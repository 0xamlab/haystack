from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.api_server.connectors.base import ConnectorRegistry
from apps.api_server.connectors.oracle_connector import OracleConnector


def _config(**overrides: object) -> dict[str, object]:
    config: dict[str, object] = {
        "user": "ADMIN",
        "password": "secret",
        "dsn": (
            "(description=(address=(protocol=tcps)(port=1522)"
            "(host=adb.example.oraclecloud.com))"
            "(connect_data=(service_name=exampledb_low)))"
        ),
        "wallet_location": "/secure/wallet",
        "wallet_password": "wallet-secret",
        "query": "SELECT ID, AMOUNT FROM ORDERS",
    }
    config.update(overrides)
    return config


def test_oracle_connector_is_automatically_discoverable() -> None:
    assert ConnectorRegistry.get("oracle") is OracleConnector
    assert "oracle" in ConnectorRegistry.available_types()


@pytest.mark.anyio
async def test_oracle_connector_is_advertised_by_connector_types_endpoint() -> None:
    from apps.api_server.routers.connectors import list_connector_types

    response = await list_connector_types(SimpleNamespace())

    assert "oracle" in response["types"]


def test_connection_settings_parse_descriptor_host_and_wallet() -> None:
    settings = OracleConnector.connection_settings(_config())

    assert settings.user == "ADMIN"
    assert settings.host == "adb.example.oraclecloud.com"
    assert settings.port == 1522
    assert settings.wallet_location == "/secure/wallet"


def test_connection_settings_reject_wallet_without_password() -> None:
    with pytest.raises(ValueError, match="wallet_password"):
        OracleConnector.connection_settings(_config(wallet_password=""))


def test_pool_settings_reject_invalid_bounds() -> None:
    with pytest.raises(ValueError, match="pool_max"):
        OracleConnector.pool_settings(_config(pool_min=4, pool_max=2))
    with pytest.raises(ValueError, match="pool_min"):
        OracleConnector.pool_settings(_config(pool_min=-1))


def test_pool_settings_default_to_zero_idle_sessions() -> None:
    settings = OracleConnector.pool_settings(_config())

    assert settings.minimum == 0
    assert settings.maximum == 4
    assert settings.wait_timeout_ms == 2_000


def test_pool_cache_key_is_stable_and_credential_separated() -> None:
    config = _config()
    settings = OracleConnector.connection_settings(config)
    pool_settings = OracleConnector.pool_settings(config)

    first = OracleConnector._pool_cache_key(settings, pool_settings)
    second = OracleConnector._pool_cache_key(settings, pool_settings)
    changed = OracleConnector._pool_cache_key(
        OracleConnector.connection_settings(_config(password="different-secret")),
        pool_settings,
    )

    assert first == second
    assert first != changed
    assert settings.password not in repr(first)
    assert settings.wallet_password not in repr(first)


def test_connect_sync_reuses_bounded_pool_across_queries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import oracledb

    created_pools: list[object] = []

    class _Connection:
        def __init__(self, pool=None) -> None:
            self.pool = pool
            self.closed = False

        def close(self) -> None:
            if self.closed:
                return
            self.closed = True
            if self.pool is not None:
                self.pool.busy -= 1

    class _Pool:
        def __init__(self, kwargs: dict[str, object]) -> None:
            self.kwargs = kwargs
            self.busy = 0
            self.acquire_count = 0
            self.closed = False

        def acquire(self) -> _Connection:
            self.busy += 1
            self.acquire_count += 1
            return _Connection(self)

        def close(self, *, force: bool) -> None:
            assert force is True
            self.closed = True

    def _create_pool(**kwargs):
        pool = _Pool(kwargs)
        created_pools.append(pool)
        return pool

    monkeypatch.setattr(oracledb, "create_pool", _create_pool)
    OracleConnector.close_pools()
    first_config = _config(query="SELECT 1 FROM DUAL")
    second_config = _config(query="SELECT 2 FROM DUAL")
    settings = OracleConnector.connection_settings(first_config)

    first = OracleConnector._connect_sync(settings, first_config)
    second = OracleConnector._connect_sync(settings, second_config)
    first.close()
    second.close()
    third = OracleConnector._connect_sync(settings, first_config)
    third.close()

    assert len(created_pools) == 4
    primary_pool, second_pool, *idle_pools = created_pools
    assert primary_pool.acquire_count == 2
    assert primary_pool.kwargs["min"] == 0
    assert primary_pool.kwargs["max"] == 1
    assert second_pool.acquire_count == 1
    assert second_pool.kwargs["min"] == 0
    assert second_pool.kwargs["max"] == 1
    assert all(pool.acquire_count == 0 for pool in idle_pools)
    cache_key = next(iter(OracleConnector._pool_cache))
    assert "secret" not in repr(cache_key)

    OracleConnector.close_pools()
    assert all(pool.closed is True for pool in created_pools)


def test_pool_cache_capacity_fails_without_unpooled_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _BusyPool:
        busy = 1

        def close(self, *, force: bool) -> None:
            raise AssertionError("busy pools must not be evicted")

    OracleConnector.close_pools()
    monkeypatch.setattr(OracleConnector, "_POOL_CACHE_MAX_SIZE", 1)
    OracleConnector._pool_cache["busy"] = _BusyPool()  # type: ignore[assignment]
    config = _config(user="OTHER")
    settings = OracleConnector.connection_settings(config)

    with pytest.raises(RuntimeError, match="at capacity"):
        OracleConnector._connect_sync(settings, config)

    OracleConnector._pool_cache.clear()


def test_connect_sync_evicts_pool_when_bootstrap_authentication_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import oracledb

    class _Pool:
        busy = 0
        closed = False

        def acquire(self):
            raise RuntimeError("authentication failed")

        def close(self, *, force: bool) -> None:
            assert force is True
            self.closed = True

    pools: list[_Pool] = []

    def _create_pool(**_kwargs):
        pool = _Pool()
        pools.append(pool)
        return pool

    monkeypatch.setattr(oracledb, "create_pool", _create_pool)
    OracleConnector.close_pools()
    config = _config()
    settings = OracleConnector.connection_settings(config)

    with pytest.raises(RuntimeError, match="authentication failed"):
        OracleConnector._connect_sync(settings, config)

    assert OracleConnector._pool_cache == {}
    assert len(pools) == 4
    assert all(pool.closed is True for pool in pools)


def test_bounded_query_is_oracle_compatible_and_rejects_mutation() -> None:
    statement, parameters = OracleConnector._bounded_query("SELECT * FROM ORDERS;", 25)

    assert statement == (
        "SELECT * FROM (SELECT * FROM ORDERS) algenta_source WHERE ROWNUM <= :algenta_limit"
    )
    assert parameters == {"algenta_limit": 25}

    with pytest.raises(ValueError, match="SELECT or WITH"):
        OracleConnector._bounded_query("DELETE FROM ORDERS", None)


def test_fetch_table_uses_arrow_dataframe_batches(monkeypatch: pytest.MonkeyPatch) -> None:
    import pyarrow as pa

    frames = [
        pa.table({"ID": [1, 2], "AMOUNT": [10.0, 20.0]}),
        pa.table({"ID": [3], "AMOUNT": [30.0]}),
    ]

    class _Connection:
        closed = False

        def fetch_df_batches(self, **kwargs):
            assert kwargs["size"] == 10_000
            assert kwargs["parameters"] is None
            return iter(frames)

        def close(self) -> None:
            self.closed = True

    connection = _Connection()
    monkeypatch.setattr(
        OracleConnector,
        "_connect_sync",
        lambda _settings, _config: connection,
    )
    monkeypatch.setattr(OracleConnector, "_enforce_egress", lambda *args, **kwargs: None)

    table = OracleConnector._fetch_table_sync(_config())

    assert table is not None
    assert table.to_pylist() == [
        {"ID": 1, "AMOUNT": 10.0},
        {"ID": 2, "AMOUNT": 20.0},
        {"ID": 3, "AMOUNT": 30.0},
    ]
    assert connection.closed is True


def test_validate_sync_executes_dual_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    executed: list[str] = []

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement: str) -> None:
            executed.append(statement)

        def fetchone(self):
            return (1,)

    connection = SimpleNamespace(cursor=lambda: _Cursor(), close=lambda: None)
    monkeypatch.setattr(
        OracleConnector,
        "_connect_sync",
        lambda _settings, _config: connection,
    )
    monkeypatch.setattr(OracleConnector, "_enforce_egress", lambda *args, **kwargs: None)

    OracleConnector._validate_sync(_config())

    assert executed == ["SELECT 1 FROM DUAL"]
