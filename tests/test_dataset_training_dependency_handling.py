from __future__ import annotations

from pathlib import Path

import pytest

from apps.api_server.middleware.auth import get_current_org
from apps.api_server.services import dataset_service as ds


class _FakeRegistry:
    def __init__(self) -> None:
        self.train_flags: list[bool] = []

    def register(  # type: ignore[no-untyped-def]
        self,
        schema,
        domain_aliases=None,
        epochs=80,
        batch_size=32,
        train=True,
    ):
        self.train_flags.append(train)
        return {
            "schema_hash": "schema_1234",
            "status": "untrained",
            "source_names": list(schema.keys()),
            "column_count": sum(len(columns) for columns in schema.values()),
            "registered_at": "2026-05-17T12:00:00+00:00",
        }

    def resolve(self, schema, domain_aliases=None):  # type: ignore[no-untyped-def]
        return None, "none"

    def status(self, schema, domain_aliases=None):  # type: ignore[no-untyped-def]
        return "untrained"


def _datasets_dir_factory(base: Path):
    def _datasets_dir(org_id: str) -> Path:
        path = base / org_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    return _datasets_dir


def _schema_fixture() -> dict[str, list[list[str]]]:
    return {"Orders": [["amount", "derived_measure"], ["customer", "other"]]}


def test_onboard_skips_training_when_semantic_runtime_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_registry = _FakeRegistry()

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(ds, "_schema_registry", lambda: fake_registry)
    monkeypatch.setattr(ds, "_datasets_dir", _datasets_dir_factory(tmp_path))
    monkeypatch.setattr(
        ds,
        "_semantic_training_dependency_error",
        lambda: "Semantic training requires optional dependencies not installed: torch.",
    )
    monkeypatch.setattr(ds, "ingest", lambda source, source_name=None: _schema_fixture())
    monkeypatch.setattr(ds, "suggest_aliases", lambda schema: {"amt": ["amount"]})
    monkeypatch.setattr(
        "apps.api_server.services.dataset_service._schema_registry", lambda: fake_registry
    )
    monkeypatch.setattr(
        "apps.api_server.services.dataset_service._datasets_dir", _datasets_dir_factory(tmp_path)
    )
    monkeypatch.setattr(
        "apps.api_server.services.dataset_service._semantic_training_dependency_error",
        lambda: "Semantic training requires optional dependencies not installed: torch.",
    )
    monkeypatch.setattr(
        "apps.api_server.services.dataset_service.ingest",
        lambda source, source_name=None: _schema_fixture(),
    )
    monkeypatch.setattr(
        "apps.api_server.services.dataset_service.suggest_aliases",
        lambda schema: {"amt": ["amount"]},
    )

    manifest = ds.onboard(
        org_id="org_test",
        source=[{"amount": 10.0, "customer": "A"}],
        name="Orders",
        async_train=True,
    )

    assert fake_registry.train_flags == [False]
    assert manifest["status"] == "untrained"
    assert manifest["model_tier"] == "none"
    assert manifest["training_unavailable_reason"] == (
        "Semantic training requires optional dependencies not installed: torch."
    )


@pytest.mark.anyio
async def test_onboard_file_returns_success_without_semantic_training_runtime(
    app,
    client,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_registry = _FakeRegistry()

    async def _fake_auth():  # type: ignore[no-untyped-def]
        return {"org_id": "org_test"}

    app.dependency_overrides[get_current_org] = _fake_auth
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "apps.api_server.services.dataset_service._schema_registry", lambda: fake_registry
    )
    monkeypatch.setattr(
        "apps.api_server.services.dataset_service._datasets_dir", _datasets_dir_factory(tmp_path)
    )
    monkeypatch.setattr(
        "apps.api_server.services.dataset_service._semantic_training_dependency_error",
        lambda: "Semantic training requires optional dependencies not installed: torch.",
    )
    monkeypatch.setattr(
        "apps.api_server.services.dataset_service.ingest",
        lambda source, source_name=None: _schema_fixture(),
    )
    monkeypatch.setattr(
        "apps.api_server.services.dataset_service.suggest_aliases",
        lambda schema: {"amt": ["amount"]},
    )

    response = await client.post(
        "/v1/datasets/onboard/file",
        data={"name": "Orders"},
        files={"file": ("orders.csv", b"amount,customer\n10,A\n20,B\n", "text/csv")},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    body = response.json()
    assert fake_registry.train_flags == [False]
    assert body["status"] == "untrained"
    assert body["model_tier"] == "none"
    assert body["decision_mode"] == "deterministic_only"
    assert body["schema"] == _schema_fixture()


@pytest.mark.anyio
async def test_retrain_returns_structured_error_when_semantic_training_runtime_missing(
    app,
    client,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def _fake_auth():  # type: ignore[no-untyped-def]
        return {"org_id": "org_test"}

    app.dependency_overrides[get_current_org] = _fake_auth
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "apps.api_server.services.dataset_service._load_manifest",
        lambda org_id, dataset_id: {
            "dataset_id": dataset_id,
            "schema_hash": "schema_1234",
            "schema": _schema_fixture(),
            "domain_aliases": None,
        },
    )
    monkeypatch.setattr(
        "apps.api_server.services.dataset_service._semantic_training_dependency_error",
        lambda: "Semantic training requires optional dependencies not installed: torch.",
    )

    response = await client.post("/v1/datasets/ds_test/retrain")

    app.dependency_overrides.clear()

    assert response.status_code == 422, response.text
    body = response.json()
    error = body.get("error") or body["detail"]["error"]
    assert error["code"] == "semantic_training_unavailable"
    assert "torch" in error["message"]
