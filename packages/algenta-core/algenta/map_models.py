from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class FieldMapping:
    source_field: str
    source: str
    target_field: str
    target: str
    confidence: float
    reason: list[str]
    match_type: str


@dataclass
class MapResult:
    sources_analyzed: int
    total_fields: int
    mappings: list[FieldMapping]
    unified_schema: list[dict[str, Any]]
    join_keys: list[dict[str, Any]]
    simulation_ready: bool
