from __future__ import annotations

from bisect import bisect_right
from functools import lru_cache


def _build_line_start_offsets(text: str) -> tuple[int, ...]:
    starts = [0]
    search_start = 0
    while True:
        newline_index = text.find("\n", search_start)
        if newline_index < 0:
            break
        starts.append(newline_index + 1)
        search_start = newline_index + 1
    return tuple(starts)


@lru_cache(maxsize=1024)
def line_start_offsets(text: str) -> tuple[int, ...]:
    return _build_line_start_offsets(text)


def line_number_for_offset(
    text: str,
    offset: int,
    *,
    starts: tuple[int, ...] | None = None,
) -> int:
    bounded_offset = max(0, min(offset, len(text)))
    resolved_starts = line_start_offsets(text) if starts is None else starts
    return max(1, bisect_right(resolved_starts, bounded_offset))


__all__ = ["line_number_for_offset", "line_start_offsets"]
