"""ASGI entrypoint that selects the app by ALGENTA_SERVICE_ROLE (P4).

  uvicorn apps.api_server.asgi:app

ALGENTA_SERVICE_ROLE=control_plane → the engine-free control-plane app; otherwise (default
'full') the complete app in main.py. One image, one entrypoint — the env var picks the surface.
The legacy ``apps.api_server.main:app`` target still works for the full app.
"""

from __future__ import annotations

from apps.api_server.app_support import create_app

app = create_app()
