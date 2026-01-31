"""
TwelveData API Response Models (Story 21.1)

Pydantic models for parsing TwelveData API responses.
These are separate from validation.py models which are for internal use.

Models:
- TwelveDataSearchResult: Symbol search endpoint response (API-specific)
- SymbolInfo: General symbol information
- ForexPairInfo: Forex pair details
- IndexInfo: Index details
- CryptoInfo: Cryptocurrency details
"""

from pydantic import BaseModel, ConfigDict, Field


class SymbolSearchResult(BaseModel):
    """Result from TwelveData symbol search endpoint (API response model)."""

    symbol: str = Field(..., description="Symbol identifier (e.g., EURUSD)")
    name: str = Field(..., description="Full instrument name")
    exchange: str = Field(..., description="Exchange where traded")
    type: str = Field(..., description="Instrument type")
    currency: str | None = Field(default=None, description="Quote currency")
    country: str | None = Field(default=None, description="Country of origin")

    model_config = ConfigDict(extra="ignore")


class SymbolInfo(BaseModel):
    """Detailed symbol information from TwelveData (API response model)."""

    symbol: str = Field(..., description="Symbol identifier")
    name: str = Field(..., description="Full instrument name")
    exchange: str = Field(..., description="Exchange")
    type: str = Field(..., description="Instrument type (forex, index, crypto, stock)")
    currency: str | None = Field(default=None, description="Quote currency")
    currency_base: str | None = Field(default=None, description="Base currency (forex)")
    currency_quote: str | None = Field(default=None, description="Quote currency (forex)")

    model_config = ConfigDict(extra="ignore")


class ForexPairInfo(BaseModel):
    """Forex pair information from TwelveData."""

    symbol: str = Field(..., description="Forex pair symbol (EUR/USD format)")
    currency_group: str | None = Field(default=None, description="Major/Minor/Exotic")
    currency_base: str | None = Field(default=None, description="Base currency name")
    currency_quote: str | None = Field(default=None, description="Quote currency name")

    model_config = ConfigDict(extra="ignore")


class IndexInfo(BaseModel):
    """Index information from TwelveData."""

    symbol: str = Field(..., description="Index symbol")
    name: str = Field(..., description="Index name")
    country: str | None = Field(default=None, description="Country")
    currency: str | None = Field(default=None, description="Currency")

    model_config = ConfigDict(extra="ignore")


class CryptoInfo(BaseModel):
    """Cryptocurrency information from TwelveData."""

    symbol: str = Field(..., description="Crypto pair symbol")
    currency_base: str | None = Field(default=None, description="Base cryptocurrency")
    currency_quote: str | None = Field(default=None, description="Quote currency")

    model_config = ConfigDict(extra="ignore")
