"""Hatch build hook: bundle the CI-built Algenta runtime into a platform-tagged wheel.

Gated on ``ALGENTA_BUNDLE_RUNTIME=1``. Release wheels contain the prebuilt runtime
worker, a signed manifest, and the release public key needed to verify that
manifest offline. The package is an automatic dependency of ``algenta``; users do
not install or configure it directly.
"""

from __future__ import annotations

import os
import sys

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    PLUGIN_NAME = "algenta-runtime-native"

    def initialize(self, version: str, build_data: dict) -> None:  # noqa: ARG002
        if os.environ.get("ALGENTA_BUNDLE_RUNTIME") != "1":
            if os.environ.get("ALGENTA_ALLOW_EMPTY_RUNTIME_NATIVE_WHEEL") == "1":
                return
            raise RuntimeError(
                "algenta-runtime-native cannot be built as an empty wheel. "
                "Set ALGENTA_BUNDLE_RUNTIME=1 after compiling and signing the "
                "runtime artifacts, or set ALGENTA_ALLOW_EMPTY_RUNTIME_NATIVE_WHEEL=1 "
                "only for explicit local metadata smoke tests."
            )

        src_dir = os.environ.get("ALGENTA_RUNTIME_SRC") or os.path.abspath(
            os.path.join(self.root, "..", "..", "mojo_build")
        )
        worker_name = (
            "algenta-runtime-worker.exe"
            if sys.platform.startswith("win")
            else "algenta-runtime-worker"
        )
        required = (
            os.path.join(src_dir, worker_name),
            os.path.join(src_dir, "manifest.json"),
            os.path.join(src_dir, "manifest.sig"),
            os.path.join(src_dir, "algenta_release_pub.pem"),
        )
        for artifact in required:
            if not os.path.exists(artifact):
                raise FileNotFoundError(
                    "ALGENTA_BUNDLE_RUNTIME=1 but a required runtime artifact is "
                    f"missing: {artifact}. The build-runtime workflow must compile, "
                    "sign, and stage the bundled runtime before building the wheel."
                )

        force_include = build_data.setdefault("force_include", {})
        force_include[required[0]] = f"algenta_runtime_native/{worker_name}"
        force_include[required[1]] = "algenta_runtime_native/manifest.json"
        force_include[required[2]] = "algenta_runtime_native/manifest.sig"
        force_include[required[3]] = "algenta_runtime_native/algenta_release_pub.pem"

        stem = "libalgenta_runtime"
        ext = (
            "dylib"
            if sys.platform == "darwin"
            else ("dll" if sys.platform.startswith("win") else "so")
        )
        lib = os.path.join(src_dir, f"{stem}.{ext}")
        if os.path.exists(lib):
            force_include[lib] = f"algenta_runtime_native/{stem}.{ext}"

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
                    "macOS runtime tag build is missing the Secure Enclave helper "
                    "(se/algenta-se-helper + manifest.json + manifest.sig). Run "
                    "scripts/build_se_helper.py before building the runtime wheel."
                )

        build_data["pure_python"] = False
        build_data["infer_tag"] = True
