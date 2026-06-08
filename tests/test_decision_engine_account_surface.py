from __future__ import annotations

import importlib
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
if str(PYTHON_SDK) not in sys.path:
    sys.path.insert(0, str(PYTHON_SDK))

client_account_surface = importlib.import_module("decision_engine.client_account_surface")
async_client_account_surface = importlib.import_module(
    "decision_engine.async_client_account_surface"
)
APIKeyInfo = importlib.import_module("decision_engine.models_account").APIKeyInfo
MeResult = importlib.import_module("decision_engine.models_control_plane").MeResult
DistributionListResult = importlib.import_module(
    "decision_engine.models_control_plane"
).DistributionListResult
TemplateListResult = importlib.import_module(
    "decision_engine.models_control_plane"
).TemplateListResult


def test_create_api_key_serializes_naive_datetime_expiry_as_utc() -> None:
    captured: dict[str, object] = {}

    def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kwargs["json"]
        return {
            "id": "key_123",
            "key_prefix": "de_live_abcd",
            "device_limit": 2,
            "raw_key": "de_live_abcd_secret_value",
        }

    client = SimpleNamespace(_request=_request)
    expiry = datetime(2028, 5, 19, 0, 0, 0)

    result = client_account_surface.create_api_key(
        client,
        name="Mission Runtime Key",
        expires_at=expiry,
        device_limit=2,
    )

    assert result["id"] == "key_123"
    assert result["key_prefix"] == "de_live_abcd"
    assert result["device_limit"] == 2
    assert result["raw_key"] == "de_live_abcd_secret_value"
    assert captured["method"] == "POST"
    assert captured["path"] == "/v1/api-keys"
    assert captured["json"] == {
        "label": "Mission Runtime Key",
        "expires_at": "2028-05-19T00:00:00+00:00",
        "device_limit": 2,
    }


def test_create_api_key_accepts_iso_expiry_string() -> None:
    captured: dict[str, object] = {}

    def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        captured["json"] = kwargs["json"]
        return {
            "id": "key_456",
            "key_prefix": "de_live_wxyz",
            "device_limit": 5,
            "raw_key": "de_live_wxyz_secret_value",
        }

    client = SimpleNamespace(_request=_request)

    result = client_account_surface.create_api_key(
        client,
        label="Mission Runtime Key",
        expires_at="2028-05-19T00:00:00Z",
    )

    assert result["id"] == "key_456"
    assert result["key_prefix"] == "de_live_wxyz"
    assert result["device_limit"] == 5
    assert result["raw_key"] == "de_live_wxyz_secret_value"
    assert captured["json"] == {
        "label": "Mission Runtime Key",
        "expires_at": "2028-05-19T00:00:00Z",
    }


def test_create_api_key_accepts_zero_device_limit() -> None:
    captured: dict[str, object] = {}

    def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kwargs["json"]
        return {
            "id": "key_zero",
            "key_prefix": "de_live_zero",
            "device_limit": 0,
            "raw_key": "de_live_zero_secret_value",
        }

    client = SimpleNamespace(_request=_request)

    result = client_account_surface.create_api_key(
        client,
        label="Mission Enterprise Key",
        device_limit=0,
    )

    assert result["id"] == "key_zero"
    assert result["device_limit"] == 0
    assert captured["method"] == "POST"
    assert captured["path"] == "/v1/api-keys"
    assert captured["json"] == {
        "label": "Mission Enterprise Key",
        "device_limit": 0,
    }


def test_create_api_key_rejects_invalid_expiry_type() -> None:
    client = SimpleNamespace(_request=lambda *_args, **_kwargs: {})

    with pytest.raises(
        TypeError,
        match="expires_at must be a datetime, ISO-8601 string, or None",
    ):
        client_account_surface.create_api_key(
            client,
            label="Mission Runtime Key",
            expires_at=730,
        )


