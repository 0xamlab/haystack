"""File-backed local connector registry for offline (device-token) mode.

In offline mode the repository connector lives on local disk under ``$CODNA_CONNECTOR_STORE``
(default ``~/.codna/connectors/<id>.json``), org-scoped, instead of the Postgres ``data_connectors``
table — so the per-fix hot path reads ZERO Postgres. The stored ``config_json`` is encrypted exactly
like the DB row, so ``parse_connector_config`` decrypts it unchanged. The synthesized DataConnector
is an UNSAVED ORM instance (no session); the fix workflows read only columns (id / org_id /
owner_key_id / connector_type / config_json) plus the ``_to_response`` fields, so a detached
instance is safe.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

_DIR = Path(os.environ.get("CODNA_CONNECTOR_STORE") or (Path.home() / ".codna" / "connectors"))


def save_connector(record: dict[str, Any]) -> None:
    _DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(_DIR), prefix=".conn.", suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(record, f)
    os.replace(tmp, _DIR / f"{record['id']}.json")  # atomic


def get_connector(connector_id: str) -> dict[str, Any] | None:
    try:
        return json.loads((_DIR / f"{connector_id}.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _u(value: Any) -> uuid.UUID | None:
    return uuid.UUID(value) if value else None


def _dt(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(value) if value else None
    except (ValueError, TypeError):
        return None


def synthesize_connector(record: dict[str, Any]):
    """Reconstruct an unsaved DataConnector from a local record (no DB session)."""
    from apps.api_server.models.data_connector import (
        ConnectorStatus,
        ConnectorType,
        DataConnector,
    )

    return DataConnector(
        id=_u(record["id"]),
        org_id=_u(record["org_id"]),
        workspace_id=_u(record.get("workspace_id")),
        name=record.get("name") or "local-repo",
        description=record.get("description"),
        connector_type=ConnectorType(record["connector_type"]),
        config_json=record.get("config_json"),
        config_fingerprint=record.get("config_fingerprint"),
        status=ConnectorStatus(record["status"]),
        visibility=record.get("visibility") or "private",
        owner_user_id=_u(record.get("owner_user_id")),
        owner_key_id=_u(record.get("owner_key_id")),
        last_tested_at=_dt(record.get("last_tested_at")),
        error_message=record.get("error_message"),
        created_at=_dt(record.get("created_at")),
    )
