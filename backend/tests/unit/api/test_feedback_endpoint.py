"""
Unit tests for Feedback API endpoint (Story 10.7)

Tests POST /api/v1/feedback endpoint functionality:
- Feedback submission validation
- Signal existence validation
- Explanation requirement for review_request type
- Feedback persistence
- Response status codes and messages
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes.feedback import _feedback_store, _mock_signal_ids

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_feedback_store():
    """Clear feedback store before each test."""
    _feedback_store.clear()
    _mock_signal_ids.clear()
    yield
    _feedback_store.clear()
    _mock_signal_ids.clear()


def test_submit_positive_feedback_success():
    """Test successful positive feedback submission."""
    signal_id = uuid4()
    _mock_signal_ids.add(signal_id)  # Add signal to mock store

    submission = {
        "signal_id": str(signal_id),
        "feedback_type": "positive",
        "explanation": None,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    response = client.post("/api/v1/feedback", json=submission)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert "feedback_id" in data
    assert data["status"] == "received"
    assert "Thank you" in data["message"]


def test_submit_review_request_with_explanation_success():
    """Test review_request feedback with explanation."""
    signal_id = uuid4()
    _mock_signal_ids.add(signal_id)

    submission = {
        "signal_id": str(signal_id),
        "feedback_type": "review_request",
        "explanation": "I think the volume threshold is too strict",
        "timestamp": datetime.now(UTC).isoformat(),
    }

    response = client.post("/api/v1/feedback", json=submission)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["status"] == "queued_for_review"
    assert "review request" in data["message"].lower()


def test_submit_review_request_without_explanation_fails():
    """Test review_request feedback without explanation fails validation."""
    signal_id = uuid4()
    _mock_signal_ids.add(signal_id)

    submission = {
        "signal_id": str(signal_id),
        "feedback_type": "review_request",
        "explanation": None,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    response = client.post("/api/v1/feedback", json=submission)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_submit_feedback_signal_not_found():
    """Test feedback submission for non-existent signal."""
    signal_id = uuid4()
    # Do not add signal_id to _mock_signal_ids

    submission = {
        "signal_id": str(signal_id),
        "feedback_type": "positive",
        "explanation": None,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    response = client.post("/api/v1/feedback", json=submission)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()


def test_submit_question_feedback_success():
    """Test question feedback submission."""
    signal_id = uuid4()
    _mock_signal_ids.add(signal_id)

    submission = {
        "signal_id": str(signal_id),
        "feedback_type": "question",
        "explanation": "Why is the volume threshold 0.7x?",
        "timestamp": datetime.now(UTC).isoformat(),
    }

    response = client.post("/api/v1/feedback", json=submission)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert "feedback_id" in data
    assert "coming soon" in data["message"].lower()


def test_feedback_persisted_to_store():
    """Test feedback is persisted to store."""
    signal_id = uuid4()
    _mock_signal_ids.add(signal_id)

    submission = {
        "signal_id": str(signal_id),
        "feedback_type": "positive",
        "explanation": None,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    response = client.post("/api/v1/feedback", json=submission)
    assert response.status_code == status.HTTP_201_CREATED

    feedback_id = UUID(response.json()["feedback_id"])
    assert feedback_id in _feedback_store
    assert _feedback_store[feedback_id].signal_id == signal_id
    assert _feedback_store[feedback_id].feedback_type == "positive"


def test_invalid_feedback_type():
    """Test invalid feedback_type returns validation error."""
    signal_id = uuid4()
    _mock_signal_ids.add(signal_id)

    submission = {
        "signal_id": str(signal_id),
        "feedback_type": "invalid_type",  # Invalid type
        "explanation": None,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    response = client.post("/api/v1/feedback", json=submission)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_invalid_signal_id_format():
    """Test invalid signal_id format returns validation error."""
    submission = {
        "signal_id": "not-a-uuid",  # Invalid UUID format
        "feedback_type": "positive",
        "explanation": None,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    response = client.post("/api/v1/feedback", json=submission)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
