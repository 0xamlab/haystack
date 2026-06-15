from __future__ import annotations

from types import SimpleNamespace

import pytest
from alembic.util.exc import CommandError

from tests import conftest as pytest_conftest


def test_assert_database_revision_is_known_skips_empty_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL_SYNC", "postgresql://example")
    monkeypatch.setattr(pytest_conftest, "_read_database_alembic_revision", lambda _: None)

    called = False

    def _unexpected_loader() -> object:
        nonlocal called
        called = True
        return object()

    monkeypatch.setattr(pytest_conftest, "_load_alembic_script_directory", _unexpected_loader)

    pytest_conftest._assert_database_revision_is_known()

    assert called is False


def test_assert_database_revision_is_known_raises_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL_SYNC", "postgresql://example")
    monkeypatch.setattr(pytest_conftest, "_read_database_alembic_revision", lambda _: "0037")

    script_directory = SimpleNamespace(
        dir="/repo/apps/api_server/alembic",
        get_heads=lambda: ["0034"],
        get_revision=lambda _: (_ for _ in ()).throw(
            CommandError("Can't locate revision identified by '0037'")
        ),
    )
    monkeypatch.setattr(
        pytest_conftest,
        "_load_alembic_script_directory",
        lambda: script_directory,
    )

    with pytest.raises(RuntimeError) as excinfo:
        pytest_conftest._assert_database_revision_is_known()

    message = str(excinfo.value)
    assert "database_revision='0037'" in message
    assert "checkout_heads='0034'" in message
    assert "Update the checkout" in message
    assert "will not auto-reset" in message
