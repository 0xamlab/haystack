"""Shared imports + helpers for test_llm_provider_service_* sub-modules.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-2/tests/test_llm_provider_service.py during modularization.
"""
# ruff: noqa: F401

from __future__ import annotations

import json

from types import SimpleNamespace

import httpx

import pytest

from apps.api_server.services import egress_guard

from apps.api_server.services import llm_provider_service

from apps.api_server.services.llm_api_service import LLMAPIError


async def allow_egress_for_test(*args, **kwargs):
    """Neutralize the egress policy gate for provider PAYLOAD-mapping tests that POST to a loopback
    base_url (e.g. ollama on http://localhost:11434), which the SSRF/private-destination guard
    correctly denies under the default cloud test policy. These tests assert the request SHAPE, not
    egress policy — that is covered by tests/test_llm_provider_egress.py."""
    return None


__all__ = [
    "annotations",
    "json",
    "SimpleNamespace",
    "httpx",
    "pytest",
    "egress_guard",
    "llm_provider_service",
    "LLMAPIError",
    "allow_egress_for_test",
]
