from __future__ import annotations

import sys as _sys

from apps.api_server.services import repository_intelligence_core as _core

_sys.modules[__name__] = _core
