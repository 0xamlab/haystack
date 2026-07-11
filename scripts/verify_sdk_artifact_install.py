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
        "from decision_engine import DecisionEngineClient, AlgentaClient; "
        f"assert m.__version__ == {_EXPECTED_VERSION!r}, m.__version__; "
        "assert DecisionEngineClient and AlgentaClient; "
        "print('python-sdk', m.__version__, 'OK')"
    ),
    # NB: `algenta` (graduated) is verified by _verify_algenta() below (it hard-deps the
    # native runtime wheel, so needs a local runtime wheel first). The `algenta-core` shim
    # ships no importable files, so it has no smoke here.
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


def _verify_algenta() -> None:
    """The graduated `algenta` CLI hard-depends on the proprietary `algenta-runtime-native` wheel. In CI
    the full runtime artifact is built by build-runtime, so this lean artifact gate builds BOTH wheels locally
    with an explicitly empty runtime wheel for metadata/import proof. That wheel is allowed only here, where
    the loader must fail closed on execute, not import. Then run import-smoke + `algenta runtime doctor`
    without ever mentioning Mojo."""
    import os

    with tempfile.TemporaryDirectory(prefix="artifact-algenta-") as tmp:
        dist = Path(tmp) / "dist"
        env = {k: v for k, v in os.environ.items() if k != "ALGENTA_BUNDLE_RUNTIME"}
        env["ALGENTA_ALLOW_EMPTY_RUNTIME_NATIVE_WHEEL"] = "1"
        for pkg in ("algenta-runtime-native", "algenta"):
            _run([sys.executable, "-m", "build", "--outdir", str(dist), str(_ROOT / "packages" / pkg)], env=env)
        env_dir = Path(tmp) / "venv"
        venv.create(env_dir, with_pip=True)
        bindir = env_dir / ("Scripts" if sys.platform == "win32" else "bin")
        py = bindir / "python"
        wheels = [str(p) for p in dist.glob("*.whl")]
        assert wheels, "algenta: no wheels built"
        # Install both local wheels together so the native-runtime hard dependency resolves locally.
        _run([str(py), "-m", "pip", "install", "--quiet", *wheels])
        _run(
            [
                str(py),
                "-c",
                "import algenta as m; from algenta import Runtime; "
                "from algenta.native import loader, doctor, verify; "
                f"assert m.__version__ == {_EXPECTED_VERSION!r}, m.__version__; "
                "assert Runtime and doctor and verify; "
                "assert loader.available() is False; "  # no bundled native runtime in this metadata smoke
                "print('algenta', m.__version__, 'OK')",
            ],
            cwd=tmp,
        )
        # The console script + `runtime doctor` run without the native lib; doctor must emit the invariant
        # lines and NEVER leak Mojo/Modular/Docker (the clean-machine contract, mini version).
        r = subprocess.run(
            [str(bindir / "algenta"), "runtime", "doctor"], cwd=tmp, capture_output=True, text=True
        )
        out = (r.stdout + r.stderr).lower()
        assert "in-process" in out and "denied" in out and "tcp listeners" in out, out
        for forbidden in ("mojo", "modular", "docker", "command not found"):
            assert forbidden not in out, f"algenta runtime doctor leaked {forbidden!r}: {out}"
        print("[ok] algenta: native-runtime + CLI wheels install + import + runtime doctor (fail-closed, no Mojo) OK")


def main() -> int:
    for pkg, smoke in _SMOKES.items():
        _verify(pkg, smoke)
    _verify_algenta()
    _verify_mcp()
    print("\nAll Python SDK + MCP artifacts install + import from the wheel.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
