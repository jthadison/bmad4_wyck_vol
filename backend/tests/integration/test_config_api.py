"""
Integration tests for configuration API endpoints.

Tests complete API workflows including database operations.
"""


import pytest
from httpx import AsyncClient
from sqlalchemy import text

from src.api.main import app
from src.database import async_session_maker


@pytest.fixture
async def async_client():
    """Create async HTTP client for testing."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
async def setup_test_config():
    """Setup test configuration in database."""
    async with async_session_maker() as session:
        # Ensure default config exists
        check_query = text("SELECT COUNT(*) FROM system_configuration")
        result = await session.execute(check_query)
        count = result.scalar()

        if count == 0:
            # Insert default config
            insert_query = text(
                """
                INSERT INTO system_configuration (version, configuration_json, applied_by)
                VALUES (
                    1,
                    :config_json,
                    'test_setup'
                )
            """
            )
            config_dict = {
                "volume_thresholds": {
                    "spring_volume_min": "0.7",
                    "spring_volume_max": "1.0",
                    "sos_volume_min": "2.0",
                    "lps_volume_min": "0.5",
                    "utad_volume_max": "0.7",
                },
                "risk_limits": {
                    "max_risk_per_trade": "2.0",
                    "max_campaign_risk": "5.0",
                    "max_portfolio_heat": "10.0",
                },
                "cause_factors": {"min_cause_factor": "2.0", "max_cause_factor": "3.0"},
                "pattern_confidence": {
                    "min_spring_confidence": 70,
                    "min_sos_confidence": 70,
                    "min_lps_confidence": 70,
                    "min_utad_confidence": 70,
                },
            }
            await session.execute(insert_query, {"config_json": config_dict})
            await session.commit()

    yield

    # Cleanup handled by transaction rollback


class TestGetConfiguration:
    """Tests for GET /api/v1/config endpoint."""

    @pytest.mark.asyncio
    async def test_get_current_configuration_success(self, async_client, setup_test_config):
        """Test successful retrieval of current configuration."""
        response = await async_client.get("/api/v1/config")

        assert response.status_code == 200
        data = response.json()

        assert "data" in data
        assert "metadata" in data
        assert data["data"]["version"] >= 1
        assert "volume_thresholds" in data["data"]
        assert "risk_limits" in data["data"]
        assert "cause_factors" in data["data"]
        assert "pattern_confidence" in data["data"]

    @pytest.mark.asyncio
    async def test_get_configuration_includes_metadata(self, async_client, setup_test_config):
        """Test that response includes metadata."""
        response = await async_client.get("/api/v1/config")

        assert response.status_code == 200
        data = response.json()

        metadata = data["metadata"]
        assert "version" in metadata
        assert "last_modified_at" in metadata
        assert "modified_by" in metadata


class TestUpdateConfiguration:
    """Tests for PUT /api/v1/config endpoint."""

    @pytest.mark.asyncio
    async def test_update_configuration_success(self, async_client, setup_test_config):
        """Test successful configuration update."""
        # First get current config
        get_response = await async_client.get("/api/v1/config")
        current_data = get_response.json()["data"]
        current_version = current_data["version"]

        # Modify configuration
        current_data["volume_thresholds"]["spring_volume_min"] = "0.65"

        # Update configuration
        update_payload = {"configuration": current_data, "current_version": current_version}

        response = await async_client.put("/api/v1/config", json=update_payload)

        assert response.status_code == 200
        data = response.json()

        assert data["data"]["version"] == current_version + 1
        assert data["data"]["volume_thresholds"]["spring_volume_min"] == "0.65"
        assert "message" in data["metadata"]

    @pytest.mark.asyncio
    async def test_update_configuration_optimistic_lock_conflict(
        self, async_client, setup_test_config
    ):
        """Test optimistic locking prevents concurrent updates."""
        # Get current config
        get_response = await async_client.get("/api/v1/config")
        current_data = get_response.json()["data"]

        # Try to update with wrong version
        current_data["volume_thresholds"]["spring_volume_min"] = "0.65"
        update_payload = {
            "configuration": current_data,
            "current_version": 999,  # Wrong version
        }

        response = await async_client.put("/api/v1/config", json=update_payload)

        assert response.status_code == 409  # Conflict
        error = response.json()["detail"]
        assert error["code"] == "VERSION_CONFLICT"
        assert "expected_version" in error

    @pytest.mark.asyncio
    async def test_update_configuration_validation_error(self, async_client, setup_test_config):
        """Test that validation errors return 422."""
        # Get current config
        get_response = await async_client.get("/api/v1/config")
        current_data = get_response.json()["data"]
        current_version = current_data["version"]

        # Create invalid config (violate risk hierarchy)
        current_data["risk_limits"]["max_campaign_risk"] = "1.5"  # Less than max_risk_per_trade

        update_payload = {"configuration": current_data, "current_version": current_version}

        response = await async_client.put("/api/v1/config", json=update_payload)

        assert response.status_code == 422  # Unprocessable Entity
        error = response.json()["detail"]
        assert error["code"] == "VALIDATION_ERROR"


class TestAnalyzeImpact:
    """Tests for POST /api/v1/config/analyze-impact endpoint."""

    @pytest.mark.asyncio
    async def test_analyze_impact_success(self, async_client, setup_test_config):
        """Test successful impact analysis."""
        # Get current config
        get_response = await async_client.get("/api/v1/config")
        current_data = get_response.json()["data"]

        # Modify configuration for analysis
        proposed_config = current_data.copy()
        proposed_config["volume_thresholds"]["spring_volume_min"] = "0.6"

        response = await async_client.post("/api/v1/config/analyze-impact", json=proposed_config)

        assert response.status_code == 200
        data = response.json()

        assert "data" in data
        impact = data["data"]
        assert "signal_count_delta" in impact
        assert "current_signal_count" in impact
        assert "proposed_signal_count" in impact
        assert "recommendations" in impact
        assert isinstance(impact["recommendations"], list)

    @pytest.mark.asyncio
    async def test_analyze_impact_includes_recommendations(self, async_client, setup_test_config):
        """Test that impact analysis includes recommendations."""
        # Get current config
        get_response = await async_client.get("/api/v1/config")
        current_data = get_response.json()["data"]

        # Relax spring volume (should trigger WARNING)
        proposed_config = current_data.copy()
        proposed_config["volume_thresholds"]["spring_volume_min"] = "0.5"

        response = await async_client.post("/api/v1/config/analyze-impact", json=proposed_config)

        assert response.status_code == 200
        impact = response.json()["data"]

        # Should have at least one recommendation
        assert len(impact["recommendations"]) > 0

        # Should have WARNING about spring volume
        warnings = [r for r in impact["recommendations"] if r["severity"] == "WARNING"]
        assert len(warnings) > 0

    @pytest.mark.asyncio
    async def test_analyze_impact_calculates_win_rate(self, async_client, setup_test_config):
        """Test that impact analysis calculates win rates."""
        # Get current config
        get_response = await async_client.get("/api/v1/config")
        current_data = get_response.json()["data"]

        response = await async_client.post("/api/v1/config/analyze-impact", json=current_data)

        assert response.status_code == 200
        impact = response.json()["data"]

        # Should calculate win rates (may be null if no patterns)
        assert "current_win_rate" in impact
        assert "proposed_win_rate" in impact
        assert "confidence_range" in impact


class TestConfigurationHistory:
    """Tests for GET /api/v1/config/history endpoint."""

    @pytest.mark.asyncio
    async def test_get_configuration_history(self, async_client, setup_test_config):
        """Test retrieval of configuration history."""
        response = await async_client.get("/api/v1/config/history?limit=5")

        assert response.status_code == 200
        data = response.json()

        assert "data" in data
        assert isinstance(data["data"], list)
        assert "metadata" in data
        assert data["metadata"]["limit"] == 5

    @pytest.mark.asyncio
    async def test_configuration_history_ordered_by_version_desc(
        self, async_client, setup_test_config
    ):
        """Test that history is ordered by version descending."""
        # Create multiple versions
        for i in range(3):
            get_response = await async_client.get("/api/v1/config")
            current_data = get_response.json()["data"]
            current_version = current_data["version"]

            current_data["volume_thresholds"]["spring_volume_min"] = str(0.7 - (i * 0.05))

            update_payload = {"configuration": current_data, "current_version": current_version}
            await async_client.put("/api/v1/config", json=update_payload)

        # Get history
        response = await async_client.get("/api/v1/config/history?limit=10")
        history = response.json()["data"]

        # Should be ordered descending
        versions = [item["version"] for item in history]
        assert versions == sorted(versions, reverse=True)


class TestEndToEndWorkflow:
    """End-to-end workflow tests."""

    @pytest.mark.asyncio
    async def test_complete_configuration_update_workflow(self, async_client, setup_test_config):
        """Test complete workflow: get -> analyze -> update -> verify."""
        # 1. Get current configuration
        get_response = await async_client.get("/api/v1/config")
        assert get_response.status_code == 200
        current_data = get_response.json()["data"]
        current_version = current_data["version"]
        original_spring_volume = current_data["volume_thresholds"]["spring_volume_min"]

        # 2. Modify configuration
        proposed_config = current_data.copy()
        proposed_config["volume_thresholds"]["spring_volume_min"] = "0.65"

        # 3. Analyze impact
        analyze_response = await async_client.post(
            "/api/v1/config/analyze-impact", json=proposed_config
        )
        assert analyze_response.status_code == 200
        impact = analyze_response.json()["data"]
        assert len(impact["recommendations"]) > 0

        # 4. Update configuration
        update_payload = {"configuration": proposed_config, "current_version": current_version}
        update_response = await async_client.put("/api/v1/config", json=update_payload)
        assert update_response.status_code == 200
        updated_data = update_response.json()["data"]
        assert updated_data["version"] == current_version + 1
        assert updated_data["volume_thresholds"]["spring_volume_min"] == "0.65"

        # 5. Verify configuration persisted
        verify_response = await async_client.get("/api/v1/config")
        assert verify_response.status_code == 200
        verified_data = verify_response.json()["data"]
        assert verified_data["version"] == current_version + 1
        assert verified_data["volume_thresholds"]["spring_volume_min"] == "0.65"

        # 6. Check history includes old version
        history_response = await async_client.get("/api/v1/config/history?limit=10")
        history = history_response.json()["data"]
        assert len(history) >= 2
        assert any(item["version"] == current_version for item in history)
