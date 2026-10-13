"""Request-ID middleware: every response carries X-Request-ID, also stored on audit events.

It also rejects oversized CSV uploads from their Content-Length header, before FastAPI reads
(and spools to disk) the request body. Without this the size check in the route would only run
after the whole upload had been received, even for unauthenticated clients.
"""

import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
UPLOAD_PATH = "/api/v1/imports"
# Room for multipart boundaries and headers on top of the file itself.
MULTIPART_OVERHEAD_BYTES = 64 * 1024


def _error(status_code: int, code: str, message: str, request_id: str) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "details": [], "request_id": request_id}}
    return JSONResponse(status_code=status_code, content=body)


def _check_upload_size(request: Request, request_id: str) -> Response | None:
    if request.method != "POST" or request.url.path.rstrip("/") != UPLOAD_PATH:
        return None
    max_mb = get_settings().max_upload_mb
    length = request.headers.get("content-length")
    if length is None or not length.isdigit():
        return _error(
            411, "LENGTH_REQUIRED", "Uploads must send a Content-Length header", request_id
        )
    if int(length) > max_mb * 1024 * 1024 + MULTIPART_OVERHEAD_BYTES:
        return _error(
            413,
            "FILE_TOO_LARGE",
            f"Uploads are limited to {max_mb} MB. Import larger files with: "
            "python -m app.cli import-csv <path>",
            request_id,
        )
    return None


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex
        request.state.request_id = request_id
        response = _check_upload_size(request, request_id) or await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
