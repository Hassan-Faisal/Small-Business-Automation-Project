from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.api.router import api_router
from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.api.routes.orders import router as orders_router
from app.api.routes.products import router as products_router
from app.api.routes.root import router as root_router
from app.api.routes.webhook import router as webhook_router
from app.core.config import settings
from app.core.lifespan import lifespan
from app.core.logging import configure_logging
from app.core.middleware import RequestLoggingMiddleware

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    logger.info(
        "request_validation_error",
        extra={
            "event": "request_validation_error",
            "method": request.method,
            "route": request.url.path,
            "error_count": len(exc.errors()),
        },
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "type": "validation_error",
                "message": "Request validation failed",
                "details": exc.errors(),
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    logger.info(
        "http_exception",
        extra={
            "event": "http_exception",
            "method": request.method,
            "route": request.url.path,
            "status_code": exc.status_code,
        },
    )
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": "http_exception",
                "message": detail,
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "unhandled_exception",
        extra={
            "event": "unhandled_exception",
            "method": request.method,
            "route": request.url.path,
        },
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "type": "internal_server_error",
                "message": "An unexpected error occurred.",
            }
        },
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.admin_frontend_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
)

app.add_middleware(RequestLoggingMiddleware)

app.include_router(root_router)
app.include_router(health_router)
app.include_router(products_router)
app.include_router(orders_router)
app.include_router(chat_router)
app.include_router(webhook_router)
app.include_router(api_router)
