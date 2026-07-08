from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from algenta.runtime_connector_model_common import coerce_payload_mapping, jsonable


@dataclass(frozen=True)
class ConnectorMetadata:
    id: str
    name: str
    connector_type: str
    status: str
    visibility: str
    description: str | None = None
    last_tested_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime | None = None

    @classmethod
    def from_api(cls, payload: Any) -> ConnectorMetadata:
        data = coerce_payload_mapping(payload)
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            connector_type=str(data["connector_type"]),
            status=str(data["status"]),
            visibility=str(data["visibility"]),
            description=data.get("description"),
            last_tested_at=data.get("last_tested_at"),
            error_message=data.get("error_message"),
            created_at=data.get("created_at"),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))
