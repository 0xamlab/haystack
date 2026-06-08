"""Data connector schemas and connection testing service."""

from .schemas import (  # noqa: F401
    TYPE_NORMALIZE,
    VALID_TYPES,
    ConnectorCreate,
    ConnectorPreviewRequest,
    ConnectorResponse,
    ConnectorTestResult,
    ConnectorUpdate,
    normalize_type,
)
from .tester import (  # noqa: F401
    ConnectorTestOutcome,
    classify_connector_failure,
    test_connector_real,  # noqa: F401
    test_connector_real_detailed,
)

__all__ = [
    "TYPE_NORMALIZE",
    "VALID_TYPES",
    "ConnectorCreate",
    "ConnectorPreviewRequest",
    "ConnectorResponse",
    "ConnectorTestOutcome",
    "ConnectorTestResult",
    "ConnectorUpdate",
    "classify_connector_failure",
    "normalize_type",
    "test_connector_real",
    "test_connector_real_detailed",
]
