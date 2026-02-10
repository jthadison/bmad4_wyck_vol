"""
Application configuration module using Pydantic Settings.

This module provides centralized configuration management for the BMAD Wyckoff system,
including database connection settings, API keys, and environment-specific values.
"""

from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator
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
    environment: Literal["development", "staging", "production", "test"] = Field(
        default="development",
        description="Application environment",
    )
    debug: bool = Field(
        default=True,
        description="Debug mode flag",
    )

    # Database Configuration
    database_url: str = Field(
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
    enable_query_logging: bool = Field(
        default=False,
        description="Enable detailed query logging with execution times",
    )
    bar_batch_size: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Batch size for bulk bar operations (insert/query)",
    )

    # Redis Configuration
    enable_bar_cache: bool = Field(
        default=False,
        description="Enable Redis cache for bar data (optional, for performance)",
    )
    bar_cache_ttl: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="Bar cache TTL in seconds",
    )
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
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for analytics caching (Task 4)",
    )

    # External API Configuration
    polygon_api_key: str = Field(
        default="",
        description="Polygon.io API key for market data",
    )
    alpaca_api_key: str = Field(
        default="",
        description="Alpaca Markets API key for market data",
    )
    alpaca_secret_key: str = Field(
        default="",
        description="Alpaca Markets secret key for authentication",
    )

    # Twelve Data API Configuration (Story 21.1)
    twelvedata_api_key: str = Field(
        default="",
        description="Twelve Data API key for symbol validation",
    )
    twelvedata_base_url: str = Field(
        default="https://api.twelvedata.com",
        description="Twelve Data API base URL",
    )
    twelvedata_rate_limit: int = Field(
        default=8,
        ge=1,
        le=100,
        description="Twelve Data API rate limit (requests per minute)",
    )
    twelvedata_timeout: int = Field(
        default=10,
        ge=1,
        le=60,
        description="Twelve Data API request timeout in seconds",
    )

    # Real-Time Data Feed Configuration
    watchlist_symbols: list[str] = Field(
        default=["AAPL", "TSLA", "SPY"],
        description="Symbols to stream real-time data for",
    )
    bar_timeframe: str = Field(
        default="1m",
        description="Real-time bar timeframe (1m, 5m, 15m, 1h, 1d)",
    )

    # Real-Time Pattern Scanner Configuration (Story 19.1)
    scanner_queue_max_size: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Maximum bars to queue for pattern scanning",
    )
    scanner_processing_timeout_ms: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Target processing time per bar in milliseconds",
    )
    scanner_circuit_breaker_threshold: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Consecutive failures before circuit breaker opens",
    )
    scanner_circuit_breaker_reset_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Seconds before circuit breaker resets from open to half-open",
    )

    # Stale Data Protection Configuration (Story 19.26)
    staleness_threshold_seconds: int = Field(
        default=300,
        ge=60,
        le=1800,
        description="Seconds before symbol data is considered stale (5 minutes default)",
    )
    staleness_alert_threshold_seconds: int = Field(
        default=900,
        ge=300,
        le=3600,
        description="Seconds of staleness before alerting during market hours (15 minutes default). "
        "Used by Prometheus alert rules in alert-rules.yml.",
    )

    # Data Ingestion Settings
    default_provider: str = Field(
        default="polygon",
        description="Default market data provider (polygon, yahoo, alpaca)",
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

    # Risk Management Configuration
    risk_allocation_config_path: str = Field(
        default="config/risk_allocation.yaml",
        description="Path to risk allocation configuration file (relative to backend/)",
    )

    # MasterOrchestrator Configuration (Story 8.10)
    max_concurrent_symbols: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Parallel symbol processing limit (orchestrator)",
    )
    cache_ttl_seconds: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Cache expiration time for ranges/phases (5 min default)",
    )
    performance_alert_threshold_ms: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Latency alert threshold in milliseconds (NFR1: <1s)",
    )
    backpressure_queue_size: int = Field(
        default=10,
        ge=5,
        le=100,
        description="Max queued bars for real-time processing",
    )
    enable_real_time_mode: bool = Field(
        default=True,
        description="Enable WebSocket bar processing",
    )
    enable_performance_tracking: bool = Field(
        default=True,
        description="Enable pipeline latency tracking",
    )
    forex_volume_source: Literal["TICK", "ACTUAL", "ESTIMATED"] = Field(
        default="TICK",
        description="Default volume source for forex (TICK for most brokers)",
    )

    # JWT Authentication Configuration (Story 11.7)
    jwt_secret_key: str = Field(
        default="dev-secret-key-change-in-production-use-64-char-random-string",
        description="Secret key for JWT token signing (MUST be changed in production)",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm",
    )
    jwt_access_token_expire_minutes: int = Field(
        default=30,
        ge=5,
        le=1440,
        description="Access token expiration time in minutes (default: 30 min)",
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Refresh token expiration time in days (default: 7 days)",
    )

    # Broker Router Configuration (Story 23.7)
    auto_execute_orders: bool = Field(
        default=False,
        description="Automatically execute orders via broker after webhook receipt (default: off)",
    )

    # Email Notification Configuration (Story 19.25)
    email_provider: Literal["smtp", "sendgrid", "ses"] = Field(
        default="smtp",
        description="Email provider (smtp, sendgrid, ses)",
    )
    email_from_address: str = Field(
        default="alerts@bmad-trading.com",
        description="Sender email address for notifications",
    )
    email_from_name: str = Field(
        default="BMAD Trading Alerts",
        description="Sender name for notifications",
    )
    email_rate_limit_per_hour: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum email notifications per user per hour",
    )
    sendgrid_api_key: str = Field(
        default="",
        description="SendGrid API key (if using sendgrid provider)",
    )
    app_base_url: str = Field(
        default="http://localhost:5173",
        description="Base URL for links in email notifications",
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

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        """Validate that production environment has secure configuration."""
        if self.environment == "production":
            if (
                self.jwt_secret_key
                == "dev-secret-key-change-in-production-use-64-char-random-string"
            ):
                raise ValueError(
                    "JWT_SECRET_KEY must be changed from default in production. "
                    'Generate with: python -c "import secrets; print(secrets.token_urlsafe(64))"'
                )
            if self.debug:
                raise ValueError("DEBUG must be False in production environment")
            if "changeme" in self.database_url.lower():
                import warnings

                warnings.warn(
                    "DATABASE_URL appears to contain a default password. "
                    "Use a strong, unique password in production.",
                    stacklevel=2,
                )
        return self


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """
    Get the global settings instance.

    Returns
    -------
    Settings
        Application settings object
    """
    return settings


# ============================================================================
# BMAD Position Allocation Constants (Story 9.2, FR23)
# ============================================================================
# BMAD Methodology: Spring (40%) gets largest allocation as it has tightest
# stop and highest R-multiple potential. SOS (30%) and LPS (30%) share
# remaining 60% as they have wider stops but lower R-multiple.
# Total campaign budget: 5% maximum (FR18) = 40% + 30% + 30%

# Campaign Risk Limits (FR18)
CAMPAIGN_MAX_RISK_PCT: Decimal = Decimal("5.0")  # 5% maximum per campaign

# BMAD Allocation Percentages (FR23)
BMAD_SPRING_ALLOCATION: Decimal = Decimal("0.40")  # 40% of campaign budget
BMAD_SOS_ALLOCATION: Decimal = Decimal("0.30")  # 30% of campaign budget
BMAD_LPS_ALLOCATION: Decimal = Decimal("0.30")  # 30% of campaign budget

# Pattern-Specific Risk Percentages (FR16)
# These determine actual position size based on pattern type
PATTERN_RISK_SPRING: Decimal = Decimal("0.005")  # 0.5% of portfolio
PATTERN_RISK_SOS: Decimal = Decimal("0.010")  # 1.0% of portfolio
PATTERN_RISK_LPS: Decimal = Decimal("0.006")  # 0.6% of portfolio
PATTERN_RISK_UTAD: Decimal = Decimal("0.005")  # 0.5% of portfolio

# Special Confidence Threshold (AC: 11)
# When LPS is sole entry (100% allocation), require elevated confidence
LPS_SOLE_ENTRY_MIN_CONFIDENCE: Decimal = Decimal("75.0")  # 75% vs normal 70%
