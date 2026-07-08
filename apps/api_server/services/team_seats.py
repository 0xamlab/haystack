"""Seat limits per plan for team membership.

A "seat" = one active User in the org (owner/admin/member/viewer), plus any
pending invites (a pending invite reserves a seat so you can't over-invite).

Solo plans (free/pro/proplus/ultra/developer + telys_developer/pro) are 1 seat:
the account owner only — they cannot add teammates. `team` (and telys_team) is a
multi-seat plan; its cap is the number of seats purchased on the Stripe
subscription (per-seat billing), defaulting to DEFAULT_TEAM_SEATS until a quantity
is synced. `enterprise` is unlimited.
"""

DEFAULT_TEAM_SEATS = 5
_UNLIMITED = 0  # sentinel: 0 means "no cap"

_MULTI_SEAT_PLANS = {"team", "telys_team", "algenta_team"}
_UNLIMITED_PLANS = {"enterprise"}


def seat_limit(plan: str, purchased_seats: int | None = None) -> int:
    """Max active members + pending invites allowed on this plan. 0 = unlimited."""
    p = (plan or "free").lower()
    if p in _UNLIMITED_PLANS:
        return _UNLIMITED
    if p in _MULTI_SEAT_PLANS:
        # per-seat billing: the cap is what they bought (Stripe subscription quantity);
        # fall back to the default bundle until a quantity is synced.
        if purchased_seats and purchased_seats > 0:
            return purchased_seats
        return DEFAULT_TEAM_SEATS
    return 1  # solo plans


def can_add_member(plan: str, current_seats_used: int, purchased_seats: int | None = None) -> bool:
    """True if one more member/invite fits under the plan's seat cap."""
    limit = seat_limit(plan, purchased_seats)
    if limit == _UNLIMITED:
        return True
    return current_seats_used < limit


def is_multi_seat(plan: str) -> bool:
    p = (plan or "free").lower()
    return p in _MULTI_SEAT_PLANS or p in _UNLIMITED_PLANS
