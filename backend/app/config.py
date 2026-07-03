from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "绿智顾问 API"
    database_url: str = "sqlite:///./green_advisor.db"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:5010"
    dify_api_url: str = ""
    dify_api_key: str = ""
    llm_mode: str = "local"
    upload_dir: str = "uploads"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
