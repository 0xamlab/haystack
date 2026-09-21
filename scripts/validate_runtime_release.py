from __future__ import annotations

import argparse
import hashlib
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


def _load_bundle_manifest_module() -> Any:
    """The module that defines (and validates) the signed bundled-runtime manifest schema.

    The manifest that ships inside ``algenta_runtime_native/`` — the one
    ``algenta serve`` reads to decide whether it may launch the bundled CUDA engine
    — has its schema defined next to its generator, so this script re-uses that
    validator rather than restating the rules and risking drift.
    """
    import scripts.generate_runtime_bundle_manifest as schema

    return schema


class RuntimeReleaseValidationScriptError(ValueError):
    def __init__(
        self, code: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_bundle_manifest(path: str | Path) -> dict[str, Any]:
    """Validate one SIGNED bundled-runtime manifest: signature, schema, then bytes.

    This is the release-theorem check for the artifact that actually reaches a
    user's disk, and it is deliberately ordered so nothing is trusted before it is
    proven: the RS256 signature over the exact shipped bytes is verified FIRST
    (never a re-serialization of them), only then is the payload parsed against the
    generator's schema, and only then is every listed artifact re-hashed — which is
    what makes the manifest's `build_variant` and its `engine` block evidence about
    these binaries rather than a claim about them.

    Fails closed: raises ``RuntimeReleaseValidationScriptError`` on any problem.
    """
    manifest_path = Path(path)
    schema = _load_bundle_manifest_module()
    if not manifest_path.is_file():
        raise RuntimeReleaseValidationScriptError(
            "bundle_manifest_missing", f"no bundled runtime manifest at {manifest_path}"
        )
    sig_path = manifest_path.with_name("manifest.sig")
    if not sig_path.is_file():
        raise RuntimeReleaseValidationScriptError(
            "bundle_manifest_unsigned", f"{manifest_path} has no manifest.sig beside it"
        )

    sys.path.insert(0, str(ROOT / "packages" / "algenta"))
    try:
        from algenta.native import verify as native_verify

        manifest_bytes = manifest_path.read_bytes()
        manifest = native_verify.verify_manifest(
            manifest_bytes, sig_path.read_bytes(), pubkey=native_verify.release_public_key()
        )
    except RuntimeReleaseValidationScriptError:
        raise
    except Exception as exc:  # noqa: BLE001 - any verification failure is a refusal
        raise RuntimeReleaseValidationScriptError(
            "bundle_manifest_untrusted",
            f"the bundled runtime manifest did not verify against the release trust anchor: {exc}",
        ) from exc

    try:
        schema.validate_bundle_manifest(manifest)
    except schema.BundleManifestError as exc:
        raise RuntimeReleaseValidationScriptError(
            "bundle_manifest_schema_invalid", str(exc)
        ) from exc

    artifact_dir = manifest_path.parent
    for entry in manifest["artifacts"]:
        artifact = artifact_dir / entry["name"]
        if not artifact.is_file():
            raise RuntimeReleaseValidationScriptError(
                "bundle_artifact_missing",
                f"signed runtime artifact is missing: {entry['name']}",
            )
        actual = _sha256(artifact)
        if actual != entry["sha256"].lower():
            raise RuntimeReleaseValidationScriptError(
                "bundle_artifact_tampered",
                f"artifact integrity check FAILED for {entry['name']}: "
                f"expected {entry['sha256'][:12]}…, got {actual[:12]}…",
            )

    engine = manifest.get("engine")
    summary: dict[str, Any] = {
        "path": str(manifest_path),
        "platform": manifest["platform"],
        "build_variant": manifest["build_variant"],
        "artifact_count": len(manifest["artifacts"]),
        "engine": None,
    }
    if engine is not None:
        summary["engine"] = {
            "name": engine["name"],
            "source": engine["source"],
            "cuda_target": engine["cuda_target"],
            "comptime_define_count": len(engine["comptime_defines"]),
            "host_shared_libraries": list(engine["host_shared_libraries"]),
        }
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the signed Algenta runtime manifest against the formal release theorem."
        )
    )
    parser.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="Output format for the validation result.",
    )
    parser.add_argument(
        "--bundle-manifest",
        metavar="PATH",
        default=None,
        help=(
            "Also validate a SIGNED bundled-runtime manifest (the manifest.json that ships inside "
            "algenta_runtime_native/, or an unpacked wheel's copy). Verifies its signature, its "
            "schema — including build_variant and the bundled CUDA engine block — and re-hashes "
            "every artifact it lists. Optional: without it this script behaves exactly as before."
        ),
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


def _render_table(payload: object, bundle: dict[str, Any] | None = None) -> str:
    validation = _normalize_release_validation_payload(payload)
    deployment_mode = (
        validation.deployment_mode.value
        if validation.deployment_mode is not None
        else validation.deployment_mode_raw
    )
    lines = [
        (
            f"Algenta runtime release validation: {validation.runtime_version} "
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
    if bundle is not None:
        lines.append("Bundled runtime (the signed manifest inside the wheel):")
        lines.append(f"  path:          {bundle['path']}")
        lines.append(f"  platform:      {bundle['platform']}")
        lines.append(f"  build_variant: {bundle['build_variant']}")
        lines.append(f"  artifacts:     {bundle['artifact_count']} (all re-hashed, all matched)")
        engine = bundle.get("engine")
        if engine is None:
            lines.append("  engine:        none bundled")
        else:
            lines.append(f"  engine:        {engine['name']} ({engine['cuda_target']})")
            lines.append(f"    source:      {engine['source']}")
            lines.append(f"    defines:     {engine['comptime_define_count']} comptime defines")
            lines.append(
                "    host libs:   "
                + (", ".join(engine["host_shared_libraries"]) or "none")
            )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    bundle: dict[str, Any] | None = None
    if args.bundle_manifest:
        try:
            bundle = validate_bundle_manifest(args.bundle_manifest)
        except RuntimeReleaseValidationScriptError as exc:
            sys.stderr.write(f"{exc.code}: {exc}\n")
            return 1

    try:
        validation = _normalize_release_validation_payload(
            build_runtime_release_validation(get_runtime_manifest())
        )
    except RuntimeReleaseValidationScriptError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    if args.format == "json":
        payload = validation.model_dump(mode="json")
        if bundle is not None:
            payload["bundled_runtime_manifest"] = bundle
        sys.stdout.write(json.dumps(payload, indent=2))
        sys.stdout.write("\n")
    else:
        sys.stdout.write(_render_table(validation, bundle))
        sys.stdout.write("\n")
    return 0 if validation.valid_release else 1


if __name__ == "__main__":
    raise SystemExit(main())
