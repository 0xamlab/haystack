from __future__ import annotations

import re

from algenta.runtime_api_exact import registration_fields
from algenta.runtime_intent import normalize_text
from algenta.runtime_model_source_registration import SourceRegistration

_BUNDLE_FIELD_TOKEN_RE = re.compile(r"[a-z0-9]+")


def bundle_field_tokens(field_name: str) -> set[str]:
    base_name = field_name.split("__", 1)[0]
    return set(_BUNDLE_FIELD_TOKEN_RE.findall(normalize_text(base_name)))


def field_overlap_score(left: str, right: str) -> float:
    left_tokens = bundle_field_tokens(left)
    right_tokens = bundle_field_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    shared = left_tokens & right_tokens
    if not shared:
        return 0.0
    return len(shared) / min(len(left_tokens), len(right_tokens))


def bundle_overlap_lines(registrations: list[SourceRegistration]) -> list[str]:
    overlap_lines: list[tuple[int, str]] = []
    for left_index, left in enumerate(registrations):
        left_fields = registration_fields(left)
        if not left_fields:
            continue
        for right in registrations[left_index + 1 :]:
            right_fields = registration_fields(right)
            if not right_fields:
                continue
            matches: dict[str, tuple[float, str]] = {}
            for left_field in left_fields:
                best_score = 0.0
                best_right: str | None = None
                for right_field in right_fields:
                    score = field_overlap_score(left_field, right_field)
                    if score > best_score:
                        best_score = score
                        best_right = right_field
                if best_right is None:
                    continue
                left_tokens = bundle_field_tokens(left_field)
                right_tokens = bundle_field_tokens(best_right)
                if best_score >= 1.0 and left_tokens and right_tokens:
                    matches[left_field] = (best_score, best_right)
                elif best_score >= 0.75 and min(len(left_tokens), len(right_tokens)) >= 2:
                    matches[left_field] = (best_score, best_right)
            if not matches:
                continue
            summarized = [
                f"{left_field} ~ {right_field}"
                for left_field, (_score, right_field) in sorted(
                    matches.items(),
                    key=lambda item: (-item[1][0], item[0].lower(), item[1][1].lower()),
                )[:3]
            ]
            left_name = left.name or left.dataset_id or "source"
            right_name = right.name or right.dataset_id or "source"
            overlap_lines.append(
                (
                    len(matches),
                    f"{left_name} ↔ {right_name}: {', '.join(summarized)}",
                )
            )
    return [
        line
        for _count, line in sorted(overlap_lines, key=lambda item: (-item[0], item[1].lower()))[:5]
    ]
