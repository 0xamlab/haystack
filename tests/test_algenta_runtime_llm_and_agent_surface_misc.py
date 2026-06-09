"""Tests for test_algenta_runtime_llm_and_agent_surface: misc.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_b79cfb1f-957-3/tests/test_algenta_runtime_llm_and_agent_surface.py during modularization.
"""
from __future__ import annotations

from tests._test_algenta_runtime_llm_and_agent_surface_helpers import *  # noqa: F401,F403


def test_algenta_root_exports_plan_aligned_runtime_models() -> None:
    preserved = {
        module_name: module
        for module_name, module in list(sys.modules.items())
        if module_name == "algenta" or module_name.startswith("algenta.")
    }
    for module_name in list(sys.modules):
        if module_name == "algenta" or module_name.startswith("algenta."):
            sys.modules.pop(module_name, None)

    try:
        root = importlib.import_module("algenta")

        assert "algenta.runtime_model_llm" not in sys.modules
        assert "algenta.runtime_model_agent_runs" not in sys.modules
        assert "algenta.runtime_model_decision_plan" not in sys.modules

        assert root.DecisionPlanOutput.__name__ == "DecisionPlanOutput"
        assert root.LLMModelListOutput.__name__ == "LLMModelListOutput"
        assert root.AgentRunOutput.__name__ == "AgentRunOutput"
        assert root.AgentRunEventsOutput.__name__ == "AgentRunEventsOutput"

        assert "algenta.runtime_model_llm" in sys.modules
        assert "algenta.runtime_model_agent_runs" in sys.modules
        assert "algenta.runtime_model_decision_plan" in sys.modules
    finally:
        for module_name in list(sys.modules):
            if module_name == "algenta" or module_name.startswith("algenta."):
                sys.modules.pop(module_name, None)
        sys.modules.update(preserved)


