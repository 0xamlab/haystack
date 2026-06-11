from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "repository-intelligence-bot.yml"


def _load_workflow() -> dict[str, object]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_repository_bot_workflow_has_split_trigger_lanes() -> None:
    workflow = _load_workflow()

    assert "pull_request" in workflow["on"]
    assert "workflow_dispatch" in workflow["on"]
    assert "issue_comment" in workflow["on"]
    assert "pull_request_target" not in workflow["on"]


def test_pull_request_lane_is_review_only_and_read_scoped() -> None:
    workflow = _load_workflow()
    job = workflow["jobs"]["review_only"]

    assert job["permissions"]["contents"] == "read"
    assert job["permissions"]["pull-requests"] == "read"
    assert "write" not in "\n".join(
        str(step.get("run", "")) for step in job["steps"] if isinstance(step, dict)
    )
    checkout = job["steps"][0]["with"]
    assert checkout["ref"] == "${{ github.event.pull_request.base.sha }}"
    assert checkout["persist-credentials"] is False


def test_issue_comment_lane_requires_algenta_mention_and_avoids_untrusted_head_checkout() -> None:
    workflow = _load_workflow()
    job = workflow["jobs"]["issue_comment_fix"]

    assert "contains(github.event.comment.body, '@algenta')" in job["if"]
    assert job["permissions"]["contents"] == "write"
    checkout = job["steps"][0]["with"]
    assert checkout["ref"] == "${{ github.event.repository.default_branch }}"
    assert checkout["persist-credentials"] is False
    rendered_steps = "\n".join(
        str(step.get("run", "")) for step in job["steps"] if isinstance(step, dict)
    )
    assert "OWNER|MEMBER|COLLABORATOR" in rendered_steps
    assert "github.event.pull_request.head.sha" not in rendered_steps
