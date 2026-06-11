"""github_workflows — a workflow that can run untrusted PR code with a write token.

The classic supply-chain footgun: ``pull_request_target`` (write-capable token)
combined with checking out the untrusted PR HEAD. NOT baselined — any hit fails
immediately (T11a). The safe pattern is contents:read on pull_request, and for
write-capable issue_comment flows: verify the actor, check out the trusted base or
an isolated bot branch, and apply only gate-passed patch artifacts."""

from __future__ import annotations

import re
from pathlib import Path

from .._base import Guard, Violation

_WF_DIR = ".github/workflows"
_UNTRUSTED_HEAD = re.compile(r"ref:\s*\$\{\{\s*github\.event\.pull_request\.head")
_WRITES = re.compile(r"contents:\s*write")


def _scan(root: Path) -> list[Violation]:
    out: list[Violation] = []
    base = root / _WF_DIR
    if not base.exists():
        return out
    for p in sorted(base.glob("*.yml")) + sorted(base.glob("*.yaml")):
        text = p.read_text(encoding="utf-8", errors="ignore")
        if "pull_request_target" not in text:
            continue
        checks_untrusted_head = "actions/checkout" in text and bool(_UNTRUSTED_HEAD.search(text))
        # write-capable if it explicitly grants contents:write OR sets no permissions
        # block at all (the default GITHUB_TOKEN under pull_request_target is write).
        write_capable = bool(_WRITES.search(text)) or "permissions:" not in text
        if checks_untrusted_head and write_capable:
            out.append(
                Violation(
                    "github_workflows",
                    p.relative_to(root).as_posix(),
                    "pull_request_target checks out untrusted PR head with a write-capable token",
                )
            )
    return out


GUARD = Guard(
    name="github_workflows",
    description="workflow runs untrusted PR head code with a write-capable token",
    scan=_scan,
    fix_wave="A0",
    baselined=False,  # any hit is always fatal
)
