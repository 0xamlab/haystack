"""B2: the org_scope guard catches a query that forgets the tenant boundary.

WHY A GUARD AND NOT REVIEW. A `select(Model)` on an org-scoped model with no
`workspace_scope_clauses` / `org_id` predicate reads across ALL tenants, and nothing about it looks
wrong locally: it returns rows, and single-tenant test fixtures pass. The defect only surfaces once
a second customer exists. That shape — correct-looking, silently wrong, late-discovered — is what
mechanical checks are for.

THE TESTS RUN THE GUARD OVER SYNTHETIC TREES rather than the real repo, so they assert BEHAVIOUR
(what it flags and what it must not) instead of a count that changes with every merge. A test
pinned to "45 violations" would fail on unrelated work and get bumped without thought, which is
how a guard stops being read.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.reliability_guards.guards.org_scope import GUARD, _org_scoped_models

MODEL_SRC = '''
from sqlalchemy.orm import Mapped, mapped_column


class OrgWorkspaceScopedMixin:
    org_id: Mapped[str] = mapped_column()


class AuditEvent(OrgWorkspaceScopedMixin, Base):
    __tablename__ = "audit_events"


class Widget(Base):
    org_id: Mapped[str] = mapped_column()


class GlobalThing(Base):
    name: Mapped[str] = mapped_column()
'''


def _tree(tmp_path: Path, router_src: str) -> Path:
    (tmp_path / "apps/api_server/models").mkdir(parents=True)
    (tmp_path / "apps/api_server/routers").mkdir(parents=True)
    (tmp_path / "apps/api_server/services").mkdir(parents=True)
    (tmp_path / "apps/api_server/models/m.py").write_text(MODEL_SRC)
    (tmp_path / "apps/api_server/routers/r.py").write_text(router_src)
    return tmp_path


# ── which models count ──────────────────────────────────────────────────────────────────────────


def test_org_scoped_models_are_derived_including_via_the_mixin(tmp_path: Path) -> None:
    """Derived, never listed: a hardcoded set stops protecting whichever model is added next."""
    root = _tree(tmp_path, "x = 1\n")
    models = _org_scoped_models(root)
    assert "Widget" in models, "a model declaring org_id directly must count"
    assert "AuditEvent" in models, "a model inheriting the org_id mixin must count"
    assert "GlobalThing" not in models, "a model without org_id is not tenant-scoped"
    assert not any("Mixin" in m for m in models), "the mixin itself is not a queryable entity"


# ── what it flags ───────────────────────────────────────────────────────────────────────────────


def test_an_unscoped_select_is_flagged(tmp_path: Path) -> None:
    root = _tree(tmp_path, "rows = await db.execute(select(Widget))\n")
    v = GUARD.scan(root)
    assert len(v) == 1, v
    assert "select(Widget)" in v[0].snippet


def test_a_select_on_a_non_org_model_is_not_flagged(tmp_path: Path) -> None:
    """The guard must be about tenancy, not about every query in the codebase."""
    root = _tree(tmp_path, "rows = await db.execute(select(GlobalThing))\n")
    assert GUARD.scan(root) == []


@pytest.mark.parametrize(
    "scoped",
    [
        pytest.param("select(Widget).where(*workspace_scope_clauses(Widget, auth))", id="helper"),
        pytest.param("select(Widget).where(Widget.org_id == auth['org_id'])", id="explicit-predicate"),
        pytest.param("select(Widget).filter_by(org_id=auth['org_id'])", id="keyword-form"),
    ],
)
def test_a_properly_scoped_select_is_not_flagged(tmp_path: Path, scoped: str) -> None:
    root = _tree(tmp_path, f"rows = await db.execute({scoped})\n")
    assert GUARD.scan(root) == [], f"false positive on a scoped query: {scoped}"


def test_a_multiline_chain_with_the_scope_on_a_later_line_is_not_flagged(tmp_path: Path) -> None:
    """The reason this guard is AST-based. A line-grep sees `select(AuditEvent)` alone and screams.

    This exact shape is what the real code looks like, so getting it wrong would have made the
    guard unusable on day one.
    """
    src = (
        "base_q = (\n"
        "    select(AuditEvent)\n"
        "    .where(*workspace_scope_clauses(AuditEvent, auth))\n"
        "    .order_by(desc(AuditEvent.created_at))\n"
        ")\n"
    )
    root = _tree(tmp_path, src)
    assert GUARD.scan(root) == [], "multi-line scoping was not recognised"


def test_a_multiline_chain_with_no_scope_anywhere_is_flagged(tmp_path: Path) -> None:
    """The counterpart: multi-line must not become a way to hide from the guard."""
    src = (
        "base_q = (\n"
        "    select(AuditEvent)\n"
        "    .order_by(desc(AuditEvent.created_at))\n"
        "    .limit(100)\n"
        ")\n"
    )
    root = _tree(tmp_path, src)
    v = GUARD.scan(root)
    assert len(v) == 1, f"an unscoped multi-line query slipped through: {v}"


def test_a_select_inside_a_function_is_reported_once(tmp_path: Path) -> None:
    """Attributed to its nearest enclosing statement, not re-reported per ancestor block."""
    src = (
        "async def handler(db):\n"
        "    if True:\n"
        "        rows = await db.execute(select(Widget))\n"
        "    return rows\n"
    )
    root = _tree(tmp_path, src)
    assert len(GUARD.scan(root)) == 1


def test_a_lambda_does_not_crash_the_scan(tmp_path: Path) -> None:
    """Regression: walking `parent.body` blindly raised TypeError -- Lambda.body is an expression."""
    src = "f = lambda: 1\nrows = await db.execute(select(Widget))\n"
    root = _tree(tmp_path, src)
    assert len(GUARD.scan(root)) == 1


def test_services_are_scanned_too_not_only_routers(tmp_path: Path) -> None:
    root = _tree(tmp_path, "x = 1\n")
    (root / "apps/api_server/services/s.py").write_text(
        "rows = await db.execute(select(Widget))\n"
    )
    v = GUARD.scan(root)
    assert any("services/s.py" in x.path for x in v), "service-layer queries must be scanned"


def test_the_guard_fails_loudly_if_model_derivation_breaks(tmp_path: Path) -> None:
    """A guard that silently finds nothing to protect is worse than no guard.

    If models/ moves or the parse breaks, the scan would otherwise return [] and read as a clean
    pass forever. It reports a violation against itself instead.
    """
    (tmp_path / "apps/api_server/routers").mkdir(parents=True)
    (tmp_path / "apps/api_server/routers/r.py").write_text("rows = select(Widget)\n")
    v = GUARD.scan(tmp_path)  # no models/ directory at all
    assert len(v) == 1
    assert "derivation is broken" in v[0].snippet


# ── the ratchet ─────────────────────────────────────────────────────────────────────────────────


def test_the_guard_is_baselined_so_known_debt_is_non_fatal() -> None:
    """Existing unscoped queries are recorded debt; the ratchet only has to stop NEW ones."""
    assert GUARD.baselined is True
    assert GUARD.fix_wave == "B2"


def test_the_committed_baseline_covers_the_current_tree() -> None:
    """The repo must be green: every current violation is either scoped or recorded.

    This is the assertion that makes the guard load-bearing -- if someone adds an unscoped query,
    it is NOT in baseline.json and the build fails.
    """
    from scripts.reliability_guards import run_guards

    results = run_guards(guards=["org_scope"])
    new = results["org_scope"]["new"]
    assert new == [], f"unbaselined org_scope violations: {new[:5]}"
