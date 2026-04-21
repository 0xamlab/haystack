from __future__ import annotations

import uuid

import pytest

from apps.api_server.services import calibration_service


class FakeResult:
    def __init__(self, rows: list[tuple[float, float]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[float, float]]:
        return self._rows


class FakeDB:
    def __init__(self, rows: list[tuple[float, float]]) -> None:
        self.rows = rows
        self.statement = None

    async def execute(self, statement: object) -> FakeResult:
        self.statement = statement
        return FakeResult(self.rows)


@pytest.fixture(autouse=True)
def clear_calibration_cache() -> None:
    calibration_service._CALIBRATION_CACHE.clear()


def test_calibrate_confidence_returns_raw_value_until_calibration_is_reliable() -> None:
    stats = calibration_service.update_calibration(
        "org-1",
        [100.0, 100.0, 100.0, 100.0],
        [90.0, 105.0, 95.0, 110.0],
    )

    adjusted, used_stats = calibration_service.calibrate_confidence(0.82, "org-1")

    assert stats.n_samples == 4
    assert stats.is_reliable is False
    assert adjusted == 0.82
    assert used_stats.n_samples == 4


@pytest.mark.asyncio
async def test_refresh_calibration_from_db_recomputes_org_stats() -> None:
    org_id = str(uuid.uuid4())
    db = FakeDB(
        [
            (100.0, 80.0),
            (100.0, 90.0),
            (100.0, 100.0),
            (100.0, 110.0),
            (100.0, 120.0),
        ]
    )

    stats = await calibration_service.refresh_calibration_from_db(org_id, db)
    adjusted, used_stats = calibration_service.calibrate_confidence(0.8, org_id)

    assert db.statement is not None
    assert stats.n_samples == 5
    assert stats.is_reliable is True
    assert used_stats.n_samples == 5
    assert 0.01 <= adjusted <= 0.99
