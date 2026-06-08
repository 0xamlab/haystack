"""Structured MCP transport and tool error helpers."""

from __future__ import annotations

import json
from typing import Any


class MCPToolError(RuntimeError):
    def __init__(
        self,
        *,
        error_code: str,
        message: str,
        status_code: int,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or []

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error": {
                "code": self.error_code,
                "message": str(self),
                "status_code": self.status_code,
            }
        }
        if self.details:
            payload["error"]["details"] = self.details
        return payload


class UnsupportedMCPAuthConfigurationError(MCPToolError):
    def __init__(self, message: str) -> None:
        super().__init__(
            error_code="unsupported_mcp_auth_configuration",
            message=message,
            status_code=400,
        )


class MCPUpstreamUnavailableError(MCPToolError):
    def __init__(self, message: str) -> None:
        super().__init__(
            error_code="mcp_upstream_unavailable",
            message=message,
            status_code=503,
        )


class MCPAPIError(MCPToolError):
    def __init__(
        self,
        *,
        error_code: str,
        message: str,
        status_code: int,
        details: list[dict[str, Any]] | None = None,
        payload: Any | None = None,
    ) -> None:
        super().__init__(
            error_code=error_code,
            message=message,
            status_code=status_code,
            details=details,
        )
        self.payload = payload


class MCPPrivacyConfigurationError(MCPToolError):
    def __init__(self, message: str) -> None:
        super().__init__(
            error_code="mcp_privacy_configuration_error",
            message=message,
            status_code=403,
        )


def serialize_tool_error(exc: Exception, *, tool_name: str | None = None) -> str:
    if isinstance(exc, MCPToolError):
        return json.dumps(exc.to_payload(), sort_keys=True)
    if isinstance(exc, KeyError):
        return json.dumps(
            {
                "error": {
                    "code": "unknown_tool",
                    "message": f"Unknown tool: {tool_name or 'unknown'}",
                    "status_code": 404,
                }
            },
            sort_keys=True,
        )
    return json.dumps(
        {
            "error": {
                "code": "tool_error",
                "message": str(exc),
                "status_code": 500,
            }
        },
        sort_keys=True,
    )
