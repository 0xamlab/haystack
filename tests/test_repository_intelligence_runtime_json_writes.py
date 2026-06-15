from __future__ import annotations

import json
from pathlib import Path

from apps.api_server.services import repository_intelligence_runtime as repository_runtime


def test_cache_json_writer_is_compact_and_round_trips(tmp_path: Path) -> None:
    payload = {
        "alpha": 1,
        "nested": {"bravo": True, "charlie": ["x", "y"]},
    }
    target_path = tmp_path / "cache.json"

    repository_runtime._write_cache_json_atomic(target_path, payload)

    written = target_path.read_text(encoding="utf-8")
    assert written == json.dumps(payload, sort_keys=True, separators=(",", ":"))
    assert json.loads(written) == payload


def test_pretty_json_writer_keeps_manifest_style_format(tmp_path: Path) -> None:
    payload = {"alpha": 1, "nested": {"bravo": True}}
    target_path = tmp_path / "manifest.json"

    repository_runtime._write_json_atomic(target_path, payload)

    written = target_path.read_text(encoding="utf-8")
    assert written == json.dumps(payload, indent=2, sort_keys=True)
    assert "\n" in written
