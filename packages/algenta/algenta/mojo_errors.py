from __future__ import annotations

from typing import Any


class MojoRuntimeError(RuntimeError):
    """Base error for the public runtime-backed Mojo library surface."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


class MojoRuntimeConfigurationError(MojoRuntimeError):
    """Raised when the local Mojo runtime SDK is unavailable."""


class MojoModuleNotRegisteredError(MojoRuntimeError):
    """Raised when a requested executable module is not registered."""


class MojoFunctionNotRegisteredError(MojoRuntimeError):
    """Raised when a requested executable function is not registered."""


class MojoExecutionError(MojoRuntimeError):
    """Raised when the local runtime cannot execute a Mojo library call."""
