"""Decision Packs — governed, domain-specific decision models.

A Decision Pack is the *net-new domain product* the Decision Service is built to
deliver: generic numerical simulation (Monte Carlo, sensitivity, optimization) does
not explain how a business *lever* changes a business *outcome*. A pack supplies the
missing lever→outcome response function, plus the contract, evidence semantics,
validity ranges, and golden tests that make its output defensible.

The first pack is :mod:`renewal_capacity_allocation`. Everything here is deliberately
dependency-light (pydantic + stdlib only) so a pack's contract and golden tests run
without the API app, DB, or engine — the vertical "walking skeleton" starts here.
"""

from __future__ import annotations

__all__ = ["renewal_capacity_allocation"]
