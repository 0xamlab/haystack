"""canonicalize_email — Gmail dot/plus-tag folding for dedup/rate-limit keys only.

Regression coverage for the free-tier abuse gap: a single Gmail inbox owner minting
unlimited free-tier orgs via +tag/dotted address variants (all deliver to the same real
inbox), because org lookups and the signup daily cap keyed on the literal, un-folded
address string.
"""

from __future__ import annotations

import pytest

from apps.api_server.services.user_service import canonicalize_email


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("name@gmail.com", "name@gmail.com"),
        ("name+work@gmail.com", "name@gmail.com"),
        ("n.a.m.e@gmail.com", "name@gmail.com"),
        ("N.A.ME+x@GMAIL.com", "name@gmail.com"),
        ("  Name@Gmail.com  ", "name@gmail.com"),
        ("name@googlemail.com", "name@googlemail.com"),
        ("n.a.me+y@googlemail.com", "name@googlemail.com"),
        # Dot-folding is Gmail/Googlemail-specific — other providers treat dots as
        # significant, so folding them there would be WRONG (could collide two real,
        # distinct mailboxes). Only +tag stripping applies generically.
        ("name@outlook.com", "name@outlook.com"),
        ("name+tag@outlook.com", "name@outlook.com"),
        ("n.a.me@outlook.com", "n.a.me@outlook.com"),
        ("not-an-email", "not-an-email"),
        ("", ""),
    ],
)
def test_canonicalize_email(raw: str, expected: str) -> None:
    assert canonicalize_email(raw) == expected


def test_alias_variants_share_a_canonical_form() -> None:
    variants = [
        "attacker@gmail.com",
        "attacker+0@gmail.com",
        "attacker+1@gmail.com",
        "attac.ker@gmail.com",
        "at.tac.ker+2@gmail.com",
    ]
    canon = {canonicalize_email(v) for v in variants}
    assert canon == {"attacker@gmail.com"}


def test_distinct_people_on_a_non_gmail_domain_stay_distinct() -> None:
    # A dot is a real, significant character for most providers — this must NOT collapse
    # two different people's addresses into one canonical key.
    assert canonicalize_email("jane.doe@outlook.com") != canonicalize_email("janedoe@outlook.com")
