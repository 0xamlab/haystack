"""Hatch build hook: bundle the CI-built native runtime + signed manifest into a PLATFORM-TAGGED wheel.

Gated on ``ALGENTA_BUNDLE_RUNTIME=1`` (the build-runtime CI sets it after compiling + RS256-signing the Mojo
runtime). Force-includes the artifacts into the ``algenta_runtime_native`` package and marks the wheel
non-pure + platform-tagged so pip resolves the right build per OS/arch. When unset, produces a plain
(empty-of-native) wheel — useful for dev, never published. Invariant: a PUBLISHED sidecar wheel always
contains the native lib; an unsupported platform simply has no wheel (a generic pip "no matching
distribution"), never a wheel that later asks for Mojo.
"""
from __future__ import annotations

import os
import sys

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    PLUGIN_NAME = "algenta-runtime-native"

    def initialize(self, version: str, build_data: dict) -> None:  # noqa: ARG002
        if os.environ.get("ALGENTA_BUNDLE_RUNTIME") != "1":
            return  # dev build: no native bundled (never published)

        stem = "libalgenta_runtime"
        ext = "dylib" if sys.platform == "darwin" else ("dll" if sys.platform.startswith("win") else "so")
        src_dir = os.environ.get("ALGENTA_RUNTIME_SRC") or os.path.abspath(
            os.path.join(self.root, "..", "..", "mojo_build")
        )
        lib = os.path.join(src_dir, f"{stem}.{ext}")
        manifest = os.path.join(src_dir, "manifest.json")
        sig = os.path.join(src_dir, "manifest.sig")
        for required in (lib, manifest, sig):
            if not os.path.exists(required):
                raise FileNotFoundError(
                    f"ALGENTA_BUNDLE_RUNTIME=1 but a required artifact is missing: {required}. "
                    "The build-runtime CI must compile + RS256-sign the runtime (lib + manifest.json + "
                    "manifest.sig) before building the sidecar wheel."
                )

        force_include = build_data.setdefault("force_include", {})
        force_include[lib] = f"algenta_runtime_native/{stem}.{ext}"
        force_include[manifest] = "algenta_runtime_native/manifest.json"
        force_include[sig] = "algenta_runtime_native/manifest.sig"

        # macOS only: bundle the PREBUILT + code-signed + RS256-manifest-signed Secure Enclave helper
        # (scripts/build_se_helper.py wrote it under <src>/se) so the runtime verifies + runs it instead of
        # JIT-compiling swiftc — the clean-machine contract (no runtime compiler). The runtime resolves it
        # via importlib.resources("algenta_runtime_native")/se and fails closed if the manifest doesn't verify.
        if sys.platform == "darwin":
            se_dir = os.path.join(src_dir, "se")
            se_bin = os.path.join(se_dir, "algenta-se-helper")
            se_manifest = os.path.join(se_dir, "manifest.json")
            se_sig = os.path.join(se_dir, "manifest.sig")
            if all(os.path.exists(p) for p in (se_bin, se_manifest, se_sig)):
                force_include[se_bin] = "algenta_runtime_native/se/algenta-se-helper"
                force_include[se_manifest] = "algenta_runtime_native/se/manifest.json"
                force_include[se_sig] = "algenta_runtime_native/se/manifest.sig"
            elif os.environ.get("GITHUB_REF", "").startswith("refs/tags/"):
                raise FileNotFoundError(
                    "macOS sidecar tag build is missing the Secure Enclave helper "
                    "(se/algenta-se-helper + manifest.json + manifest.sig). Run scripts/build_se_helper.py "
                    "before building the sidecar wheel."
                )

        build_data["pure_python"] = False
        build_data["infer_tag"] = True