def test_create_api_key_rejects_invalid_device_limit_type() -> None:
    client = SimpleNamespace(_request=lambda *_args, **_kwargs: {})

    with pytest.raises(TypeError, match="device_limit must be an integer or None"):
        client_account_surface.create_api_key(
            client,
            label="Mission Runtime Key",
            device_limit="2",
        )


def test_create_api_key_rejects_negative_device_limit() -> None:
    client = SimpleNamespace(_request=lambda *_args, **_kwargs: {})

    with pytest.raises(ValueError, match="device_limit must be greater than or equal to 0"):
        client_account_surface.create_api_key(
            client,
            label="Mission Runtime Key",
            device_limit=-1,
        )


def test_list_api_keys_validates_expiry_metadata() -> None:
    api_key_id = str(uuid4())

    def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        assert method == "GET"
        assert path == "/v1/api-keys"
        assert kwargs == {}
        return {
            "api_keys": [
                {
                    "id": api_key_id,
                    "label": "Mission Runtime Key",
                    "key_prefix": "de_live_abcd",
                    "device_limit": 3,
                    "status": "active",
                    "created_at": "2026-05-19T00:00:00Z",
                    "last_used_at": None,
                    "expires_at": "2028-05-19T00:00:00Z",
                }
            ],
            "total": 1,
            "page": 1,
            "limit": 50,
            "pages": 1,
        }

    client = SimpleNamespace(_request=_request)

    result = client_account_surface.list_api_keys(client)

    assert len(result) == 1
    assert isinstance(result[0], APIKeyInfo)
    assert result[0].id == UUID(api_key_id)
    assert result[0].device_limit == 3
    assert result[0].expires_at == datetime(2028, 5, 19, 0, 0, tzinfo=UTC)
    assert not hasattr(result[0], "raw_key")


def test_list_api_keys_accepts_raw_list_shape() -> None:
    api_key_id = str(uuid4())

    def _request(method: str, path: str, **kwargs: object) -> list[dict[str, object]]:
        assert method == "GET"
        assert path == "/v1/api-keys"
        assert kwargs == {}
        return [
            {
                "id": api_key_id,
                "label": "Mission Runtime Key",
                "key_prefix": "de_live_abcd",
                "device_limit": 5,
                "status": "active",
                "created_at": "2026-05-19T00:00:00Z",
                "expires_at": "2028-05-19T00:00:00Z",
            }
        ]

    client = SimpleNamespace(_request=_request)

    result = client_account_surface.list_api_keys(client)

    assert len(result) == 1
    assert result[0].id == UUID(api_key_id)


def test_list_api_keys_accepts_zero_device_limit() -> None:
    api_key_id = str(uuid4())

    def _request(method: str, path: str, **kwargs: object) -> list[dict[str, object]]:
        assert method == "GET"
        assert path == "/v1/api-keys"
        assert kwargs == {}
        return [
            {
                "id": api_key_id,
                "label": "Mission Enterprise Key",
                "key_prefix": "de_live_zero",
                "device_limit": 0,
                "status": "active",
                "created_at": "2026-05-19T00:00:00Z",
                "expires_at": "2028-05-19T00:00:00Z",
            }
        ]

    client = SimpleNamespace(_request=_request)

    result = client_account_surface.list_api_keys(client)

    assert len(result) == 1
    assert result[0].id == UUID(api_key_id)
    assert result[0].device_limit == 0


def test_list_api_keys_rejects_secret_leakage() -> None:
    def _request(method: str, path: str, **kwargs: object) -> list[dict[str, object]]:
        assert method == "GET"
        assert path == "/v1/api-keys"
        assert kwargs == {}
        return [
            {
                "id": str(uuid4()),
                "label": "Leaked Key",
                "key_prefix": "de_live_abcd",
                "status": "active",
                "created_at": "2026-05-19T00:00:00Z",
                "expires_at": "2028-05-19T00:00:00Z",
                "raw_key": "de_live_abcd_secret_value",
            }
        ]

    client = SimpleNamespace(_request=_request)

    with pytest.raises(ValueError, match="one-time secret material"):
        client_account_surface.list_api_keys(client)


