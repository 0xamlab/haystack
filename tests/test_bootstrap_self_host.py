from __future__ import annotations
# ruff: noqa: I001

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "bootstrap_self_host.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("bootstrap_self_host_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("bootstrap_self_host_test", module)
    spec.loader.exec_module(module)
    return module


def test_generate_password_is_alphanumeric_and_expected_length() -> None:
    module = _load_module()

    password = module._generate_password()

    assert len(password) == module.PASSWORD_LENGTH
    assert password.isalnum()


def test_render_result_uses_machine_readable_lines() -> None:
    module = _load_module()
    result = module.BootstrapResult(
        org_slug="self-hosted-org",
        user_email="owner@selfhost.algenta.ai",
        user_password="secret-password",
        user_created=True,
        api_key_id="11111111-2222-3333-4444-555555555555",
        api_key_prefix="de_test_abcd",
        api_key="de_test_abcdefghijklmnopqrstuvwxyz123456",
    )

    rendered = module._render_result(result)

    assert "ALGENTA_BOOTSTRAP_READY=1" in rendered
    assert "BOOTSTRAP_ORG_SLUG=self-hosted-org" in rendered
    assert "BOOTSTRAP_USER_EMAIL=owner@selfhost.algenta.ai" in rendered
    assert "BOOTSTRAP_USER_CREATED=1" in rendered
    assert "BOOTSTRAP_API_KEY_ID=11111111-2222-3333-4444-555555555555" in rendered
    assert "BOOTSTRAP_API_KEY_PREFIX=de_test_abcd" in rendered
    assert "BOOTSTRAP_API_KEY=de_test_abcdefghijklmnopqrstuvwxyz123456" in rendered
    assert "BOOTSTRAP_USER_PASSWORD=secret-password" in rendered
