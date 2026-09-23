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


class InvalidArgumentsError(MCPToolError):
    """A tool call failed input-schema validation before dispatch.

    Raised only by ``registry.call_tool``'s pre-dispatch validation, so a missing or
    ill-typed argument can never again surface as ``unknown_tool`` (the old bare-KeyError
    mapping) or as a handler KeyError whose precedence over the auth pre-flight depended
    on argument shape.
    """

    def __init__(self, *, tool_name: str, problem: str, field: str | None = None) -> None:
        super().__init__(
            error_code="invalid_arguments",
            message=f"Invalid arguments for tool '{tool_name}': {problem}.",
            status_code=400,
            details=(
                [{"argument": field, "problem": problem}] if field is not None else None
            ),
        )


class UnknownToolError(MCPToolError, KeyError):
    """A genuine dispatch miss: no registered (or visible) tool by that name.

    Also a ``KeyError`` so existing ``except KeyError`` callers keep working; the
    ``__str__`` override neutralizes ``KeyError.__str__`` (which would repr-wrap the
    message in quotes) so ``to_payload`` keeps the plain message.
    """

    def __init__(self, tool_name: str) -> None:
        super().__init__(
            error_code="unknown_tool",
            message=f"Unknown tool: {tool_name}",
            status_code=404,
        )

    def __str__(self) -> str:
        return BaseException.__str__(self)


def serialize_tool_error(exc: Exception, *, tool_name: str | None = None) -> str:
    if isinstance(exc, MCPToolError):
        return json.dumps(exc.to_payload(), sort_keys=True)
    # A bare KeyError is NOT a dispatch miss: only UnknownToolError (raised by
    # registry.call_tool's dispatch lookup) means "unknown tool". Any other KeyError
    # escaping a handler is an internal failure and falls through to tool_error/500.
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
