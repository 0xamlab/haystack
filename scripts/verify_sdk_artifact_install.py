"""Verify the public Python SDKs install + import from the BUILT ARTIFACT (wheel), not just source.

GTM Wave 1, item 2. The release workflow already builds + `twine check`s; this is the stronger
"a user can actually `pip install` it" proof: for each package, build the wheel + sdist, install
the wheel into a FRESH venv (no repo on sys.path), and run an import smoke in that venv. Catches
the classic "works from source but the wheel is missing modules / has bad metadata" failure.

Run locally or in CI:  python scripts/verify_sdk_artifact_install.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import venv
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_EXPECTED_VERSION = "1.0.0"

# pkg dir -> import-smoke executed inside the fresh venv (must not depend on the repo source tree).
_SMOKES: dict[str, str] = {
    "python-sdk": (
        "import decision_engine as m; "
        "from decision_engine import DecisionEngineClient, CodnaClient; "
        f"assert m.__version__ == {_EXPECTED_VERSION!r}, m.__version__; "
        "assert DecisionEngineClient and CodnaClient; "
        "print('python-sdk', m.__version__, 'OK')"
    ),
    "algenta-core": (
        "import algenta as m; "
        "from algenta import Runtime; "
        f"assert m.__version__ == {_EXPECTED_VERSION!r}, m.__version__; "
        "assert Runtime; "
        "print('algenta-core', m.__version__, 'OK')"
    ),
}


def _run(cmd: list[str], **kw) -> None:
    subprocess.run(cmd, check=True, **kw)


def _verify(pkg: str, smoke: str) -> None:
    pkg_dir = _ROOT / "packages" / pkg
    with tempfile.TemporaryDirectory(prefix=f"artifact-{pkg}-") as tmp:
        dist = Path(tmp) / "dist"
        _run([sys.executable, "-m", "build", "--outdir", str(dist), str(pkg_dir)])
        wheels = list(dist.glob("*.whl"))
        sdists = list(dist.glob("*.tar.gz"))
        assert wheels, f"{pkg}: no wheel built"
        assert sdists, f"{pkg}: no sdist built"

        env_dir = Path(tmp) / "venv"
        venv.create(env_dir, with_pip=True)
        py = env_dir / ("Scripts" if sys.platform == "win32" else "bin") / "python"
        _run([str(py), "-m", "pip", "install", "--quiet", str(wheels[0])])
        # Import smoke from a cwd with no repo source, so it loads the INSTALLED package.
        _run([str(py), "-c", smoke], cwd=tmp)
        print(f"[ok] {pkg}: built {wheels[0].name} + {sdists[0].name}, fresh-venv install + import OK")


def _verify_mcp() -> None:
    """algenta-mcp depends on algenta-sdk (not yet on PyPI), so build + install the SDK wheel
    first, then the mcp wheel (which pulls mcp/fastapi/starlette from PyPI), then import-smoke
    (exercises every decoupled tool) + run the console-script."""
    with tempfile.TemporaryDirectory(prefix="artifact-mcp-") as tmp:
        dist = Path(tmp) / "dist"
        for pkg in ("python-sdk", "mcp"):
            _run([sys.executable, "-m", "build", "--outdir", str(dist), str(_ROOT / "packages" / pkg)])
        env_dir = Path(tmp) / "venv"
        venv.create(env_dir, with_pip=True)
        bindir = env_dir / ("Scripts" if sys.platform == "win32" else "bin")
        py = bindir / "python"
        _run([str(py), "-m", "pip", "install", "--quiet", *(str(p) for p in dist.glob("algenta_sdk-*.whl"))])
        _run([str(py), "-m", "pip", "install", "--quiet", *(str(p) for p in dist.glob("algenta_mcp-*.whl"))])
        _run(
            [
                str(py),
                "-c",
                "import algenta_mcp.registry, algenta_mcp.server, algenta_mcp.client, algenta_mcp.config; "
                "print('algenta-mcp import OK')",
            ],
            cwd=tmp,
        )
        _run([str(bindir / "algenta-mcp"), "--help"])
        # Protocol/security tests against the INSTALLED package (auth forwarding, no key leak, ...).
        _run([str(py), "-m", "pip", "install", "--quiet", "pytest", "respx"])
        _run([str(py), "-m", "pytest", "-q", str(_ROOT / "packages" / "mcp" / "tests")])
        print("[ok] algenta-mcp: built + installed + import + console-script + protocol tests OK")


def main() -> int:
    for pkg, smoke in _SMOKES.items():
        _verify(pkg, smoke)
    _verify_mcp()
    print("\nAll Python SDK + MCP artifacts install + import from the wheel.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
