from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from algenta.runtime_model_common import coerce_payload_mapping


@dataclass(frozen=True)
class ColumnExtract:
    """Aligned numeric column extraction result.

    Mirrors the TS SDK's ``ColumnExtractResult`` exactly (conformance-tested
    cross-language): per-column number-or-null arrays aligned rowwise, plus a
    canonical ``input_hash`` over the extraction request.
    """

    columns: dict[str, list[float | None]] = field(default_factory=dict)
    row_count: int = 0
    source_name: str = ""
    schema_revision: str = ""
    alignment: str = "rowwise"
    input_hash: str = ""

    @classmethod
    def from_api(cls, payload: Any) -> ColumnExtract:
        data = coerce_payload_mapping(payload)
        return cls(
            columns=data.get("columns") or {},
            row_count=data.get("row_count") or 0,
            source_name=data.get("source_name") or "",
            schema_revision=data.get("schema_revision") or "",
            alignment=data.get("alignment") or "rowwise",
            input_hash=data.get("input_hash") or "",
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
