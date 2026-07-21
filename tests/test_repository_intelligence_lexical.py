"""Tests for the Telys code-lexical triage lane (repository_intelligence_lexical)."""
from __future__ import annotations

import importlib.util

import pytest

from apps.api_server.services import repository_intelligence_lexical as lex


def _manifest() -> dict:
    return {
        "files": [
            {"file_path": "aiogram/fsm/context.py",
             "symbols": [{"symbol_name": "FSMContext"}, {"symbol_name": "get_data"}]},
            {"file_path": "aiogram/fsm/scene.py", "symbols": [{"symbol_name": "SceneWizard"}]},
            {"file_path": "README.md", "symbols": []},
        ]
    }


def test_flag_defaults_off_and_toggles(monkeypatch):
    monkeypatch.delenv("ALGENTA_REPOSITORIES_LEXICAL_RANKING", raising=False)
    assert lex.lexical_ranking_enabled() is False
    for on in ("1", "true", "YES", "on"):
        monkeypatch.setenv("ALGENTA_REPOSITORIES_LEXICAL_RANKING", on)
        assert lex.lexical_ranking_enabled() is True


def test_rank_degrades_on_empty_query_or_corpus():
    assert lex.lexical_rank(_manifest(), [], 5) == []
    assert lex.lexical_rank({"files": []}, ["x"], 5) == []


@pytest.mark.skipif(importlib.util.find_spec("memengine") is None, reason="memengine not installed")
def test_rank_localizes_to_the_symbol_bearing_file():
    ranked = lex.lexical_rank(_manifest(), ["FSMContext", "get_data"], top_k=3)
    assert ranked, "expected a ranking when memengine is available"
    assert ranked[0] == "aiogram/fsm/context.py"  # BM25 over path+symbols picks the right file
