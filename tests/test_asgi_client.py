from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from tests._asgi_client import SyncASGIClient


def test_sync_asgi_client_manage_lifespan_enters_fastapi_lifespan_context() -> None:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.started = True
        app.state.stopped = False
        yield
        app.state.stopped = True

    app = FastAPI(lifespan=lifespan)

    @app.get("/state")
    async def state() -> dict[str, bool]:
        return {
            "started": bool(getattr(app.state, "started", False)),
            "stopped": bool(getattr(app.state, "stopped", False)),
        }

    assert getattr(app.state, "started", False) is False
    assert getattr(app.state, "stopped", False) is False

    with SyncASGIClient(app, manage_lifespan=True) as client:
        response = client.get("/state")
        assert response.status_code == 200
        assert response.json() == {"started": True, "stopped": False}

    assert app.state.started is True
    assert app.state.stopped is True
