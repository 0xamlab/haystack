#!/usr/bin/env python3
"""Detects whether `algenta-runtime-native` publishes a wheel compatible with
this machine, and reports the result to GitHub Actions (`supported=true|false`
in `$GITHUB_OUTPUT`) so the workflow can run the demo where it is meaningful
and loudly SKIP where no runtime exists.

Exit codes:
    0 — detection completed (see the `supported` output for the answer)
    1 — detection itself failed (network, index, or unexpected platform);
        the job must fail rather than silently skip

Stdlib-only so it runs on any GitHub-hosted runner image (Python 3.8+).
"""

from __future__ import annotations

import json
import os
import platform
import re
import sys
import urllib.request

PACKAGE = "algenta-runtime-native"
PYPI_JSON_URL = f"https://pypi.org/pypi/{PACKAGE}/json"
REQUEST_TIMEOUT_SECONDS = 20


def _macos_major() -> int | None:
    """Major version of the running macOS (e.g. 26 for macOS 26.6.2)."""
    version = platform.mac_ver()[0]
    if not version:
        return None
    try:
        return int(version.split(".")[0])
    except ValueError:
        return None


def _glibc_minor() -> int | None:
    """glibc minor version of the running system (e.g. 39 for glibc 2.39)."""
    name, version = platform.libc_ver()
    if name != "glibc" or not version:
        return None
    try:
        return int(version.split(".")[1])
    except (IndexError, ValueError):
        return None


def compatible_wheel(filename: str) -> bool:
    """True when `filename` is a wheel this machine could install."""
    if not filename.endswith(".whl"):
        return False
    if sys.platform == "darwin" and platform.machine() == "arm64":
        match = re.search(r"macosx_(\d+)_\d+_arm64\.whl$", filename)
        macos = _macos_major()
        # Apple preserves binary compatibility within later major releases.
        return bool(match and macos is not None and int(match.group(1)) <= macos)
    if sys.platform.startswith("linux") and platform.machine() in ("x86_64", "amd64"):
        match = re.search(r"manylinux_2_(\d+)_x86_64\.whl$", filename)
        glibc = _glibc_minor()
        return bool(match and glibc is not None and int(match.group(1)) <= glibc)
    return False


def platform_label() -> str:
    return f"{sys.platform}/{platform.machine()}"


def emit_output(supported: bool) -> None:
    print(f"supported={str(supported).lower()}")
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(f"supported={str(supported).lower()}\n")


def main() -> int:
    try:
        request = urllib.request.Request(
            PYPI_JSON_URL, headers={"User-Agent": "algenta-sdk-ci"}
        )
        with urllib.request.urlopen(
            request, timeout=REQUEST_TIMEOUT_SECONDS
        ) as response:
            index = json.load(response)
    except (OSError, ValueError) as exc:
        print(f"::error::could not query the PyPI index for {PACKAGE}: {exc}")
        return 1

    compatible = sorted(
        f"{version}: {artifact['filename']}"
        for version, artifacts in index.get("releases", {}).items()
        for artifact in artifacts
        if compatible_wheel(artifact.get("filename", ""))
    )

    if compatible:
        print(f"{PACKAGE} wheels compatible with {platform_label()}:")
        for entry in compatible:
            print(f"  {entry}")
        emit_output(True)
        return 0

    print(
        f"::notice::No {PACKAGE} wheel is published for {platform_label()} — "
        "the Mojo quickstart demo cannot run here and will be SKIPPED. "
        "This is an explicit, expected skip, not a pass."
    )
    emit_output(False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
