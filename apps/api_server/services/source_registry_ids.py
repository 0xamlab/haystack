from __future__ import annotations

import hashlib
import uuid


def source_id_for(content_key: str | None, *, path_key: str | None = None) -> str:
    """
    Deterministic source ID.
    content_key  — sha256 hex of the raw content bytes (inline sources)
    path_key     — type:name string (file/url/connection sources, no content hash)
    """
    raw = content_key or path_key or str(uuid.uuid4())
    return hashlib.sha256(raw.encode()).hexdigest()[:24]
