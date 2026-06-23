from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:password@db:5432/interviewiq"
    SECRET_KEY: str = "interviewiq-secret-key-change-in-production-2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    UPLOAD_DIR: str = "/tmp/uploads"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
