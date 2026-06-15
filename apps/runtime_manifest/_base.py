"""RuntimeManifestBaseModel — base Pydantic config for every manifest model.

Extracted from apps/runtime_manifest.py during modularization.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import subprocess
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, TypeVar, get_origin

from pydantic import (
    BaseModel,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    ValidationError,
    field_validator,
    model_validator,
)

from apps.api_server.config import get_settings
from apps.api_server.services.execution_policy_service import default_policy_payload
from apps.platform_contract import load_platform_contract_manifest
from apps.runtime.mojo_inventory import build_inventory_report
from apps.runtime_manifest._module_order import LLM_ROLLOUT_MODULE_ORDER



class RuntimeManifestBaseModel(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def validate_list_fields_use_json_arrays(
        cls,
        value: Any,
    ) -> Any:
        if not isinstance(value, dict):
            return value
        for field_name, field_info in cls.model_fields.items():
            if field_name not in value:
                continue
            if get_origin(field_info.annotation) is not list:
                continue
            field_value = value[field_name]
            if field_value is None or isinstance(field_value, list):
                continue
            raise ValueError(f"{field_name} must be provided as a list.")
        return value


