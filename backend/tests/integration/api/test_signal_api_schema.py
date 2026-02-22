"""
Integration Tests for Signal API OpenAPI Schema (Story 8.8)

Tests for:
- OpenAPI schema includes TradeSignal component
- All FR22 fields present in schema with correct types
- API endpoints return valid schema-compliant responses
- Field descriptions and examples present

Author: Story 8.8 (AC 9)
"""


import pytest
import pytest_asyncio
from httpx import AsyncClient

from src.repositories.signal_repository import SignalRepository
from tests.fixtures.signal_fixtures import valid_spring_signal


@pytest_asyncio.fixture
async def signal_repo(db_session):
    """Provide signal repository with test database session."""
    return SignalRepository(db_session=db_session)


# ============================================================================
# OpenAPI Schema Tests (AC: 9)
# ============================================================================


@pytest.mark.asyncio
async def test_openapi_schema_includes_trade_signal(async_client: AsyncClient):
    """Test OpenAPI schema includes TradeSignal component definition."""
    response = await async_client.get("/openapi.json")
    assert response.status_code == 200

    schema = response.json()

    # Check components section exists
    assert "components" in schema
    assert "schemas" in schema["components"]

    # Check TradeSignal schema exists
    schemas = schema["components"]["schemas"]
    assert "TradeSignal" in schemas

    trade_signal_schema = schemas["TradeSignal"]

    # Check properties section exists
    assert "properties" in trade_signal_schema


@pytest.mark.asyncio
async def test_openapi_schema_has_all_fr22_fields(async_client: AsyncClient):
    """Test TradeSignal schema contains all FR22 required fields."""
    response = await async_client.get("/openapi.json")
    schema = response.json()

    trade_signal_schema = schema["components"]["schemas"]["TradeSignal"]
    properties = trade_signal_schema["properties"]

    # FR22 required fields
    fr22_fields = [
        "symbol",
        "pattern_type",
        "phase",
        "entry_price",
        "stop_loss",
        "target_levels",
        "position_size",
        "risk_amount",
        "r_multiple",
        "confidence_score",
        "campaign_id",
        "timestamp",
    ]

    for field in fr22_fields:
        assert field in properties, f"FR22 field '{field}' missing from schema"


@pytest.mark.asyncio
async def test_openapi_schema_has_forex_support_fields(async_client: AsyncClient):
    """Test TradeSignal schema includes FOREX support fields (AC: 11-14)."""
    response = await async_client.get("/openapi.json")
    schema = response.json()

    trade_signal_schema = schema["components"]["schemas"]["TradeSignal"]
    properties = trade_signal_schema["properties"]

    # FOREX support fields (AC: 11-14)
    forex_fields = [
        "asset_class",
        "position_size_unit",
        "leverage",
        "margin_requirement",
        "notional_value",
    ]

    for field in forex_fields:
        assert field in properties, f"FOREX field '{field}' missing from schema"


@pytest.mark.asyncio
async def test_openapi_schema_has_validation_fields(async_client: AsyncClient):
    """Test TradeSignal schema includes validation and audit fields."""
    response = await async_client.get("/openapi.json")
    schema = response.json()

    trade_signal_schema = schema["components"]["schemas"]["TradeSignal"]
    properties = trade_signal_schema["properties"]

    # Validation and audit fields
    validation_fields = [
        "validation_chain",
        "confidence_components",
        "status",
        "rejection_reasons",
        "pattern_data",
        "volume_analysis",
        "schema_version",
    ]

    for field in validation_fields:
        assert field in properties, f"Validation field '{field}' missing from schema"


@pytest.mark.asyncio
async def test_openapi_schema_field_descriptions(async_client: AsyncClient):
    """Test TradeSignal schema fields have descriptions."""
    response = await async_client.get("/openapi.json")
    schema = response.json()

    trade_signal_schema = schema["components"]["schemas"]["TradeSignal"]
    properties = trade_signal_schema["properties"]

    # Check key fields have descriptions
    key_fields = ["symbol", "entry_price", "stop_loss", "position_size", "confidence_score"]

    for field in key_fields:
        assert "description" in properties[field], f"Field '{field}' missing description"
        assert len(properties[field]["description"]) > 0


