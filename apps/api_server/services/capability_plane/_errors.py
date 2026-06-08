"""CapabilityPlaneError + capability_plane_error_payload + _raise_error.

Extracted from apps/api_server/services/capability_plane.py during modularization.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable, Sequence
from urllib.parse import urlencode

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.models.capability_plane import (
    AuthorizationSessionStatus,
    BindingScope,
    BindingStatus,
    CapabilityBinding,
    CapabilityExecutionSession,
    CapabilityKind,
    CapabilityProvider,
    CapabilityProviderProfile,
    CapabilityRoutingOutcome,
    CapabilitySnapshot,
    ExecutionOwner,
    ExecutionSessionStatus,
    ImplementationKind,
    ProviderType,
)
from apps.api_server.models.data_connector import DataConnector
from apps.api_server.models.organization import Organization
from apps.api_server.services import source_registry as sreg
from apps.api_server.services.config_crypto import (
    decrypt_config_dict,
    decrypt_config_json,
    encrypt_config_dict,
)
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.workspace_scope import (
    workspace_id_for_write,
    workspace_scope_clauses,
)
from apps.api_server.services.connectors import test_connector_real_detailed
from apps.api_server.services.data_connection_browse import browse_connector_real_detailed
from apps.api_server.services.data_visibility import (
    filter_visible_datasets,
    get_visible_connector,
    get_visible_dataset_entry,
)
from apps.api_server.services.runtime_library_service import (
    execute_public_runtime_library,
    get_public_runtime_library_health,
    list_public_runtime_library_descriptors,
)
from apps.runtime_manifest import Replayability, RiskLevel, SideEffectClass

POLICY_SNAPSHOT_ID = "capability-plane-policy-v1"
SYSTEM_BINDING_REFRESH_TTL = timedelta(minutes=5)
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_.-]+")


from apps.api_server.services.capability_plane._constants import *  # noqa: F401, F403
from apps.api_server.services.capability_plane._constants import (
    _CATALOG_CACHE_TTL,
    _catalog_cache,
    _invalidate_catalog_cache,
)


class CapabilityPlaneError(ValueError):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def capability_plane_error_payload(exc: CapabilityPlaneError) -> dict[str, Any]:
    return {
        "error": {
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
        }
    }


def _raise_error(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    raise CapabilityPlaneError(
        status_code=status_code,
        code=code,
        message=message,
        details=details,
    )


