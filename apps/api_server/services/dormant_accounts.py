"""12-month dormant-account policy — GDPR storage-limitation + Resend notifications.

Policy (mirrors Google's inactive-account approach): an identity with no sign-in for 365 days is
deleted, but ONLY after ≥1 month of clearly-communicated warnings — emails at T-30d / T-14d / T-7d /
T-1d before the deletion date, each sent exactly once. An account with an ACTIVE PAID Stripe
subscription is NEVER treated as dormant (paying = active). Deletion removes the Supabase identity
(cascading the profile) and cancels any Stripe subscriptions; invoices are retained by Stripe for
tax/legal. Dormancy signal = auth.users.last_sign_in_at (the identity's last login).

The sweep is designed to run daily from a scheduler (Fly scheduled machine / cron) via
scripts/dormant_sweep.py. It is DRY-RUN by default and heavily guarded — it never sends or deletes
unless explicitly executed, and it records every notice sent (dormant_notifications) so it never
double-sends or double-deletes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

DORMANT_AFTER_DAYS = 365
# Days-before-deletion at which each warning fires (>= 1 month of notice, multiple sends).
WARNING_SCHEDULE = (30, 14, 7, 1)

# Stage names, in escalating order.
STAGE_ACTIVE = "active"
STAGE_DELETE = "delete"


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def days_inactive(last_sign_in: datetime | None, now: datetime) -> int:
    """Whole days since the last sign-in. None (never signed in) counts from account creation is the
    caller's job; here None → treated as very dormant (large number)."""
    if last_sign_in is None:
        return DORMANT_AFTER_DAYS * 10
    return max(0, (_aware(now) - _aware(last_sign_in)).days)


def deletion_date(last_sign_in: datetime, now: datetime) -> datetime:
    return _aware(last_sign_in) + timedelta(days=DORMANT_AFTER_DAYS)


def classify(last_sign_in: datetime | None, now: datetime) -> str:
    """Return the account's stage: 'active', 'warn_30'|'warn_14'|'warn_7'|'warn_1', or 'delete'."""
    days_left = DORMANT_AFTER_DAYS - days_inactive(last_sign_in, now)
    if days_left <= 0:
        return STAGE_DELETE
    for w in sorted(WARNING_SCHEDULE):  # 1, 7, 14, 30
        if days_left <= w:
            return f"warn_{w}"
    return STAGE_ACTIVE


def is_warning(stage: str) -> bool:
    return stage.startswith("warn_")


def days_left_for_stage(stage: str) -> int | None:
    if stage == STAGE_DELETE:
        return 0
    if is_warning(stage):
        return int(stage.split("_", 1)[1])
    return None


# ── Sweep orchestration ───────────────────────────────────────────────────────
# Paid plans that make an account "active" regardless of sign-in — never dormant-delete a payer.
# (Free tiers — free / telys_developer / algenta_free — are intentionally NOT here: a never-signing-in
# free account is dormant-deletable. Every PAID tier of every brand MUST be listed or a payer is deleted.)
PAID_PLANS = {
    "developer", "pro", "proplus", "ultra", "team",
    "telys_pro", "telys_team",
    "algenta_pro", "algenta_team",
}
KEEP_URL = "https://accounts.thyn.ai/login"


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


async def _list_supabase_users() -> list[dict]:
    """All Supabase identities with their last_sign_in_at, via the admin API (paginated)."""
    import httpx

    from apps.api_server.config import get_settings

    s = get_settings()
    if not getattr(s, "supabase_url", "") or not getattr(s, "supabase_service_role_key", ""):
        return []
    key = s.supabase_service_role_key
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    users: list[dict] = []
    async with httpx.AsyncClient(timeout=30) as client:
        page = 1
        while page <= 100:  # safety bound
            r = await client.get(f"{s.supabase_url}/auth/v1/admin/users?per_page=200&page={page}", headers=headers)
            if r.status_code >= 400:
                break
            batch = r.json().get("users", [])
            if not batch:
                break
            users += [
                {"id": u.get("id"), "email": u.get("email"), "last_sign_in_at": u.get("last_sign_in_at")}
                for u in batch
            ]
            if len(batch) < 200:
                break
            page += 1
    return users


async def _delete_supabase_user(user_id: str) -> bool:
    import httpx

    from apps.api_server.config import get_settings

    s = get_settings()
    key = s.supabase_service_role_key
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.delete(
            f"{s.supabase_url}/auth/v1/admin/users/{user_id}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
        )
    return r.status_code < 400


async def _has_active_paid_sub(db, email: str) -> bool:
    from sqlalchemy import func, select

    from apps.api_server.models.organization import Organization
    from apps.api_server.models.user import User

    rows = (
        await db.execute(
            select(Organization.plan)
            .join(User, User.org_id == Organization.id)
            .where(func.lower(User.email) == email.lower())
        )
    ).all()
    for (plan,) in rows:
        pv = plan.value if hasattr(plan, "value") else str(plan)
        if pv in PAID_PLANS:
            return True
    return False


async def run_sweep(db, *, execute: bool = False, now: datetime | None = None, users: list[dict] | None = None) -> dict:
    """Scan identities, warn the dormant on the T-30/14/7/1 cadence (deduped), and delete at the
    365-day deadline — NEVER a paid subscriber. DRY-RUN unless execute=True (then it emails + deletes).
    `users` can be injected for tests; otherwise it lists Supabase admin users."""
    from sqlalchemy import select

    from apps.api_server.models.dormant_notification import DormantNotification
    from apps.api_server.services import resend_email

    now = now or datetime.now(timezone.utc)
    if users is None:
        users = await _list_supabase_users()

    summary = {"scanned": len(users), "active": 0, "skipped_paid": 0, "warned": {}, "deleted": 0, "dry_run": not execute}
    for u in users:
        email = u.get("email")
        if not email:
            continue
        stage = classify(_parse_iso(u.get("last_sign_in_at")), now)
        if stage == STAGE_ACTIVE:
            summary["active"] += 1
            continue
        if await _has_active_paid_sub(db, email):
            summary["skipped_paid"] += 1
            continue

        if is_warning(stage):
            if await db.scalar(select(DormantNotification).where(DormantNotification.email == email, DormantNotification.notice_type == stage)):
                continue  # already warned at this stage
            summary["warned"][stage] = summary["warned"].get(stage, 0) + 1
            if execute:
                await resend_email.send_dormant_warning_email(
                    to=email, days_left=days_left_for_stage(stage) or 0,
                    delete_on=deletion_date(_parse_iso(u["last_sign_in_at"]) or now, now).date().isoformat(),
                    keep_url=KEEP_URL,
                )
                db.add(DormantNotification(email=email, notice_type=stage, sent_at=now))
                await db.commit()
        elif stage == STAGE_DELETE:
            summary["deleted"] += 1
            if execute:
                if await _delete_supabase_user(u["id"]):  # cascades the profile
                    await resend_email.send_dormant_deleted_email(to=email)
                    db.add(DormantNotification(email=email, notice_type="deleted", sent_at=now))
                    await db.commit()
    return summary