@pytest.mark.asyncio
async def test_openapi_schema_nested_models(async_client: AsyncClient):
    """Test OpenAPI schema includes nested models (TargetLevels, ConfidenceComponents)."""
    response = await async_client.get("/openapi.json")
    schema = response.json()

    schemas = schema["components"]["schemas"]

    # Check nested models exist
    assert "TargetLevels" in schemas
    assert "ConfidenceComponents" in schemas
    assert "ValidationChain" in schemas


@pytest.mark.asyncio
async def test_target_levels_schema_structure(async_client: AsyncClient):
    """Test TargetLevels schema has correct structure."""
    response = await async_client.get("/openapi.json")
    schema = response.json()

    target_levels_schema = schema["components"]["schemas"]["TargetLevels"]
    properties = target_levels_schema["properties"]

    # Required fields
    assert "primary_target" in properties
    assert "secondary_targets" in properties
    assert "trailing_stop_activation" in properties
    assert "trailing_stop_offset" in properties


@pytest.mark.asyncio
async def test_confidence_components_schema_structure(async_client: AsyncClient):
    """Test ConfidenceComponents schema has correct structure."""
    response = await async_client.get("/openapi.json")
    schema = response.json()

    confidence_schema = schema["components"]["schemas"]["ConfidenceComponents"]
    properties = confidence_schema["properties"]

    # Required fields
    assert "pattern_confidence" in properties
    assert "phase_confidence" in properties
    assert "volume_confidence" in properties
    assert "overall_confidence" in properties


# ============================================================================
# API Endpoint Response Schema Tests
# ============================================================================


@pytest.mark.asyncio
async def test_list_signals_endpoint_schema_compliance(
    async_client: AsyncClient, signal_repo: SignalRepository
):
    """Test GET /api/v1/signals returns schema-compliant response."""
    # Add test signal to database
    signal = valid_spring_signal()
    await signal_repo.save_signal(signal)

    # Call endpoint
    response = await async_client.get("/api/v1/signals")
    assert response.status_code == 200

    data = response.json()

    # Check response structure
    assert "data" in data
    assert "pagination" in data

    # Check pagination structure
    pagination = data["pagination"]
    assert "returned_count" in pagination
    assert "total_count" in pagination
    assert "limit" in pagination
    assert "offset" in pagination
    assert "has_more" in pagination

    # Check signal data structure
    if len(data["data"]) > 0:
        signal_data = data["data"][0]
        # Verify all FR22 fields present
        fr22_fields = [
            "symbol",
            "pattern_type",
            "phase",
            "entry_price",
            "stop_loss",
            "position_size",
            "confidence_score",
            "timestamp",
        ]
        for field in fr22_fields:
            assert field in signal_data, f"Field '{field}' missing from API response"


@pytest.mark.asyncio
async def test_get_signal_endpoint_schema_compliance(
    async_client: AsyncClient, signal_repo: SignalRepository
):
    """Test GET /api/v1/signals/{id} returns schema-compliant response."""
    # Add test signal to database
    signal = valid_spring_signal()
    await signal_repo.save_signal(signal)

    # Call endpoint
    response = await async_client.get(f"/api/v1/signals/{signal.id}")
    assert response.status_code == 200

    signal_data = response.json()

    # Verify all FR22 fields present and correct types
    assert signal_data["symbol"] == "AAPL"
    assert signal_data["pattern_type"] == "SPRING"
    assert signal_data["phase"] == "C"

    # Decimal fields should be strings
    assert isinstance(signal_data["entry_price"], str)
    # Note: DB may store with extra precision, just verify the value is correct
    from decimal import Decimal

    assert Decimal(signal_data["entry_price"]) == Decimal("150.00")

    # Nested models
    assert "target_levels" in signal_data
    assert "primary_target" in signal_data["target_levels"]

    assert "confidence_components" in signal_data
    assert "pattern_confidence" in signal_data["confidence_components"]

    assert "validation_chain" in signal_data


