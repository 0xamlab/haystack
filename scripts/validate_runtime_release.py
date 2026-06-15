from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.runtime_manifest import (
    RuntimeReleaseValidationResponse,
    build_runtime_release_validation,
    get_runtime_manifest,
    normalize_runtime_validation_payload,
)
from apps.validation_error_details import build_validation_error_details, format_validation_error_message


class RuntimeReleaseValidationScriptError(ValueError):
    def __init__(
        self, code: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the signed Codna runtime manifest against the formal release theorem."
        )
    )
    parser.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="Output format for the validation result.",
    )
    return parser


def _normalize_release_validation_payload(
    payload: object,
) -> RuntimeReleaseValidationResponse:
    try:
        return RuntimeReleaseValidationResponse.model_validate(
            normalize_runtime_validation_payload(payload)
        )
    except ValidationError as exc:
        details = build_validation_error_details(exc)
        raise RuntimeReleaseValidationScriptError(
            "invalid_runtime_release_validation_payload",
            format_validation_error_message(
                "Release validation payload does not match the signed runtime validation schema.",
                exc,
            ),
            details,
        ) from exc


def _render_table(payload: object) -> str:
    validation = _normalize_release_validation_payload(payload)
    deployment_mode = (
        validation.deployment_mode.value
        if validation.deployment_mode is not None
        else validation.deployment_mode_raw
    )
    lines = [
        (
            f"Codna runtime release validation: {validation.runtime_version} "
            f"[{validation.llm_core_manifest}]"
        ),
        f"Deployment:      {deployment_mode}",
        f"Manifest digest: {validation.manifest_digest}",
        f"Valid release:   {validation.valid_release}",
        f"Theorem:         {validation.theorem_statement}",
        "Conditions:",
    ]
    for condition in validation.conditions:
        label = "pass" if condition.satisfied else "FAIL"
        lines.append(
            f"  - {condition.condition.value}: {label} — {condition.detail}"
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        validation = _normalize_release_validation_payload(
            build_runtime_release_validation(get_runtime_manifest())
        )
    except RuntimeReleaseValidationScriptError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    if args.format == "json":
        sys.stdout.write(json.dumps(validation.model_dump(mode="json"), indent=2))
        sys.stdout.write("\n")
    else:
        sys.stdout.write(_render_table(validation))
        sys.stdout.write("\n")
    return 0 if validation.valid_release else 1


if __name__ == "__main__":
    raise SystemExit(main())
