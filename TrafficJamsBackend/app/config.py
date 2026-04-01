from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/accidents_db"
    database_url_sync: str = "postgresql+psycopg2://postgres:password@localhost:5432/accidents_db"

    # DBSCAN
    dbscan_eps_meters: float = 100.0
    dbscan_min_samples: int = 3

    # Road snapping
    road_snap_max_distance: float = 200.0  # meters

    # App
    app_title: str = "Accidents API"
    app_version: str = "1.0.0"
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
