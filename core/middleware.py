import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from core.logging_config import get_logger

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging all HTTP requests and responses"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        client_host = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path
        query_params = str(request.query_params) if request.query_params else ""

        logger.info(f"Request started: {method} {path} from {client_host}")
        if query_params:
            logger.debug(f"Query params: {query_params}")

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            logger.info(
                f"Request completed: {method} {path} | "
                f"Status: {response.status_code} | "
                f"Duration: {duration:.3f}s | "
                f"Client: {client_host}"
            )

            return response

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Request failed: {method} {path} | "
                f"Duration: {duration:.3f}s | "
                f"Client: {client_host} | "
                f"Error: {str(e)}"
            )
            raise