@pytest.mark.asyncio
async def test_patch_signal_endpoint_schema_compliance(
    async_client: AsyncClient, signal_repo: SignalRepository
):
    """Test PATCH /api/v1/signals/{id} returns schema-compliant response."""
    # Add test signal to database
    signal = valid_spring_signal()
    await signal_repo.save_signal(signal)

    # Update signal status
    response = await async_client.patch(
        f"/api/v1/signals/{signal.id}",
        json={
            "status": "FILLED",
            "filled_price": "150.50",
            "filled_timestamp": "2024-03-13T14:35:00Z",
        },
    )
    assert response.status_code == 200

    signal_data = response.json()

    # Should return updated TradeSignal with new status
    assert signal_data["status"] == "FILLED"
    assert signal_data["id"] == str(signal.id)


# ============================================================================
# API Query Parameter Tests
# ============================================================================


@pytest.mark.asyncio
async def test_list_signals_with_filters(async_client: AsyncClient, signal_repo: SignalRepository):
    """Test GET /api/v1/signals with query parameters."""
    # Add multiple signals - use different symbols to test symbol filter
    signal1 = valid_spring_signal()
    signal1 = signal1.model_copy(update={"symbol": "AAPL"})  # confidence_score=85
    await signal_repo.save_signal(signal1)

    signal2 = valid_spring_signal()
    signal2 = signal2.model_copy(update={"symbol": "MSFT"})  # confidence_score=85
    await signal_repo.save_signal(signal2)

    # Filter by symbol
    response = await async_client.get("/api/v1/signals?symbol=AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["pagination"]["returned_count"] == 1
    assert data["data"][0]["symbol"] == "AAPL"

    # Filter by min_confidence (both signals have 85 >= 80)
    response = await async_client.get("/api/v1/signals?min_confidence=80")
    assert response.status_code == 200
    data = response.json()
    assert data["pagination"]["returned_count"] == 2
    assert all(s["confidence_score"] >= 80 for s in data["data"])


@pytest.mark.asyncio
async def test_list_signals_pagination(async_client: AsyncClient, signal_repo: SignalRepository):
    """Test GET /api/v1/signals pagination."""
    # Add 3 signals
    for i in range(3):
        signal = valid_spring_signal()
        await signal_repo.save_signal(signal)

    # Get first page (limit 2)
    response = await async_client.get("/api/v1/signals?limit=2&offset=0")
    assert response.status_code == 200
    data = response.json()

    assert data["pagination"]["returned_count"] == 2
    assert data["pagination"]["total_count"] == 3
    assert data["pagination"]["has_more"] is True

    # Get second page
    response = await async_client.get("/api/v1/signals?limit=2&offset=2")
    assert response.status_code == 200
    data = response.json()

    assert data["pagination"]["returned_count"] == 1
    assert data["pagination"]["has_more"] is False


# ============================================================================
# Error Handling Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_signal_not_found(async_client: AsyncClient):
    """Test GET /api/v1/signals/{id} returns 404 for non-existent signal."""
    from uuid import uuid4

    fake_id = uuid4()
    response = await async_client.get(f"/api/v1/signals/{fake_id}")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_patch_signal_not_found(async_client: AsyncClient):
    """Test PATCH /api/v1/signals/{id} returns 404 for non-existent signal."""
    from uuid import uuid4

    fake_id = uuid4()
    response = await async_client.patch(
        f"/api/v1/signals/{fake_id}",
        json={"status": "FILLED"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_signals_invalid_limit(async_client: AsyncClient):
    """Test GET /api/v1/signals rejects invalid limit parameter."""
    # Limit too large
    response = await async_client.get("/api/v1/signals?limit=500")
    assert response.status_code == 422  # Validation error

    # Limit too small
    response = await async_client.get("/api/v1/signals?limit=0")
    assert response.status_code == 422
