from __future__ import annotations

import builtins
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta"
for path in (str(ALGENTA_CORE), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

runtime_errors = importlib.import_module("algenta.runtime_errors")
runtime_local_limits = importlib.import_module("algenta.runtime_local_limits")
RuntimeConfigurationError = runtime_errors.RuntimeConfigurationError
RuntimeValidationError = runtime_errors.RuntimeValidationError
consume_local_credit = runtime_local_limits.consume_local_credit
ensure_local_execution_entitlement = runtime_local_limits.ensure_local_execution_entitlement
uses_hosted_local_limits = runtime_local_limits.uses_hosted_local_limits


def _reload_runtime_credits_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    module_name = "apps.runtime.credits"
    if module_name in sys.modules:
        return importlib.reload(sys.modules[module_name])
    return importlib.import_module(module_name)


def test_uses_hosted_local_limits_is_explicit() -> None:
    assert uses_hosted_local_limits(mode="local", enforce_limits=True) is True
    assert uses_hosted_local_limits(mode="local", enforce_limits=False) is False
    assert uses_hosted_local_limits(mode="api", enforce_limits=True) is False


def test_ensure_local_execution_entitlement_revalidates_existing_license() -> None:
    valid_license = SimpleNamespace(valid=True, message="", source="stored", plan="pro")

    with patch("apps.runtime.license.load_license", return_value=valid_license) as mocked:
        result = ensure_local_execution_entitlement(
            enabled=True,
            api_key="de_live_key",
            current_license=valid_license,
        )

    mocked.assert_called_once_with("de_live_key")
    assert result is valid_license


def test_ensure_local_execution_entitlement_loads_when_missing() -> None:
    loaded_license = SimpleNamespace(valid=True, message="", source="hosted", plan="team")

    with patch("apps.runtime.license.load_license", return_value=loaded_license) as mocked:
        result = ensure_local_execution_entitlement(
            enabled=True,
            api_key="de_live_key",
            current_license=None,
        )

    mocked.assert_called_once_with("de_live_key")
    assert result is loaded_license


def test_ensure_local_execution_entitlement_noop_when_all_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # P5: not enabled + require_local OFF + enforce OFF (defaults) → returns the existing license
    # untouched, no load_license call — today's behavior.
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_ENFORCE_LICENSE_VALIDATION", raising=False)
    monkeypatch.delenv("ALGENTA_REQUIRE_LOCAL_LICENSE", raising=False)
    sentinel = object()
    with patch("apps.runtime.license.load_license") as mocked:
        result = ensure_local_execution_entitlement(
            enabled=False, api_key=None, current_license=sentinel
        )
    mocked.assert_not_called()
    assert result is sentinel


def test_ensure_local_execution_entitlement_enforce_flag_gates_pure_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # P5: opting into enforce_license_validation gates pure-local Runtime() too — even with
    # enabled=False and require_local OFF, it must validate a license.
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_ENFORCE_LICENSE_VALIDATION", "1")
    monkeypatch.delenv("ALGENTA_REQUIRE_LOCAL_LICENSE", raising=False)
    invalid = SimpleNamespace(valid=False, message="x", source="none", plan="none")
    with patch("apps.runtime.license.load_license", return_value=invalid):
        with pytest.raises(RuntimeConfigurationError) as excinfo:
            ensure_local_execution_entitlement(
                enabled=False, api_key="", current_license=None
            )
    assert excinfo.value.code == "license_required"
    valid = SimpleNamespace(valid=True, message="", source="offline-local", plan="enterprise")
    with patch("apps.runtime.license.load_license", return_value=valid):
        result = ensure_local_execution_entitlement(
            enabled=False, api_key="", current_license=None
        )
    assert result is valid


def test_ensure_local_execution_entitlement_requires_api_key_when_enabled() -> None:
    with pytest.raises(RuntimeConfigurationError) as excinfo:
        ensure_local_execution_entitlement(
            enabled=True,
            api_key=None,
            current_license=None,
        )

    assert excinfo.value.code == "api_key_required"


def test_ensure_local_execution_entitlement_rejects_invalid_license() -> None:
    invalid_license = SimpleNamespace(
        valid=False,
        message="Hosted license required.",
        source="hosted",
        plan="none",
    )

    with patch("apps.runtime.license.load_license", return_value=invalid_license):
        with pytest.raises(RuntimeConfigurationError) as excinfo:
            ensure_local_execution_entitlement(
                enabled=True,
                api_key="de_live_key",
                current_license=None,
            )

    assert excinfo.value.code == "license_required"


def test_ensure_local_execution_entitlement_fails_closed_when_runtime_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "apps.runtime.license":
            raise ImportError("missing runtime license module")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _guarded_import)

    with pytest.raises(RuntimeConfigurationError) as excinfo:
        ensure_local_execution_entitlement(
            enabled=True,
            api_key="de_live_key",
            current_license=None,
        )

    assert excinfo.value.code == "hosted_local_runtime_unavailable"


