"""
Symbol Search Response Models (Story 21.4)

Defines Pydantic models for the symbol search API endpoint.

Author: Story 21.4
"""

from pydantic import BaseModel, ConfigDict, Field


class SymbolSearchResponse(BaseModel):
    """
    Symbol search result response model.

    Represents a single search result from the symbol search endpoint.
    """

    symbol: str = Field(
        ...,
        description="Trading symbol (e.g., EURUSD, AAPL)",
        examples=["EURUSD"],
    )
    name: str = Field(
        ...,
        description="Full instrument name",
        examples=["Euro / US Dollar"],
    )
    exchange: str = Field(
        ...,
        description="Exchange or market",
        examples=["FOREX"],
    )
    type: str = Field(
        ...,
        description="Asset type (forex, crypto, index, stock)",
        examples=["forex"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "symbol": "EURUSD",
                "name": "Euro / US Dollar",
                "exchange": "FOREX",
                "type": "forex",
            }
        }
    )
