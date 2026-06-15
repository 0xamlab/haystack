"""boundary_imports — customer/channel code importing algenta PRODUCT internals.

Customer/channel trees (scripts/, benchmarks/, apps/cli, apps/mcp_server) must
consume only the public boundary (Runtime SDK / AsyncCodnaClient / /v1/repositories/*
/ run_agent_via_sidecar), never the repository_intelligence_* internals or
mojo_library_runner. Wave D fails new channel code; Wave E shrinks the baseline to
zero (all become fatal)."""

from __future__ import annotations

import re
from pathlib import Path

from .._base import Guard, Violation, iter_py

_DIRS = ("scripts", "benchmarks", "apps/cli", "apps/mcp_server")
_RE = re.compile(
    r"repository_intelligence_(?:core|storage|verified_agentic|manifest_reader"
    r"|runtime|pipeline|decision_plan_workflow|graph_workflow|analysis_workflow"
    r"|execution_workflow|planner_generation)\b"
    r"|mojo_library_runner"
)


def _scan(root: Path) -> list[Violation]:
    out: list[Violation] = []
    for rel_dir in _DIRS:
        for p in iter_py(root, rel_dir):
            rel = p.relative_to(root).as_posix()
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                s = line.strip()
                is_import = s.startswith(("import ", "from ")) or "import_module(" in s
                if is_import and _RE.search(s):
                    out.append(Violation("boundary_imports", rel, s))
    return out


GUARD = Guard(
    name="boundary_imports",
    description="customer/channel code importing repository_intelligence_* / mojo_library_runner internals",
    scan=_scan,
    fix_wave="D/E",
)