def test_create_api_key_rejects_missing_secret_material() -> None:
    def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        assert method == "POST"
        assert path == "/v1/api-keys"
        return {"id": "key_789", "key_prefix": "de_live_abcd"}

    client = SimpleNamespace(_request=_request)

    with pytest.raises(ValueError, match="missing raw_key"):
        client_account_surface.create_api_key(client, label="Mission Runtime Key")


@pytest.mark.anyio
async def test_async_create_api_key_serializes_expiry_and_revoke_routes() -> None:
    captured: list[tuple[str, str, object | None]] = []

    async def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        captured.append((method, path, kwargs.get("json")))
        if method == "POST":
            return {
                "id": "key_async",
                "key_prefix": "de_live_async",
                "device_limit": 4,
                "raw_key": "de_live_async_secret_value",
            }
        return {"status": "revoked"}

    client = SimpleNamespace(_request=_request)
    expiry = datetime(2028, 5, 19, 0, 0, tzinfo=UTC)

    created = await async_client_account_surface.create_api_key(
        client,
        label="Mission Async Key",
        expires_at=expiry,
        device_limit=4,
    )
    revoked = await async_client_account_surface.revoke_api_key(client, "key_async")

    assert created["id"] == "key_async"
    assert created["key_prefix"] == "de_live_async"
    assert created["device_limit"] == 4
    assert created["raw_key"] == "de_live_async_secret_value"
    assert revoked == {"status": "revoked"}
    assert captured == [
        (
            "POST",
            "/v1/api-keys",
            {
                "label": "Mission Async Key",
                "expires_at": "2028-05-19T00:00:00+00:00",
                "device_limit": 4,
            },
        ),
        ("DELETE", "/v1/api-keys/key_async", None),
    ]


@pytest.mark.anyio
async def test_async_create_api_key_accepts_zero_device_limit() -> None:
    captured: list[tuple[str, str, object | None]] = []

    async def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        captured.append((method, path, kwargs.get("json")))
        return {
            "id": "key_async_zero",
            "key_prefix": "de_live_async_zero",
            "device_limit": 0,
            "raw_key": "de_live_async_zero_secret_value",
        }

    client = SimpleNamespace(_request=_request)

    created = await async_client_account_surface.create_api_key(
        client,
        label="Mission Async Enterprise Key",
        device_limit=0,
    )

    assert created["id"] == "key_async_zero"
    assert created["device_limit"] == 0
    assert created["raw_key"] == "de_live_async_zero_secret_value"
    assert captured == [
        (
            "POST",
            "/v1/api-keys",
            {
                "label": "Mission Async Enterprise Key",
                "device_limit": 0,
            },
        )
    ]


def test_update_me_validates_and_returns_typed_model() -> None:
    captured: dict[str, object] = {}

    def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kwargs["json"]
        return {
            "user": {
                "id": str(uuid4()),
                "email": "owner@example.com",
                "name": "Mission Ops",
                "role": "owner",
                "email_verified": True,
                "created_at": "2026-05-19T00:00:00Z",
            },
            "org": {
                "id": str(uuid4()),
                "name": "Mission Control",
                "slug": "mission-control",
                "plan": "enterprise",
                "status": "active",
                "created_at": "2026-05-19T00:00:00Z",
            },
        }

    client = SimpleNamespace(_request=_request)

    result = client_account_surface.update_me(client, name="  Mission Ops  ", org_name=" Mission Control ")

    assert isinstance(result, MeResult)
    assert result.user.name == "Mission Ops"
    assert result.org.name == "Mission Control"
    assert captured == {
        "method": "PATCH",
        "path": "/v1/me",
        "json": {"name": "Mission Ops", "org_name": "Mission Control"},
    }


