"""org_scope — a query on an org-scoped model that forgets the tenant boundary.

WHAT THIS CATCHES. Every model carrying ``org_id`` holds one tenant's data. A ``select(Model)`` in a
router or service that does not constrain it — via ``workspace_scope_clauses(Model, auth)`` or an
explicit ``Model.org_id ==`` — reads across ALL tenants. Nothing about such code looks wrong locally:
it returns rows, tests pass on a single-tenant fixture, and the leak only appears once a second
customer exists. That is the worst shape a defect can have, so it is worth a mechanical check rather
than reviewer attention.

The engine already got this right in the audited paths (a cross-tenant audit found the DB
query-scoping solid), which is exactly why a guard matters now: the risk is not the existing code,
it is the next hundred queries written against a growing model set.

HOW IT DECIDES. AST, not line-grep, because the scoping clause is usually on a different line from
the ``select``:

    base_q = (
        select(AuditEvent)
        .where(*workspace_scope_clauses(AuditEvent, auth))
        .order_by(desc(AuditEvent.created_at))
    )

A line-based check sees ``select(AuditEvent)`` alone and screams. So the guard finds the
``select(Model)`` call, walks out to the enclosing STATEMENT, and inspects that statement's whole
source span for a scoping construct. Multi-line chains, parenthesised builders and
``.where()``-after-assignment on the same statement all resolve correctly.

WHAT COUNTS AS SCOPED (deliberately generous — a false positive that cannot be silenced honestly
just teaches people to baseline things):
  * ``workspace_scope_clauses(...)``   the canonical helper
  * ``<anything>.org_id``              an explicit predicate, including ``Model.org_id == auth[...]``
  * ``org_id=``                        keyword form used by some helpers
  * ``_scope``/``scoped``              a named scoping helper in the same statement

WHICH MODELS. Derived, never listed: any class in apps/api_server/models/ that declares ``org_id``
or inherits the OrgWorkspaceScopedMixin. Hardcoding the model set would silently stop protecting
whichever model is added next, which is the only one that actually needs protecting.

Baselined: existing violations are recorded debt and stay non-fatal; a NEW one fails CI.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from .._base import Guard, Violation, iter_py

_SCAN_DIRS = ("apps/api_server/routers", "apps/api_server/services")
_MODELS_DIR = "apps/api_server/models"

# A statement containing any of these is treated as tenant-scoped.
_SCOPED_RE = re.compile(
    r"workspace_scope_clauses|\.org_id\b|\borg_id\s*=|_scope\b|scoped\b",
)


def _org_scoped_models(root: Path) -> set[str]:
    """Class names in models/ that carry org_id, directly or via the mixin."""
    names: set[str] = set()
    mixins: set[str] = set()
    trees: list[tuple[str, ast.AST]] = []

    for p in iter_py(root, _MODELS_DIR):
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        trees.append((p.name, tree))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            declares_org_id = any(
                isinstance(b, ast.AnnAssign)
                and isinstance(b.target, ast.Name)
                and b.target.id == "org_id"
                for b in node.body
            )
            if declares_org_id:
                names.add(node.name)
                # A mixin that declares org_id confers it on everything inheriting it.
                if "Mixin" in node.name:
                    mixins.add(node.name)

    # Second pass: classes inheriting an org_id-bearing mixin.
    for _name, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(
                isinstance(b, ast.Name) and b.id in mixins for b in node.bases
            ):
                names.add(node.name)

    # A mixin is not itself a queryable entity.
    return {n for n in names if "Mixin" not in n}


def _selected_model(call: ast.Call) -> str | None:
    """Model name from ``select(Model)`` / ``select(Model.col)``, else None."""
    func = call.func
    if not (isinstance(func, ast.Name) and func.id == "select"):
        return None
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Name):
        return first.id
    if isinstance(first, ast.Attribute) and isinstance(first.value, ast.Name):
        return first.value.id  # select(Model.column)
    return None


def _scan(root: Path) -> list[Violation]:
    models = _org_scoped_models(root)
    if not models:  # the derivation broke; say so rather than reporting a clean scan
        return [
            Violation(
                "org_scope",
                _MODELS_DIR,
                "found no org-scoped models — the model derivation is broken, so this guard "
                "would silently pass everything",
            )
        ]

    out: list[Violation] = []
    for rel_dir in _SCAN_DIRS:
        for p in iter_py(root, rel_dir):
            src = p.read_text(encoding="utf-8", errors="ignore")
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue
            lines = src.splitlines()
            rel = p.relative_to(root).as_posix()

            # Each select() is attributed to its NEAREST enclosing statement, so the scoping clause
            # is looked for across the whole chain rather than one line -- and a select nested in a
            # function is reported once, not again for every ancestor block.
            #
            # Walking `parent.body` instead looks simpler and is wrong twice: `Lambda.body` and
            # `IfExp.body` are expressions rather than lists (that raised TypeError immediately),
            # and every enclosing block would re-report the same select.
            parent_of: dict[ast.AST, ast.AST] = {}
            for node in ast.walk(tree):
                for child in ast.iter_child_nodes(node):
                    parent_of[child] = node

            seen: set[tuple[int, str]] = set()
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                model = _selected_model(node)
                if model not in models:
                    continue
                stmt: ast.AST | None = node
                while stmt is not None and not isinstance(stmt, ast.stmt):
                    stmt = parent_of.get(stmt)
                if stmt is None:
                    continue
                start = (stmt.lineno or 1) - 1
                end = stmt.end_lineno or stmt.lineno or 1
                span = "\n".join(lines[start:end])
                if _SCOPED_RE.search(span):
                    continue
                if (start, model) in seen:
                    continue
                seen.add((start, model))
                first_line = (lines[start] if start < len(lines) else "").strip()
                out.append(
                    Violation(
                        "org_scope",
                        rel,
                        f"select({model}) without a tenant scope :: {first_line[:120]}",
                    )
                )
    return out


GUARD = Guard(
    name="org_scope",
    description=(
        "query on an org-scoped model with no workspace_scope_clauses / org_id predicate "
        "(reads across tenants)"
    ),
    scan=_scan,
    fix_wave="B2",
    baselined=True,
)
