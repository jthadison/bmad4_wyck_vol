"""
TwelveData API Response Models (Story 21.1)

Pydantic models for parsing TwelveData API responses:
- SymbolSearchResult: Symbol search endpoint response
- SymbolInfo: General symbol information
- ForexPairInfo: Forex pair details
- IndexInfo: Index details
- CryptoInfo: Cryptocurrency details
"""

from pydantic import BaseModel, Field


class SymbolSearchResult(BaseModel):
    """Result from TwelveData symbol search endpoint."""

    symbol: str = Field(..., description="Symbol identifier (e.g., EURUSD)")
    name: str = Field(..., description="Full instrument name")
    exchange: str = Field(..., description="Exchange where traded")
    type: str = Field(..., description="Instrument type")
    currency: str | None = Field(default=None, description="Quote currency")
    country: str | None = Field(default=None, description="Country of origin")

    class Config:
        extra = "ignore"


class SymbolInfo(BaseModel):
    """Detailed symbol information from TwelveData."""

    symbol: str = Field(..., description="Symbol identifier")
    name: str = Field(..., description="Full instrument name")
    exchange: str = Field(..., description="Exchange")
    type: str = Field(..., description="Instrument type (forex, index, crypto, stock)")
    currency: str | None = Field(default=None, description="Quote currency")
    currency_base: str | None = Field(default=None, description="Base currency (forex)")
    currency_quote: str | None = Field(default=None, description="Quote currency (forex)")

    class Config:
        extra = "ignore"


class ForexPairInfo(BaseModel):
    """Forex pair information from TwelveData."""

    symbol: str = Field(..., description="Forex pair symbol (EUR/USD format)")
    currency_group: str | None = Field(default=None, description="Major/Minor/Exotic")
    currency_base: str | None = Field(default=None, description="Base currency name")
    currency_quote: str | None = Field(default=None, description="Quote currency name")

    class Config:
        extra = "ignore"


class IndexInfo(BaseModel):
    """Index information from TwelveData."""

    symbol: str = Field(..., description="Index symbol")
    name: str = Field(..., description="Index name")
    country: str | None = Field(default=None, description="Country")
    currency: str | None = Field(default=None, description="Currency")

    class Config:
        extra = "ignore"


class CryptoInfo(BaseModel):
    """Cryptocurrency information from TwelveData."""

    symbol: str = Field(..., description="Crypto pair symbol")
    currency_base: str | None = Field(default=None, description="Base cryptocurrency")
    currency_quote: str | None = Field(default=None, description="Quote currency")

    class Config:
        extra = "ignore"
