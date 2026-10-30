from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://k9x@127.0.0.1:5433/k9x"

    manifest_provider: str = "mock"  # "mock" | "http"
    manifest_api_url: str = ""
    manifest_api_token: str = ""
    manifest_cache_ttl_s: int = 300
    manifest_timeout_s: float = 5.0

    robot_api_keys: str = "dev-robot-key"

    name_match_threshold: float = 85
    name_uncertain_threshold: float = 70
    weight_tolerance_pct: float = 5
    min_ocr_confidence: float = 0.6

    host: str = "127.0.0.1"
    port: int = 8077

    @property
    def api_keys(self) -> set[str]:
        return {k.strip() for k in self.robot_api_keys.split(",") if k.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
