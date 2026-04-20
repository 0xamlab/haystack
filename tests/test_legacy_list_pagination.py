from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from apps.api_server.routers import account as account_router
from apps.api_server.routers import connectors as connectors_router
from apps.api_server.routers import devices as devices_router
from apps.api_server.routers import engines as engines_router
from apps.api_server.routers import team as team_router


@pytest.mark.asyncio
async def test_list_connectors_keeps_raw_list_without_pagination(monkeypatch) -> None:
    connector_payloads = [
        connectors_router.ConnectorResponse(
            id="c1",
            name="Primary DB",
            description=None,
            connector_type="postgres",
            status="live",
            visibility="private",
            last_tested_at=None,
            error_message=None,
            created_at=datetime.now(UTC),
        ),
        connectors_router.ConnectorResponse(
            id="c2",
            name="Warehouse",
            description=None,
            connector_type="snowflake",
            status="untested",
            visibility="shared",
            last_tested_at=None,
            error_message=None,
            created_at=datetime.now(UTC),
        ),
    ]
    monkeypatch.setattr(
        connectors_router,
        "list_visible_connectors",
        AsyncMock(return_value=[SimpleNamespace(), SimpleNamespace()]),
    )
    monkeypatch.setattr(
        connectors_router,
        "_to_response",
        lambda connector: connector_payloads.pop(0),
    )

    response = await connectors_router.list_connectors(
        db=object(),
        auth={"org_id": "org_1"},
        page=None,
        limit=None,
    )

    assert isinstance(response, list)
    assert [item.id for item in response] == ["c1", "c2"]


@pytest.mark.asyncio
async def test_list_connectors_returns_envelope_when_paginated(monkeypatch) -> None:
    connector_payloads = [
        connectors_router.ConnectorResponse(
            id="c1",
            name="Primary DB",
            description=None,
            connector_type="postgres",
            status="live",
            visibility="private",
            last_tested_at=None,
            error_message=None,
            created_at=datetime.now(UTC),
        ),
        connectors_router.ConnectorResponse(
            id="c2",
            name="Warehouse",
            description=None,
            connector_type="snowflake",
            status="untested",
            visibility="shared",
            last_tested_at=None,
            error_message=None,
            created_at=datetime.now(UTC),
        ),
    ]
    monkeypatch.setattr(
        connectors_router,
        "list_visible_connectors",
        AsyncMock(return_value=[SimpleNamespace(), SimpleNamespace()]),
    )
    monkeypatch.setattr(
        connectors_router,
        "_to_response",
        lambda connector: connector_payloads.pop(0),
    )

    response = await connectors_router.list_connectors(
        db=object(),
        auth={"org_id": "org_1"},
        page=1,
        limit=1,
    )

    assert isinstance(response, connectors_router.ConnectorListResponse)
    assert response.total == 2
    assert response.page == 1
    assert response.limit == 1
    assert response.pages == 2
    assert [item.id for item in response.connectors] == ["c1"]


@dataclass
class _FakeEnumValue:
    value: str


@dataclass
class _FakeUser:
    id: str
    name: str
    email: str
    role: _FakeEnumValue
    status: _FakeEnumValue


class _ScalarResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return list(self._items)


@pytest.mark.asyncio
async def test_list_team_supports_raw_and_paginated_shapes() -> None:
    fake_users = [
        _FakeUser("u1", "Alice", "alice@example.com", _FakeEnumValue("owner"), _FakeEnumValue("active")),
        _FakeUser("u2", "Bob", "bob@example.com", _FakeEnumValue("member"), _FakeEnumValue("active")),
    ]
    db = SimpleNamespace(execute=AsyncMock(return_value=_ScalarResult(fake_users)))

    raw_response = await team_router.list_team(
        db=db,
        auth={"org_id": "org_1"},
        page=None,
        limit=None,
    )
    assert isinstance(raw_response, list)
    assert [item.user_id for item in raw_response] == ["u1", "u2"]

    paginated_response = await team_router.list_team(
        db=db,
        auth={"org_id": "org_1"},
        page=2,
        limit=1,
    )
    assert isinstance(paginated_response, team_router.TeamListResponse)
    assert paginated_response.total == 2
    assert paginated_response.page == 2
    assert paginated_response.limit == 1
    assert paginated_response.pages == 2
    assert [item.user_id for item in paginated_response.members] == ["u2"]


@dataclass
class _FakeAPIKey:
    id: str
    label: str
    key_prefix: str
    status: _FakeEnumValue
    created_at: datetime
    last_used_at: datetime | None = None


