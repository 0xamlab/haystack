from __future__ import annotations

from tests.integration import live_local_auth_bootstrap as bootstrap
from tests.integration.live_local_defaults import DEFAULT_LOCAL_LIVE_API_KEY


def test_is_local_live_base_url_accepts_loopback_hosts() -> None:
    assert bootstrap.is_local_live_base_url("http://127.0.0.1:8000") is True
    assert bootstrap.is_local_live_base_url("http://localhost:8000") is True
    assert bootstrap.is_local_live_base_url("https://[::1]:8000") is True
    assert bootstrap.is_local_live_base_url("https://example.com") is False
    assert bootstrap.is_local_live_base_url(None) is False


def test_ensure_bootstrapped_local_live_api_key_returns_configured_key_unchanged(
    monkeypatch,
) -> None:
    called: dict[str, int] = {"migrations": 0, "seed": 0}

    def _fake_migrations() -> None:
        called["migrations"] += 1

    async def _fake_seed(_database_url: str) -> str:
        called["seed"] += 1
        return "de_live_real"

    monkeypatch.setattr(bootstrap, "run_local_live_migrations", _fake_migrations)
    monkeypatch.setattr(bootstrap, "_seed_placeholder_live_api_key_async", _fake_seed)

    key, configured, reason = bootstrap.ensure_bootstrapped_local_live_api_key(
        api_key="de_live_real",
        api_key_configured=True,
        active_base_url="http://127.0.0.1:8000",
    )

    assert key == "de_live_real"
    assert configured is True
    assert reason is None
    assert called == {"migrations": 0, "seed": 0}


def test_ensure_bootstrapped_local_live_api_key_reseeds_configured_placeholder_key(
    monkeypatch,
) -> None:
    called: dict[str, int] = {"migrations": 0, "seed": 0}

    def _fake_migrations() -> None:
        called["migrations"] += 1

    async def _fake_seed(_database_url: str) -> str:
        called["seed"] += 1
        return DEFAULT_LOCAL_LIVE_API_KEY

    monkeypatch.setenv("DE_API_KEY", DEFAULT_LOCAL_LIVE_API_KEY)
    monkeypatch.setenv("ALGENTA_API_KEY", DEFAULT_LOCAL_LIVE_API_KEY)
    monkeypatch.setattr(bootstrap, "run_local_live_migrations", _fake_migrations)
    monkeypatch.setattr(bootstrap, "_seed_placeholder_live_api_key_async", _fake_seed)

    key, configured, reason = bootstrap.ensure_bootstrapped_local_live_api_key(
        api_key=DEFAULT_LOCAL_LIVE_API_KEY,
        api_key_configured=True,
        active_base_url="http://127.0.0.1:8000",
    )

    assert key == DEFAULT_LOCAL_LIVE_API_KEY
    assert configured is True
    assert reason is None
    assert called == {"migrations": 1, "seed": 1}


def test_ensure_bootstrapped_local_live_api_key_bootstraps_placeholder_for_local_base(
    monkeypatch,
) -> None:
    called: dict[str, int] = {"migrations": 0, "seed": 0}

    def _fake_migrations() -> None:
        called["migrations"] += 1

    async def _fake_seed(_database_url: str) -> str:
        called["seed"] += 1
        return DEFAULT_LOCAL_LIVE_API_KEY

    monkeypatch.delenv("DE_API_KEY", raising=False)
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.setattr(bootstrap, "run_local_live_migrations", _fake_migrations)
    monkeypatch.setattr(bootstrap, "_seed_placeholder_live_api_key_async", _fake_seed)

    key, configured, reason = bootstrap.ensure_bootstrapped_local_live_api_key(
        api_key=DEFAULT_LOCAL_LIVE_API_KEY,
        api_key_configured=False,
        active_base_url="http://127.0.0.1:8000",
    )

    assert key == DEFAULT_LOCAL_LIVE_API_KEY
    assert configured is True
    assert reason is None
    assert called == {"migrations": 1, "seed": 1}


def test_ensure_bootstrapped_local_live_api_key_rejects_remote_base(
    monkeypatch,
) -> None:
    called: dict[str, int] = {"migrations": 0, "seed": 0}

    def _fake_migrations() -> None:
        called["migrations"] += 1

    async def _fake_seed(_database_url: str) -> str:
        called["seed"] += 1
        return DEFAULT_LOCAL_LIVE_API_KEY

    monkeypatch.setattr(bootstrap, "run_local_live_migrations", _fake_migrations)
    monkeypatch.setattr(bootstrap, "_seed_placeholder_live_api_key_async", _fake_seed)

    key, configured, reason = bootstrap.ensure_bootstrapped_local_live_api_key(
        api_key=DEFAULT_LOCAL_LIVE_API_KEY,
        api_key_configured=False,
        active_base_url="https://api.algenta.ai",
    )

    assert key == DEFAULT_LOCAL_LIVE_API_KEY
    assert configured is False
    assert reason == "DE_API_KEY is not set and the active live base URL is not local."
    assert called == {"migrations": 0, "seed": 0}


def test_ensure_bootstrapped_local_live_api_key_respects_ignore_hosted_flag(
    monkeypatch,
) -> None:
    called: dict[str, int] = {"migrations": 0, "seed": 0}

    def _fake_migrations() -> None:
        called["migrations"] += 1

    async def _fake_seed(_database_url: str) -> str:
        called["seed"] += 1
        return DEFAULT_LOCAL_LIVE_API_KEY

    monkeypatch.setenv("ALGENTA_TEST_IGNORE_HOSTED_LIVE_CREDENTIALS", "1")
    monkeypatch.setenv("DE_API_KEY", DEFAULT_LOCAL_LIVE_API_KEY)
    monkeypatch.setenv("ALGENTA_API_KEY", DEFAULT_LOCAL_LIVE_API_KEY)
    monkeypatch.setattr(bootstrap, "run_local_live_migrations", _fake_migrations)
    monkeypatch.setattr(bootstrap, "_seed_placeholder_live_api_key_async", _fake_seed)

    key, configured, reason = bootstrap.ensure_bootstrapped_local_live_api_key(
        api_key=DEFAULT_LOCAL_LIVE_API_KEY,
        api_key_configured=True,
        active_base_url="http://127.0.0.1:8000",
    )

    assert key == DEFAULT_LOCAL_LIVE_API_KEY
    assert configured is False
    assert reason is None
    assert called == {"migrations": 0, "seed": 0}