def test_update_me_rejects_empty_payload() -> None:
    client = SimpleNamespace(_request=lambda *_args, **_kwargs: {})

    with pytest.raises(ValueError, match="requires name and/or org_name"):
        client_account_surface.update_me(client)


@pytest.mark.anyio
async def test_async_update_me_validates_and_returns_typed_model() -> None:
    captured: dict[str, object] = {}

    async def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kwargs["json"]
        return {
            "user": {
                "id": str(uuid4()),
                "email": "owner@example.com",
                "name": "Mission Ops",
                "role": "owner",
                "email_verified": True,
                "created_at": "2026-05-19T00:00:00Z",
            },
            "org": {
                "id": str(uuid4()),
                "name": "Mission Control",
                "slug": "mission-control",
                "plan": "enterprise",
                "status": "active",
                "created_at": "2026-05-19T00:00:00Z",
            },
        }

    client = SimpleNamespace(_request=_request)

    result = await async_client_account_surface.update_me(client, org_name=" Mission Control ")

    assert isinstance(result, MeResult)
    assert result.org.slug == "mission-control"
    assert captured == {
        "method": "PATCH",
        "path": "/v1/me",
        "json": {"org_name": "Mission Control"},
    }


def test_distributions_and_templates_normalize_list_payloads() -> None:
    calls: list[tuple[str, str]] = []

    def _request(method: str, path: str, **kwargs: object) -> object:
        assert kwargs == {}
        calls.append((method, path))
        if path == "/v1/distributions":
            return [
                {
                    "name": "normal",
                    "description": "Normal distribution.",
                    "required_params": ["mean", "std"],
                    "optional_params": [],
                    "example": {"mean": 100.0, "std": 12.0},
                }
            ]
        if path == "/v1/templates":
            return [
                {
                    "id": "product-launch",
                    "name": "Product Launch Decision",
                    "category": "business",
                    "description": "Compare launch scenarios.",
                    "example_request": {"mode": "auto"},
                }
            ]
        raise AssertionError(path)

    client = SimpleNamespace(_request=_request)

    distributions = client_account_surface.distributions(client)
    templates = client_account_surface.templates(client)

    assert isinstance(distributions, DistributionListResult)
    assert distributions.total == 1
    assert distributions.distributions[0].name == "normal"
    assert isinstance(templates, TemplateListResult)
    assert templates.page == 1
    assert templates.templates[0].id == "product-launch"
    assert calls == [("GET", "/v1/distributions"), ("GET", "/v1/templates")]


@pytest.mark.anyio
async def test_async_distributions_and_templates_normalize_paginated_payloads() -> None:
    calls: list[tuple[str, str]] = []

    async def _request(method: str, path: str, **kwargs: object) -> object:
        assert kwargs == {}
        calls.append((method, path))
        if path == "/v1/distributions":
            return {
                "distributions": [
                    {
                        "name": "normal",
                        "description": "Normal distribution.",
                        "required_params": ["mean", "std"],
                        "optional_params": [],
                        "example": {"mean": 100.0, "std": 12.0},
                    }
                ],
                "total": 1,
                "page": 1,
                "limit": 25,
                "pages": 1,
            }
        if path == "/v1/templates":
            return {
                "templates": [
                    {
                        "id": "product-launch",
                        "name": "Product Launch Decision",
                        "category": "business",
                        "description": "Compare launch scenarios.",
                        "example_request": {"mode": "auto"},
                    }
                ],
                "total": 1,
                "page": 1,
                "limit": 25,
                "pages": 1,
            }
        raise AssertionError(path)

    client = SimpleNamespace(_request=_request)

    distributions = await async_client_account_surface.distributions(client)
    templates = await async_client_account_surface.templates(client)

    assert isinstance(distributions, DistributionListResult)
    assert distributions.limit == 25
    assert isinstance(templates, TemplateListResult)
    assert templates.templates[0].category == "business"
    assert calls == [("GET", "/v1/distributions"), ("GET", "/v1/templates")]
