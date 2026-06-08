from __future__ import annotations


def _normalize_source_registration_request(
    source: dict[str, object] | None,
    *,
    description: str | None = None,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    remainder = dict(extra or {})
    if source is None:
        embedded_source = remainder.pop("source", None)
        payload = {"source": embedded_source if isinstance(embedded_source, dict) else remainder}
        remainder = {}
    elif isinstance(source.get("source"), dict):
        payload = dict(source)
    else:
        payload = {"source": dict(source)}

    payload.update(remainder)
    if description is not None:
        payload["description"] = description
    return payload


__all__ = ["_normalize_source_registration_request"]
