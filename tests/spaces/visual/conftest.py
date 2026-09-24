"""tests/spaces/visual — the goldens helper imports by bare name, like the tools do."""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
collect_ignore = ["_goldens.py"]  # a helper, not a test module (its functions are also _-prefixed)
