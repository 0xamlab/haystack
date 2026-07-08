from __future__ import annotations

import contextlib
import time
from collections.abc import Callable, MutableMapping
from typing import Any

from algenta.runtime_connector_definitions import _stable_connector_hash
from algenta.runtime_connector_preview_state import INLINE_PREVIEW_PREFIX
from algenta.runtime_errors import RuntimeValidationError


def cleanup_inline_preview_connectors(
    pending_cleanup: MutableMapping[str, float],
    *,
    uses_api_transport: bool,
    client: Any | None,
    force_ids: set[str] | None = None,
    now_epoch: Callable[[], float] = time.time,
) -> None:
    if not uses_api_transport or client is None:
        return
    forced = force_ids or set()
    now = now_epoch()
    for connector_id, expires_at_epoch in dict(pending_cleanup).items():
        if connector_id not in forced and expires_at_epoch > now:
            continue
        with contextlib.suppress(Exception):
            client.delete_connector(connector_id)
            pending_cleanup.pop(connector_id, None)


def run_with_inline_preview_connector(
    *,
    connector_type: str,
    config: dict[str, Any],
    operation: str,
    pending_cleanup: MutableMapping[str, float],
    create_connector: Callable[..., Any],
    cleanup_connectors: Callable[..., None],
    remember_inline_preview: Callable[[str, float], None],
    callback: Callable[[str], Any],
    inline_preview_description: Callable[[str, str | None], tuple[str, float]],
    consume_inline_preview_slot: Callable[[], None] | None = None,
    enforce_rate_limit: bool = True,
    now_epoch: Callable[[], float] = time.time,
) -> Any:
    if enforce_rate_limit and consume_inline_preview_slot is not None:
        consume_inline_preview_slot()
    cleanup_connectors()
    inline_hash = _stable_connector_hash({"connector_type": connector_type, "config": config})[:10]
    name = f"{INLINE_PREVIEW_PREFIX}-{int(now_epoch() * 1000)}-{inline_hash}"
    description, expires_at_epoch = inline_preview_description(
        connector_type,
        f"Ephemeral SDK {operation} preview.",
    )
    connector = create_connector(
        name=name,
        connector_type=connector_type,
        config=config,
        description=description,
        visibility="private",
    )
    remember_inline_preview(connector.id, expires_at_epoch=expires_at_epoch)
    try:
        return callback(connector.id)
    finally:
        cleanup_connectors(force_ids={connector.id})
        if connector.id in pending_cleanup:
            raise RuntimeValidationError(
                "inline_preview_cleanup_failed",
                (
                    "Inline preview cleanup failed for the temporary connector. "
                    "Use a saved connector for governed production workflows."
                ),
                {"connector_id": connector.id},
            )


__all__ = [
    "cleanup_inline_preview_connectors",
    "run_with_inline_preview_connector",
]
