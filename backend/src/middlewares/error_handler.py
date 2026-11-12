"""全局错误处理：统一 {code,message,detail} 响应。"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.utils.errors import AppError

logger = logging.getLogger("bidsift.errors")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message, "detail": exc.detail},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        code = "NOT_FOUND" if exc.status_code == 404 else "INTERNAL"
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": code, "message": str(exc.detail), "detail": None},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"code": "VALIDATION", "message": "请求参数不合法", "detail": exc.errors()[:4]},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.exception("unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"code": "INTERNAL", "message": "服务内部错误", "detail": None},
        )
