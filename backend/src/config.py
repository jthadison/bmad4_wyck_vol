"""
Application configuration module using Pydantic Settings.

This module provides centralized configuration management for the BMAD Wyckoff system,
including database connection settings, API keys, and environment-specific values.
"""

from typing import Literal

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings with validation.

    Settings are loaded from environment variables with fallback to .env file.
    All database connection pooling and configuration is centralized here.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Application environment",
    )
    debug: bool = Field(
        default=True,
        description="Debug mode flag",
    )

    # Database Configuration
    database_url: PostgresDsn = Field(
        default="postgresql+psycopg://wyckoff_user:changeme@localhost:5432/wyckoff_db",
        description="PostgreSQL connection string with async driver",
    )

    # Database Connection Pool Settings (AC: 9 - pool_size 5-20, we use 10)
    db_pool_size: int = Field(
        default=10,
        ge=5,
        le=20,
        description="SQLAlchemy connection pool size (base connections)",
    )
    db_max_overflow: int = Field(
        default=10,
        ge=0,
        le=20,
        description="Maximum overflow connections beyond pool_size",
    )
    db_pool_pre_ping: bool = Field(
        default=True,
        description="Enable connection health checks before using from pool",
    )
    db_pool_recycle: int = Field(
        default=3600,
        ge=300,
        description="Recycle connections after this many seconds (prevent stale connections)",
    )
    db_echo: bool = Field(
        default=False,
        description="Echo SQL statements to logs (useful for debugging)",
    )

    # Redis Configuration
    redis_host: str = Field(
        default="localhost",
        description="Redis server hostname",
    )
    redis_port: int = Field(
        default=6379,
        ge=1,
        le=65535,
        description="Redis server port",
    )

    # External API Configuration
    polygon_api_key: str = Field(
        default="",
        description="Polygon.io API key for market data",
    )

    # Data Ingestion Settings
    default_provider: str = Field(
        default="polygon",
        description="Default market data provider (polygon, yahoo)",
    )
    rate_limit_delay: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Delay between API requests in seconds",
    )
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of retry attempts for failed requests",
    )
    batch_size: int = Field(
        default=500,
        ge=100,
        le=50000,
        description="Number of bars to fetch per batch",
    )

    # Application Settings
    backend_port: int = Field(
        default=8000,
        ge=1024,
        le=65535,
        description="Backend API server port",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """
        Validate that database URL uses async-compatible driver.

        Ensures postgresql+psycopg:// or postgresql+asyncpg:// dialect.
        """
        if isinstance(v, str):
            if not ("+psycopg://" in v or "+asyncpg://" in v):
                raise ValueError(
                    "DATABASE_URL must use async driver (postgresql+psycopg:// or postgresql+asyncpg://)"
                )
        return v


# Global settings instance
settings = Settings()
