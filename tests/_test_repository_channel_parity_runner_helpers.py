"""Shared imports + helpers for test_repository_channel_parity_runner_* sub-modules.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_b79cfb1f-957-2/tests/test_repository_channel_parity_runner.py during modularization.
"""
# ruff: noqa: F401

from __future__ import annotations

import json

from pathlib import Path

from types import SimpleNamespace

from tests import repository_channel_parity_runner as runner

def _expected_log_artifact(*, spec: runner.ChannelSpec, logs_dir: Path) -> str:
    return runner._channel_log_artifact_path(spec, logs_dir=logs_dir)



__all__ = [
    "annotations",
    "json",
    "Path",
    "SimpleNamespace",
    "runner",
    "_expected_log_artifact",
]
