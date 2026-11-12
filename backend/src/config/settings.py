"""集中配置：全部来自环境变量，默认值与 .env.example 一致。"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_name: str = "bidsift"
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "bidsift"
    db_user: str = "bidsift"
    db_password: str = "bidsift_pw_2026"

    jwt_secret: str = "bidsift-jwt-secret-change-me-2026"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 480

    redis_url: str = "redis://localhost:6379/0"
    seed_demo: bool = True
    rate_limit_per_minute: int = 240
    rate_limit_crawl_per_minute: int = 20

    # ---- 算法口径（算法 1 / 算法 2 共用，改这里即改口径）----
    low_confidence_threshold: float = 0.55
    pressure_horizon_hours: float = 72.0
    workday_start_hour: int = 9
    workday_end_hour: int = 18
    must_act_pressure: float = 0.45
    watch_pressure: float = 0.15

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
