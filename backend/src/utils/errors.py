"""统一业务异常。"""
from __future__ import annotations

from src.constants.error_codes import ERROR_CODES


class AppError(Exception):
    def __init__(self, code: str, status_code: int = 400, detail: str | None = None) -> None:
        self.code = code
        self.status_code = status_code
        self.detail = detail
        self.message = ERROR_CODES.get(code, code)
        super().__init__(self.message)
