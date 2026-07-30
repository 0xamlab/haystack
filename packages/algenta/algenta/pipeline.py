"""Chained kernel execution: a whole DAG in one frame, on the local runtime.

`execute_batch` removes the per-call frame cost but keeps calls independent — any
step that consumes an earlier step's output still round-trips, and every
intermediate is encoded, shipped, decoded and re-encoded. Most real analysis is
exactly that shape. A pipeline keeps intermediates inside the worker.

    plan = (
        runtime.pipeline()
        .kernel("stats", "sort_values", [[3.0, 1.0, 2.0], 3])
        .kernel("stats", "median", [Ref(0), 3])
    )
    result = plan.execute()

`Ref(i)` refers to node i's output; `PREV` is shorthand for the previous node.
References must point backwards — a forward or self reference is rejected before
anything runs.

Shard constraint: a worker only contains its own shard's modules, so a plan whose
nodes span shards cannot execute in one frame. That raises `PipelineShardError`
rather than silently degrading, because a partially-executed DAG is worse than a
clear refusal. Keep a plan within one module group, which is the normal case when
the installed runtime is filtered to what the workflow needs.
"""

from __future__ import annotations

from typing import Any

__all__ = ["PREV", "Pipeline", "PipelineShardError", "Ref"]


class PipelineShardError(RuntimeError):
    """A plan's nodes are not all served by one worker."""

    code = "pipeline_spans_shards"


class Ref:
    """A reference to the output of an earlier node."""

    __slots__ = ("index",)

    def __init__(self, index: int) -> None:
        if index < 0:
            raise ValueError("node references must be non-negative")
        self.index = index

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Ref({self.index})"

    def wire(self) -> str:
        return f"${self.index}"


class _Prev:
    """Sentinel for 'the node immediately before this one'."""

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "PREV"


PREV = _Prev()


def _bind(value: Any, *, node_index: int) -> Any:
    """Turn Ref/PREV markers into their wire form, leaving other values alone."""
    if isinstance(value, Ref):
        return value.wire()
    if isinstance(value, _Prev):
        if node_index == 0:
            raise ValueError("PREV used on the first node, which has no predecessor")
        return f"${node_index - 1}"
    if isinstance(value, list):
        return [_bind(entry, node_index=node_index) for entry in value]
    return value


class Pipeline:
    """Builder for a chained kernel plan. Immutable-ish: `kernel()` returns self."""

    def __init__(self, runtime: Any) -> None:
        self._runtime = runtime
        self._nodes: list[dict[str, Any]] = []

    def kernel(self, module: str, function: str, args: Any = None) -> Pipeline:
        """Append a node. `args` may contain `Ref(i)` or `PREV`."""
        index = len(self._nodes)
        bound = _bind(args if args is not None else [], node_index=index)
        if not isinstance(bound, list):
            bound = [bound]
        self._nodes.append({"module": module, "function": function, "args": bound})
        return self

    def __len__(self) -> int:
        return len(self._nodes)

    def nodes(self) -> list[dict[str, Any]]:
        """The plan as it will be sent. Useful for inspection and tests."""
        return [dict(node) for node in self._nodes]

    def execute(self) -> dict[str, Any]:
        """Run the whole plan in one frame and return the worker's envelope."""
        return self._runtime.run_pipeline(self._nodes)
