"""Tests for repository_intelligence_real_repo_probe: store_probe.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_store_probe_prepass_cache_retries_after_missing_tmp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "runtime" / "probe_prepass" / "cache.json"
    attempts = 0
    original_replace = Path.replace

    def _flaky_replace(self: Path, target: Path) -> Path:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            self.unlink(missing_ok=True)
            raise FileNotFoundError(self)
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", _flaky_replace)

    _store_probe_prepass_cache(cache_path, {"schema_version": "repository-probe-prepass-v1"})

    assert attempts == 2
    assert cache_path.exists()


