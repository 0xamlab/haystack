from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from apps.api_server.services.repository_intelligence import (
    RepositoryIntelligenceError,
    test_repository_connector,
)

from .tester_common import ConnectorTestOutcome, elapsed_ms, failure_outcome, success_outcome


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
        return failure_outcome(
            message=f"Repository source not found: {Path(exc.filename or '').name or exc}",
            latency_ms=elapsed_ms(started_at),
            exception=exc,
        )
    if not success:
        return failure_outcome(message=message, latency_ms=elapsed_ms(started_at))
    return success_outcome(message=message, latency_ms=elapsed_ms(started_at))