def test_consume_local_credit_noops_when_disabled() -> None:
    consume_local_credit(
        enabled=False,
        run_sync=lambda coro: (_ for _ in ()).throw(AssertionError("should not run")),
    )


def test_consume_local_credit_rejects_quota_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sentinel = object()
    credits_module = _reload_runtime_credits_module(tmp_path, monkeypatch)
    seen: list[object] = []

    async def _fake_consume_credit(*, allow_background_refresh: bool):
        assert allow_background_refresh is False
        return sentinel

    def _run_sync(coro):
        seen.append(coro)
        coro.close()
        return False

    with patch.object(credits_module, "consume_credit", new=_fake_consume_credit):
        with pytest.raises(RuntimeValidationError) as excinfo:
            consume_local_credit(
                enabled=True,
                run_sync=_run_sync,
            )

    assert len(seen) == 1
    assert excinfo.value.code == "quota_exhausted"


def test_consume_local_credit_allows_permitted_execution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sentinel = object()
    seen: list[object] = []
    credits_module = _reload_runtime_credits_module(tmp_path, monkeypatch)

    async def _fake_consume_credit(*, allow_background_refresh: bool):
        assert allow_background_refresh is False
        return sentinel

    def _run_sync(coro):
        seen.append(coro)
        coro.close()
        return True

    with patch.object(credits_module, "consume_credit", new=_fake_consume_credit):
        consume_local_credit(
            enabled=True,
            run_sync=_run_sync,
        )

    assert len(seen) == 1


def test_consume_local_credit_fails_closed_when_runtime_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "apps.runtime.credits":
            raise ImportError("missing runtime credits module")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _guarded_import)

    with pytest.raises(RuntimeConfigurationError) as excinfo:
        consume_local_credit(enabled=True, run_sync=lambda coro: True)

    assert excinfo.value.code == "hosted_local_runtime_unavailable"


def _block_apps_privacy_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate a packaged (pip) install: `apps` does not ship in the wheel."""
    original_import = builtins.__import__

    def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "apps.privacy_policy":
            raise ImportError("No module named 'apps' (packaged install)")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _guarded_import)
    monkeypatch.delitem(sys.modules, "apps.privacy_policy", raising=False)


def test_packaged_install_policy_fallback_keeps_typed_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A pip-installed runtime has no `apps` package; the privacy-policy seam must fall back
    # to env-derived policy instead of raising ModuleNotFoundError mid-configuration.
    _block_apps_privacy_policy(monkeypatch)
    monkeypatch.delenv("ALGENTA_REQUIRE_LOCAL_LICENSE", raising=False)
    monkeypatch.delenv("ALGENTA_ENFORCE_LICENSE_VALIDATION", raising=False)

    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "saas")
    assert uses_hosted_local_limits(mode="local", enforce_limits=True) is True

    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    assert uses_hosted_local_limits(mode="local", enforce_limits=True) is False

    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "air_gapped")
    assert uses_hosted_local_limits(mode="local", enforce_limits=True) is False


def test_packaged_install_air_gapped_entitlement_fails_closed_typed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # air_gapped implies require_local_license; with no `apps` runtime components present the
    # entitlement check must fail closed with the typed code, never ModuleNotFoundError.
    _block_apps_privacy_policy(monkeypatch)
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "air_gapped")
    monkeypatch.delenv("ALGENTA_REQUIRE_LOCAL_LICENSE", raising=False)
    monkeypatch.delenv("ALGENTA_ENFORCE_LICENSE_VALIDATION", raising=False)

    original_import = builtins.__import__

    def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name in {"apps.privacy_policy", "apps.runtime.license"}:
            raise ImportError(f"No module named {name!r} (packaged install)")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _guarded_import)

    with pytest.raises(RuntimeConfigurationError) as excinfo:
        ensure_local_execution_entitlement(
            enabled=False, api_key="", current_license=None
        )

    assert excinfo.value.code == "hosted_local_runtime_unavailable"