@pytest.mark.asyncio
async def test_list_api_keys_supports_raw_and_paginated_shapes() -> None:
    fake_keys = [
        _FakeAPIKey(str(uuid4()), "Primary", "de_live_", _FakeEnumValue("active"), datetime.now(UTC)),
        _FakeAPIKey(str(uuid4()), "Secondary", "de_test_", _FakeEnumValue("active"), datetime.now(UTC)),
    ]
    db = SimpleNamespace(execute=AsyncMock(return_value=_ScalarResult(fake_keys)))

    raw_response = await account_router.list_api_keys(
        auth={"org_id": "org_1"},
        db=db,
        page=None,
        limit=None,
    )
    assert isinstance(raw_response, list)
    assert [str(item.id) for item in raw_response] == [fake_keys[0].id, fake_keys[1].id]

    paginated_response = await account_router.list_api_keys(
        auth={"org_id": "org_1"},
        db=db,
        page=1,
        limit=1,
    )
    assert isinstance(paginated_response, account_router.APIKeyListResponse)
    assert paginated_response.total == 2
    assert paginated_response.page == 1
    assert paginated_response.limit == 1
    assert paginated_response.pages == 2
    assert [str(item.id) for item in paginated_response.api_keys] == [fake_keys[0].id]


@pytest.mark.asyncio
async def test_static_account_lists_support_paginated_envelopes() -> None:
    distributions = await account_router.distributions(
        auth={"org_id": "org_1"},
        page=1,
        limit=2,
    )
    templates = await account_router.templates(
        auth={"org_id": "org_1"},
        page=1,
        limit=2,
    )

    assert isinstance(distributions, account_router.DistributionListResponse)
    assert distributions.total >= 5
    assert distributions.limit == 2
    assert distributions.pages >= 3
    assert len(distributions.distributions) == 2

    assert isinstance(templates, account_router.TemplateListResponse)
    assert templates.total == 3
    assert templates.limit == 2
    assert templates.pages == 2
    assert len(templates.templates) == 2


class _ScalarOneResult:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return list(self._value)


@pytest.mark.asyncio
async def test_audit_logs_return_pages_for_demo_fallback() -> None:
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _ScalarOneResult(0),
                _ScalarOneResult([]),
            ]
        )
    )

    response = await team_router.get_audit_logs(
        db=db,
        auth={"org_id": uuid4()},
        page=1,
        limit=2,
    )

    assert response.total == 3
    assert response.page == 1
    assert response.limit == 2
    assert response.pages == 2
    assert len(response.entries) == 2


def test_engine_catalog_supports_pagination() -> None:
    response = engines_router.list_engines(page=2, limit=5)

    assert response.page == 2
    assert response.limit == 5
    assert response.total >= response.count
    assert response.pages >= 1
    assert len(response.engines) <= 5


@pytest.mark.asyncio
async def test_device_list_returns_paginated_metadata(monkeypatch) -> None:
    fake_devices = [
        {"device_id": "device-1", "hostname_hash": "a"},
        {"device_id": "device-2", "hostname_hash": "b"},
        {"device_id": "device-3", "hostname_hash": "c"},
    ]
    fake_api_key_row = SimpleNamespace(
        organization=SimpleNamespace(plan="developer"),
    )
    db = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one=lambda: fake_api_key_row)),
    )
    monkeypatch.setattr(devices_router, "list_devices", AsyncMock(return_value=fake_devices))

    response = await devices_router.device_list(
        ctx={"org_id": uuid4(), "key_id": uuid4()},
        db=db,
        page=2,
        limit=2,
    )

    assert response.total == 3
    assert response.page == 2
    assert response.limit == 2
    assert response.pages == 2
    assert response.device_count == 1
    assert [item["device_id"] for item in response.devices] == ["device-3"]


@pytest.mark.asyncio
async def test_simulation_templates_support_paginated_metadata(monkeypatch) -> None:
    from apps.api_server import main as api_main

    monkeypatch.setattr(
        "apps.api_server.simulation_templates.list_templates",
        lambda domain=None, industry=None: [
            {"id": "t1", "tags": ["finance"]},
            {"id": "t2", "tags": ["finance"]},
            {"id": "t3", "tags": ["ops"]},
        ],
    )
    monkeypatch.setattr(
        "apps.api_server.simulation_templates.get_all_domains",
        lambda: ["finance", "ops"],
    )
    monkeypatch.setattr(
        "apps.api_server.simulation_templates.get_all_tags",
        lambda: ["finance", "ops"],
    )

    response = await api_main.list_simulation_templates(
        domain=None,
        industry=None,
        tag=None,
        page=2,
        limit=2,
    )

    assert response["total"] == 3
    assert response["page"] == 2
    assert response["limit"] == 2
    assert response["pages"] == 2
    assert response["count"] == 1
    assert [item["id"] for item in response["templates"]] == ["t3"]
