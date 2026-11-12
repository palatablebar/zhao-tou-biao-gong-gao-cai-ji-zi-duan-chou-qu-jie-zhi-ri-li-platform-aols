"""Pydantic schema：请求体校验 + 少量响应模型。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=6, max_length=64)


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    role: str
    role_label: str
    industry: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: UserOut


class SiteUpdateIn(BaseModel):
    cadence_minutes: int | None = None
    qps_limit: int | None = None
    status: str | None = None
    note: str | None = None


class TemplateCreateIn(BaseModel):
    site_id: int
    name: str = Field(min_length=2, max_length=80)
    change_note: str | None = None
    coverage_score: float | None = None
    field_rules: dict | None = None


class CrawlStartIn(BaseModel):
    site_ids: list[int] | None = None
    as_of: str | None = None


class FieldCorrectIn(BaseModel):
    value: str = Field(min_length=1, max_length=200)
    unit: str | None = None
    note: str | None = None


class FieldNoteIn(BaseModel):
    note: str | None = None


class RecomputeIn(BaseModel):
    as_of: str | None = None


class PageOut(BaseModel):
    total: int
    page: int
    page_size: int
