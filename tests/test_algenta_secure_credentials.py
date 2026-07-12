from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_PACKAGE = ROOT / "packages" / "algenta"
if str(ALGENTA_PACKAGE) not in sys.path:
    sys.path.insert(0, str(ALGENTA_PACKAGE))

auth = importlib.import_module("algenta.auth")
cli = importlib.import_module("algenta.cli")
login = importlib.import_module("algenta.login")
paths = importlib.import_module("algenta.paths")


class _MemoryKeyring:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def set_password(self, service: str, account: str, value: str) -> None:
        self.values[(service, account)] = value

    def get_password(self, service: str, account: str) -> str | None:
        return self.values.get((service, account))

    def delete_password(self, service: str, account: str) -> None:
        self.values.pop((service, account), None)


@pytest.fixture
def memory_keyring(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _MemoryKeyring:
    backend = _MemoryKeyring()
    monkeypatch.setenv("ALGENTA_HOME", str(tmp_path))
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.delenv("ALGENTA_LICENSE_JWT", raising=False)
    monkeypatch.setattr(auth, "_keyring_module", lambda: backend)
    return backend


def test_algenta_credentials_use_verified_os_keyring_only(
    memory_keyring: _MemoryKeyring,
) -> None:
    auth.store_api_key(" de_live_secret ")
    auth.store_license(" signed-license ")

    assert auth.read_api_key() == "de_live_secret"
    assert auth.read_license() == "signed-license"
    assert not Path(paths.api_key_path()).exists()
    assert not Path(paths.token_path()).exists()
    assert not Path(paths.license_path()).exists()


def test_algenta_legacy_secret_is_removed_only_after_verified_migration(
    memory_keyring: _MemoryKeyring,
) -> None:
    legacy_path = Path(paths.api_key_path())
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text("de_live_legacy\n", encoding="utf-8")

    assert auth.read_api_key() == "de_live_legacy"
    assert not legacy_path.exists()
    assert memory_keyring.get_password("ai.algenta.cli", "api-key") == "de_live_legacy"


def test_algenta_login_persists_no_plaintext_or_credential_derived_output(
    monkeypatch: pytest.MonkeyPatch,
    memory_keyring: _MemoryKeyring,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(login, "device_authorize", lambda **_kwargs: "oauth-secret")
    monkeypatch.setattr(login, "create_api_key", lambda **_kwargs: "de_live_secret")
    monkeypatch.setattr(login, "register_device", lambda **_kwargs: "signed-license")
    monkeypatch.setattr(login, "device_id", lambda: "device-id")

    summary = login.login(open_browser=False)
    output = capsys.readouterr().out

    assert summary == {"credential_storage": "operating-system keyring"}
    assert "oauth-secret" not in output
    assert "de_live_secret" not in output
    assert "signed-license" not in output
    assert memory_keyring.get_password("ai.algenta.cli", "api-key") == "de_live_secret"
    assert memory_keyring.get_password("ai.algenta.cli", "device-license") == "signed-license"


def test_algenta_login_rolls_back_partial_keyring_write(
    monkeypatch: pytest.MonkeyPatch,
    memory_keyring: _MemoryKeyring,
) -> None:
    original_set = memory_keyring.set_password

    def _fail_license(service: str, account: str, value: str) -> None:
        if account == "device-license":
            raise RuntimeError("unavailable")
        original_set(service, account, value)

    monkeypatch.setattr(memory_keyring, "set_password", _fail_license)

    with pytest.raises(auth.CredentialStoreError, match="No secure operating-system"):
        auth.store_login_credentials("de_live_secret", "signed-license")

    assert memory_keyring.values == {}


def test_algenta_login_restores_existing_credentials_after_partial_write(
    monkeypatch: pytest.MonkeyPatch,
    memory_keyring: _MemoryKeyring,
) -> None:
    service = "ai.algenta.cli"
    memory_keyring.values[(service, "api-key")] = "existing-key"
    memory_keyring.values[(service, "device-license")] = "existing-license"
    original_set = memory_keyring.set_password

    def _fail_new_license(service_name: str, account: str, value: str) -> None:
        if account == "device-license" and value == "new-license":
            raise RuntimeError("unavailable")
        original_set(service_name, account, value)

    monkeypatch.setattr(memory_keyring, "set_password", _fail_new_license)

    with pytest.raises(auth.CredentialStoreError, match="No secure operating-system"):
        auth.store_login_credentials("new-key", "new-license")

    assert memory_keyring.values == {
        (service, "api-key"): "existing-key",
        (service, "device-license"): "existing-license",
    }


def test_algenta_cli_identity_output_never_contains_key_material(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(auth, "read_api_key", lambda: "de_live_secret")

    cli.cmd_whoami()

    assert capsys.readouterr().out.strip() == "logged in"


def test_algenta_package_declares_automatic_keyring_dependency() -> None:
    metadata = (ALGENTA_PACKAGE / "pyproject.toml").read_text(encoding="utf-8")

    assert '"keyring>=25,<26"' in metadata
