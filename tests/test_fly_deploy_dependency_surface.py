"""Production deploy dependency guards."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PYTHON314_SAFE_DATABASE_PINS = {
    "sqlalchemy": "2.0.51",
    "asyncpg": "0.31.0",
    "alembic": "1.18.5",
    "greenlet": "3.5.3",
}

REQUIREMENT_PIN_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9_.-]+)(?:\[[^\]]+\])?==(?P<version>[^#;\s]+)"
)


def _exact_pins(requirements_path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in requirements_path.read_text().splitlines():
        match = REQUIREMENT_PIN_RE.match(line)
        if match is None:
            continue
        pins[match.group("name").lower().replace("_", "-")] = match.group("version")
    return pins


def test_fly_python314_database_stack_uses_verified_import_safe_pins() -> None:
    """Fly's release command imports Alembic under the production Python 3.14 image."""

    for relative_path in ("requirements-dev.txt", "apps/api-server/requirements.txt"):
        pins = _exact_pins(ROOT / relative_path)
        assert {
            name: pins.get(name) for name in PYTHON314_SAFE_DATABASE_PINS
        } == PYTHON314_SAFE_DATABASE_PINS
