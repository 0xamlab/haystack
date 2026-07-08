from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from algenta.runtime_connector_model_common import coerce_payload_mapping, jsonable


@dataclass(frozen=True)
class DatasetSummary:
    dataset_id: str
    dataset_name: str
    name: str | None = None
    source_id: str | None = None
    status: str | None = None
    source_names: list[str] = field(default_factory=list)
    source_name: str | None = None
    description: str | None = None
    connection_id: str | None = None
    connection_type: str | None = None
    provider: str | None = None
    visibility: str = "private"
    owner_user_id: str | None = None
    owner_key_id: str | None = None
    refreshable: bool = False
    row_count: int | None = None
    column_count: int | None = None
    columns: int | None = None
    roles_summary: dict[str, Any] = field(default_factory=dict)
    discovery_labels: dict[str, Any] | None = None
    discovery_metadata: dict[str, Any] | None = None
    registered_at: datetime | None = None
    selection: dict[str, Any] | None = None

    @classmethod
    def from_api(cls, payload: Any) -> DatasetSummary:
        data = coerce_payload_mapping(payload)
        dataset_name = str(data.get("dataset_name") or data.get("name") or data["dataset_id"])
        return cls(
            dataset_id=str(data["dataset_id"]),
            dataset_name=dataset_name,
            name=data.get("name"),
            source_id=data.get("source_id"),
            status=data.get("status"),
            source_names=list(data.get("source_names") or []),
            source_name=data.get("source_name"),
            description=data.get("description"),
            connection_id=data.get("connection_id"),
            connection_type=data.get("connection_type"),
            provider=data.get("provider"),
            visibility=str(data.get("visibility") or "private"),
            owner_user_id=data.get("owner_user_id"),
            owner_key_id=data.get("owner_key_id"),
            refreshable=bool(data.get("refreshable", False)),
            row_count=data.get("row_count"),
            column_count=data.get("column_count"),
            columns=data.get("columns"),
            roles_summary=dict(data.get("roles_summary") or {}),
            discovery_labels=data.get("discovery_labels"),
            discovery_metadata=data.get("discovery_metadata"),
            registered_at=data.get("registered_at"),
            selection=data.get("selection"),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class DatasetList:
    datasets: list[DatasetSummary] = field(default_factory=list)
    count: int = 0
    total: int = 0
    matched_total: int | None = None
    page: int = 1
    limit: int = 200
    pages: int = 1

    @classmethod
    def from_api(cls, payload: Any) -> DatasetList:
        data = coerce_payload_mapping(payload)
        datasets = [DatasetSummary.from_api(item) for item in data.get("datasets") or []]
        count = int(data.get("count", len(datasets)))
        total = int(data.get("total", count))
        matched_total = data.get("matched_total")
        return cls(
            datasets=datasets,
            count=count,
            total=total,
            matched_total=None if matched_total is None else int(matched_total),
            page=int(data.get("page", 1)),
            limit=int(data.get("limit", 200)),
            pages=int(data.get("pages", 1)),
        )

    def __iter__(self):
        return iter(self.datasets)

    def __len__(self) -> int:
        return len(self.datasets)

    def __getitem__(self, index: int | slice):
        return self.datasets[index]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class DatasetSelectionSummary:
    dataset_id: str
    name: str
    status: str
    source_names: list[str] = field(default_factory=list)
    row_count: int | None = None
    column_count: int = 0
    registered_at: datetime | None = None
    query_hints: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> DatasetSelectionSummary:
        data = coerce_payload_mapping(payload)
        return cls(
            dataset_id=str(data["dataset_id"]),
            name=str(data["name"]),
            status=str(data["status"]),
            source_names=list(data.get("source_names") or []),
            row_count=data.get("row_count"),
            column_count=int(data.get("column_count", 0)),
            registered_at=data.get("registered_at"),
            query_hints=list(data.get("query_hints") or []),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class DatasetDetail:
    dataset: DatasetSummary
    schema: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: Any) -> DatasetDetail:
        data = coerce_payload_mapping(payload)
        return cls(
            dataset=DatasetSummary.from_api(data["dataset"]),
            schema=dict(data.get("schema") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class DatasetDeleteOutput:
    dataset_id: str
    status: str
    connection_deleted: bool = False

    @classmethod
    def from_api(cls, payload: Any) -> DatasetDeleteOutput:
        data = coerce_payload_mapping(payload)
        return cls(
            dataset_id=str(data["dataset_id"]),
            status=str(data["status"]),
            connection_deleted=bool(data.get("connection_deleted", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))
