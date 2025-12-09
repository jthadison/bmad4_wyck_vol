"""
Unit tests for Pattern Statistics API endpoint (Story 10.7)

Tests GET /api/v1/patterns/statistics endpoint functionality:
- Statistics retrieval for valid pattern types
- Invalid pattern type validation
- Insufficient data handling
- Win rate calculations
- Sample size validation
"""

from fastapi import status
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_get_statistics_spring_volume_high():
    """Test retrieving statistics for SPRING with volume_high rejection."""
    response = client.get(
        "/api/v1/patterns/statistics",
        params={"pattern_type": "SPRING", "rejection_category": "volume_high"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["pattern_type"] == "SPRING"
    assert data["rejection_category"] == "volume_high"
    assert "invalid_win_rate" in data
    assert "valid_win_rate" in data
    assert data["sufficient_data"] is True
    assert data["sample_size_invalid"] >= 20
    assert "message" in data


def test_get_statistics_utad_volume_high():
    """Test retrieving statistics for UTAD with volume_high rejection."""
    response = client.get(
        "/api/v1/patterns/statistics",
        params={"pattern_type": "UTAD", "rejection_category": "volume_high"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["pattern_type"] == "UTAD"
    assert data["rejection_category"] == "volume_high"


def test_get_statistics_sos_volume_low():
    """Test retrieving statistics for SOS with volume_low rejection."""
    response = client.get(
        "/api/v1/patterns/statistics",
        params={"pattern_type": "SOS", "rejection_category": "volume_low"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["pattern_type"] == "SOS"
    assert data["rejection_category"] == "volume_low"


def test_get_statistics_lps_volume_high():
    """Test retrieving statistics for LPS with volume_high rejection."""
    response = client.get(
        "/api/v1/patterns/statistics",
        params={"pattern_type": "LPS", "rejection_category": "volume_high"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["pattern_type"] == "LPS"


def test_get_statistics_sc_volume_low():
    """Test retrieving statistics for SC (Selling Climax) with volume_low rejection."""
    response = client.get(
        "/api/v1/patterns/statistics",
        params={"pattern_type": "SC", "rejection_category": "volume_low"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["pattern_type"] == "SC"


def test_get_statistics_ar_volume_low():
    """Test retrieving statistics for AR (Automatic Rally) with volume_low rejection."""
    response = client.get(
        "/api/v1/patterns/statistics",
        params={"pattern_type": "AR", "rejection_category": "volume_low"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["pattern_type"] == "AR"


def test_get_statistics_st_volume_high():
    """Test retrieving statistics for ST (Secondary Test) with volume_high rejection."""
    response = client.get(
        "/api/v1/patterns/statistics",
        params={"pattern_type": "ST", "rejection_category": "volume_high"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["pattern_type"] == "ST"


def test_get_statistics_invalid_pattern_type():
    """Test invalid pattern_type returns 400 error."""
    response = client.get(
        "/api/v1/patterns/statistics",
        params={"pattern_type": "INVALID_PATTERN"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid pattern_type" in response.json()["detail"]


def test_get_statistics_missing_pattern_type():
    """Test missing pattern_type parameter returns 422 error."""
    response = client.get("/api/v1/patterns/statistics")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_get_statistics_without_rejection_category():
    """Test retrieving statistics without rejection_category parameter."""
    # This should return 404 because we don't have stats for this combination in mock data
    response = client.get(
        "/api/v1/patterns/statistics",
        params={"pattern_type": "SPRING"},
    )

    # Mock data doesn't have entry without rejection_category
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_statistics_insufficient_data():
    """Test retrieving statistics for combination with insufficient data returns 404."""
    response = client.get(
        "/api/v1/patterns/statistics",
        params={"pattern_type": "SPRING", "rejection_category": "nonexistent"},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "Insufficient" in response.json()["detail"]


def test_statistics_win_rate_format():
    """Test win rates are returned as decimal strings."""
    response = client.get(
        "/api/v1/patterns/statistics",
        params={"pattern_type": "SPRING", "rejection_category": "volume_high"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Win rates should be strings (Decimal serialized)
    assert isinstance(data["invalid_win_rate"], str)
    assert isinstance(data["valid_win_rate"], str)

    # Should be parseable as floats
    invalid_rate = float(data["invalid_win_rate"])
    valid_rate = float(data["valid_win_rate"])

    assert 0 <= invalid_rate <= 100
    assert 0 <= valid_rate <= 100


def test_statistics_sample_sizes():
    """Test sample sizes are positive integers."""
    response = client.get(
        "/api/v1/patterns/statistics",
        params={"pattern_type": "SPRING", "rejection_category": "volume_high"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert isinstance(data["sample_size_invalid"], int)
    assert isinstance(data["sample_size_valid"], int)
    assert data["sample_size_invalid"] > 0
    assert data["sample_size_valid"] > 0


def test_statistics_message_format():
    """Test message includes comparative win rates."""
    response = client.get(
        "/api/v1/patterns/statistics",
        params={"pattern_type": "SPRING", "rejection_category": "volume_high"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    message = data["message"]
    assert "Springs" in message
    assert "volume" in message
    assert "%" in message
    assert "win rate" in message
