"""Shared additive pagination helpers for v1 list payloads."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class PaginationEnvelope[T]:
    items: list[T]
    total: int
    page: int
    limit: int
    pages: int


def paginate_sequence[T](
    items: Sequence[T],
    *,
    page: int,
    limit: int | None,
) -> PaginationEnvelope[T]:
    total = len(items)
    effective_limit = int(limit) if limit is not None else max(total, 1)
    offset = max(page - 1, 0) * effective_limit
    page_items = list(items[offset : offset + effective_limit])
    pages = max(1, (total + effective_limit - 1) // effective_limit)
    return PaginationEnvelope(
        items=page_items,
        total=total,
        page=page,
        limit=effective_limit,
        pages=pages,
    )
