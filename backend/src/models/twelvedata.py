"""
Pydantic models for Twelve Data API responses.

These models represent the data structures returned by the Twelve Data API
for symbol search, forex pairs, indices, and cryptocurrency endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SymbolSearchResult(BaseModel):
    """
    Result from Twelve Data symbol search endpoint.

    API Response Example:
    {
        "symbol": "EURUSD",
        "instrument_name": "Euro / US Dollar",
        "exchange": "FOREX",
        "exchange_timezone": "UTC",
        "instrument_type": "Physical Currency",
        "country": "",
        "currency": "USD"
    }
    """

    symbol: str = Field(..., description="Symbol identifier (e.g., EURUSD)")
    name: str = Field(..., alias="instrument_name", description="Full instrument name")
    exchange: str = Field(..., description="Exchange name")
    type: str = Field(..., alias="instrument_type", description="Instrument type")
    currency: str = Field(default="", description="Quote currency")

    model_config = {"populate_by_name": True}


class SymbolInfo(BaseModel):
    """
    Detailed symbol information.

    Generic structure for symbol info across asset classes.
    """

    symbol: str = Field(..., description="Symbol identifier")
    name: str = Field(..., description="Full instrument name")
    exchange: str = Field(..., description="Exchange name")
    type: str = Field(..., description="Instrument type")
    currency_base: str | None = Field(default=None, description="Base currency (for forex/crypto)")
    currency_quote: str | None = Field(
        default=None, description="Quote currency (for forex/crypto)"
    )


class ForexPairInfo(BaseModel):
    """
    Forex pair information from Twelve Data.

    API Response Example:
    {
        "symbol": "EUR/USD",
        "currency_group": "Major",
        "currency_base": "Euro",
        "currency_quote": "US Dollar"
    }
    """

    symbol: str = Field(..., description="Forex pair symbol (e.g., EUR/USD)")
    currency_group: str = Field(default="", description="Currency group (Major, Minor, Exotic)")
    currency_base: str = Field(..., description="Base currency name")
    currency_quote: str = Field(..., description="Quote currency name")


class IndexInfo(BaseModel):
    """
    Index information from Twelve Data.

    API Response Example:
    {
        "symbol": "SPX",
        "name": "S&P 500",
        "country": "United States",
        "currency": "USD"
    }
    """

    symbol: str = Field(..., description="Index symbol")
    name: str = Field(..., description="Index name")
    country: str = Field(default="", description="Country of origin")
    currency: str = Field(default="", description="Index currency")


class CryptoInfo(BaseModel):
    """
    Cryptocurrency information from Twelve Data.

    API Response Example:
    {
        "symbol": "BTC/USD",
        "currency_base": "Bitcoin",
        "currency_quote": "US Dollar",
        "available_exchanges": ["Binance", "Coinbase"]
    }
    """

    symbol: str = Field(..., description="Crypto pair symbol (e.g., BTC/USD)")
    currency_base: str = Field(..., description="Base cryptocurrency name")
    currency_quote: str = Field(..., description="Quote currency name")
    available_exchanges: list[str] = Field(
        default_factory=list, description="List of available exchanges"
    )
