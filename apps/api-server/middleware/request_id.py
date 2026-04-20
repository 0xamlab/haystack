"""Request ID middleware — injects X-Request-Id on every request and response."""
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


REQUEST_ID_HEADER = "X-Request-Id"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Injects a unique request ID into every request.

    - If the client sends X-Request-Id, it is preserved.
    - Otherwise a new UUID v4 is generated.
    - The ID is attached to request.state.request_id for use in logs.
    - The ID is echoed back in the response X-Request-Id header.
    """

    async def dispatch(self, request: Request, call_next: object) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or f"req_{uuid.uuid4().hex}"
        request.state.request_id = request_id

        response: Response = await call_next(request)  # type: ignore[operator]
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
