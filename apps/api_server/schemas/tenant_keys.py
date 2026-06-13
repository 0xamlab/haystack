"""B10 PR11c: schemas for the self-serve per-tenant provider/engine key management API.

Key material is WRITE-ONLY: it is accepted on POST and never appears in any response."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SetProviderKeyRequest(BaseModel):
    backend: str = Field(
        ...,
        min_length=1,
        description=(
            "Provider backend (e.g. 'anthropic', 'openai', 'google_genai') or 'engine' for the "
            "Algenta engine key."
        ),
    )
    api_key: str = Field(
        ...,
        min_length=1,
        description="The provider/engine API key. Stored encrypted at rest; never returned.",
    )


class ProviderKeyInfo(BaseModel):
    backend: str
    updated_at: datetime


class ProviderKeyListResponse(BaseModel):
    # Configured backends only — key material is never included.
    keys: list[ProviderKeyInfo]
