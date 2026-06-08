from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class JoinHop:
    """One edge in a multi-hop join path."""

    left_source: str
    right_source: str
    left_key: str
    right_key: str
    confidence: float = 0.0
    cardinality: str = ""
    join_type: str = "inner"
    notes: list[str] = field(default_factory=list)


@dataclass
class QueryPlan:
    """Fully-resolved query plan with no human-supplied column names."""

    metric_src: str
    metric_col: str
    metric_conf: float
    metric_role: str
    agg: str

    group_col: str | None = None
    group_src: str | None = None
    group_conf: float = 0.0

    join_key_metric: str | None = None
    join_key_group: str | None = None
    join_conf: float = 0.0
    join_cardinality: str = ""
    join_hops: list[JoinHop] = field(default_factory=list)
    path_confidence: float = 0.0
    intermediate_sources: list[str] = field(default_factory=list)
    validation_notes: list[str] = field(default_factory=list)

    error: str | None = None
    mojo_ops: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AdaptiveSourceContext:
    """Per-source scoring baselines derived from the current customer/org data."""

    join_distinctiveness: tuple[tuple[float, int], ...] = ()
    column_distinctiveness: tuple[tuple[float, int], ...] = ()


__all__ = ["AdaptiveSourceContext", "JoinHop", "QueryPlan"]
