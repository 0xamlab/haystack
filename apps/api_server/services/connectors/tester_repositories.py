from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import structlog

from apps.api_server.services.repository_intelligence import (
    RepositoryIntelligenceError,
    test_repository_connector,
)

from .tester_common import ConnectorTestOutcome, elapsed_ms, failure_outcome, success_outcome

logger = structlog.get_logger(__name__)


async def test_repository_connector_config(
    connector_type: str,
    config: dict[str, Any],
) -> ConnectorTestOutcome:
    started_at = time.perf_counter()
    try:
        success, message = test_repository_connector(connector_type=connector_type, config=config)
    except RepositoryIntelligenceError as exc:
        return failure_outcome(
            message=exc.message,
            latency_ms=elapsed_ms(started_at),
            error_type=exc.code if exc.code in {"auth", "permission", "not_found", "rate_limit", "timeout", "invalid_config", "invalid_identifier", "unknown"} else None,
        )
    except FileNotFoundError as exc:
        logger.exception("connector_test_failed", connector="repository")
        basename = Path(exc.filename or "").name
        if basename:
            safe_message = f"Repository source not found: {basename}"
        else:
            safe_message = "Repository source not found."
        return failure_outcome(
            message=safe_message,
            latency_ms=elapsed_ms(started_at),
            exception=exc,
        )
    if not success:
        return failure_outcome(message=message, latency_ms=elapsed_ms(started_at))
    return success_outcome(message=message, latency_ms=elapsed_ms(started_at))
