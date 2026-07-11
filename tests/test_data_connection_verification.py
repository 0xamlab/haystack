from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from apps.api_server.models.data_connector import (
    ConnectorStatus,
    ConnectorType,
    DataConnector,
)
from apps.api_server.services import data_connection_service as service


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "error_message", "expected"),
    [
        (
            ConnectorStatus.LIVE,
            None,
            (True, "Connection credentials already verified at registration.", 0),
        ),
        (
            ConnectorStatus.ERROR,
            "authentication rejected",
            (False, "authentication rejected", 0),
        ),
    ],
)
async def test_verify_connector_once_reuses_final_registration_outcome(
    monkeypatch: pytest.MonkeyPatch,
    status: ConnectorStatus,
    error_message: str | None,
    expected: tuple[bool, str, int],
) -> None:
    connector = SimpleNamespace(
        id=uuid.uuid4(),
        status=status,
        error_message=error_message,
    )

    async def _unexpected_probe(_connector, _db):
        raise AssertionError("final connector state must not trigger a credential probe")

    monkeypatch.setattr(service, "_test_and_persist_connector", _unexpected_probe)

    assert await service._verify_connector_once(connector, object()) == expected


@pytest.mark.anyio
async def test_verify_connector_once_probes_only_on_first_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connector = SimpleNamespace(
        id=uuid.uuid4(),
        status=ConnectorStatus.UNTESTED,
        last_tested_at=None,
        error_message=None,
    )
    probe_calls = 0

    async def _initial_probe(_connector, _db):
        nonlocal probe_calls
        probe_calls += 1
        connector.status = ConnectorStatus.LIVE
        connector.last_tested_at = datetime.now(tz=UTC)
        return True, "Connection verified.", 43

    monkeypatch.setattr(service, "_test_and_persist_connector", _initial_probe)

    first = await service._verify_connector_once(connector, object())
    second = await service._verify_connector_once(connector, object())

    assert first == (True, "Connection verified.", 43)
    assert second == (
        True,
        "Connection credentials already verified at registration.",
        0,
    )
    assert probe_calls == 1


@pytest.mark.anyio
async def test_connector_probe_rechecks_status_after_row_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connector = SimpleNamespace(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        status=ConnectorStatus.UNTESTED,
        last_tested_at=None,
        error_message=None,
    )
    locked_connector = SimpleNamespace(
        id=connector.id,
        org_id=connector.org_id,
        status=ConnectorStatus.LIVE,
        last_tested_at=datetime.now(tz=UTC),
        error_message=None,
    )

    class _Session:
        commits = 0

        async def execute(self, statement):
            assert statement._for_update_arg is not None
            return SimpleNamespace(scalar_one_or_none=lambda: locked_connector)

        async def commit(self) -> None:
            self.commits += 1

        async def rollback(self) -> None:
            raise AssertionError("a persisted connector must not roll back")

    async def _unexpected_test(_connector_type, _config):
        raise AssertionError("the request that loses the row-lock race must not probe")

    session = _Session()
    monkeypatch.setattr(service, "test_connector_real", _unexpected_test)

    outcome = await service._test_and_persist_connector(connector, session)

    assert outcome == (
        True,
        "Connection credentials already verified at registration.",
        0,
    )
    assert session.commits == 1
    assert connector.status == ConnectorStatus.LIVE


@pytest.mark.anyio
async def test_connector_probe_fails_if_row_disappears() -> None:
    connector = SimpleNamespace(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        status=ConnectorStatus.UNTESTED,
    )

    class _Session:
        rolled_back = False

        async def execute(self, _statement):
            return SimpleNamespace(scalar_one_or_none=lambda: None)

        async def rollback(self) -> None:
            self.rolled_back = True

    session = _Session()

    with pytest.raises(HTTPException) as exc_info:
        await service._test_and_persist_connector(connector, session)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["error"]["code"] == "not_found"
    assert session.rolled_back is True


@pytest.mark.anyio
async def test_local_connector_probe_persists_final_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from apps.api_server.services import local_connector_store

    connector_id = uuid.uuid4()
    org_id = uuid.uuid4()
    connector = DataConnector(
        id=connector_id,
        org_id=org_id,
        name="local oracle",
        connector_type=ConnectorType.ORACLE,
        config_json="encrypted",
        status=ConnectorStatus.UNTESTED,
        visibility="private",
    )
    monkeypatch.setattr(local_connector_store, "_DIR", tmp_path)
    local_connector_store.save_connector(
        {
            "id": str(connector_id),
            "org_id": str(org_id),
            "name": connector.name,
            "connector_type": "oracle",
            "config_json": "encrypted",
            "status": "untested",
            "visibility": "private",
        }
    )

    async def _successful_test(_connector_type, _config):
        return True, "Oracle Database connection successful.", 41

    monkeypatch.setattr(service, "decrypt_config_json", lambda *_args, **_kwargs: "{}")
    monkeypatch.setattr(service, "test_connector_real", _successful_test)

    outcome = await service._test_and_persist_connector(connector, object())
    restored = local_connector_store.synthesize_connector(
        local_connector_store.get_connector(str(connector_id))
    )

    assert outcome == (True, "Oracle Database connection successful.", 41)
    assert restored.status == ConnectorStatus.LIVE
    assert restored.last_tested_at is not None
