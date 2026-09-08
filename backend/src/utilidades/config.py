"""Configuración de la aplicación usando Pydantic Settings."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    app_name: str = "TransMilenio IA"
    app_version: str = "0.1.0"
    debug: bool = True

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Datos
    datos_dir: str = "datos"
    gtfs_dir: str = "gtfs_transmilenio"

    # OSMnx
    osm_cache_dir: str = "cache_osm"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # json o text

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()