"""Renewal Capacity Allocation — the first Algenta Decision Pack.

    "Given upcoming renewals, account health, ARR, and available customer-success
     capacity, where should we allocate intervention time to maximize expected
     retained ARR?"

Public surface:
  * :mod:`contract`          — host-independent request/result schemas (the Decision API shape)
  * :mod:`evidence_contract` — canonical concept semantics + the evidence quality gate
  * :mod:`outcome_model`     — the confounded lever→outcome response model (versioned)
  * :mod:`solver`            — allocation + scenarios + sensitivity + no-feasible-solution
  * :mod:`pack`              — ``run()`` entrypoint + governed ``DESCRIPTOR``
"""

from __future__ import annotations

from .contract import (
    PACK_ID,
    PACK_VERSION,
    RenewalAllocationInput,
    RenewalAllocationResult,
)
from .outcome_model import MODEL_VERSION
from .pack import DESCRIPTOR, run

__all__ = [
    "PACK_ID",
    "PACK_VERSION",
    "MODEL_VERSION",
    "DESCRIPTOR",
    "run",
    "RenewalAllocationInput",
    "RenewalAllocationResult",
]
