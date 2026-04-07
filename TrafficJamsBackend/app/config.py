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

    # DBSCAN defaults
    dbscan_eps_meters: float = 100.0
    dbscan_min_samples: int = 3

    # Road snapping
    road_snap_max_distance: float = 200.0  # meters

    # Data source: "postgres" or "csv"
    data_source: str = "csv"

    # CSV file paths (used when data_source="csv")
    accidents_csv_path: str = "../../police_data.csv"
    road_segments_csv_path: str = "../../road_segments.csv"

    # App
    app_title: str = "Accidents API"
    app_version: str = "1.0.0"
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()

