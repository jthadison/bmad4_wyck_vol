"""
Unit tests for retry logic with exponential backoff.
"""

import asyncio
from datetime import datetime

import httpx
import pytest

from src.market_data.retry import (
    NonRetryableError,
    RetryableError,
    retry_with_backoff,
    with_retry,
)


@pytest.mark.asyncio
class TestRetryLogic:
    """Test suite for retry logic."""

    async def test_retry_with_backoff_success_first_try(self):
        """Test successful function call on first try."""
        # Arrange
        call_count = 0

        async def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        # Act
        result = await retry_with_backoff(
            successful_func,
            max_retries=3,
            delays=[1.0, 2.0, 4.0],
        )

        # Assert
        assert result == "success"
        assert call_count == 1

    async def test_retry_with_backoff_success_after_retries(self):
        """Test successful function call after retries."""
        # Arrange
        call_count = 0

        async def func_succeeds_on_third_try():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.HTTPError("Temporary error")
            return "success"

        # Act
        start_time = datetime.now()
        result = await retry_with_backoff(
            func_succeeds_on_third_try,
            max_retries=3,
            delays=[0.1, 0.2, 0.3],  # Short delays for testing
        )
        duration = (datetime.now() - start_time).total_seconds()

        # Assert
        assert result == "success"
        assert call_count == 3
        # Should have waited ~0.3s total (0.1s + 0.2s)
        assert duration >= 0.3

    async def test_retry_with_backoff_exhausted_retries(self):
        """Test that exception is raised after max retries."""
        # Arrange
        call_count = 0

        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise httpx.HTTPError("Permanent error")

        # Act & Assert
        with pytest.raises(httpx.HTTPError, match="Permanent error"):
            await retry_with_backoff(
                always_fails,
                max_retries=3,
                delays=[0.1, 0.1, 0.1],
            )

        # Should have tried 3 times
        assert call_count == 3

    async def test_retry_with_backoff_custom_delays(self):
        """Test exponential backoff with custom delays."""
        # Arrange
        call_count = 0
        retry_times = []

        async def failing_func():
            nonlocal call_count
            retry_times.append(datetime.now())
            call_count += 1
            raise httpx.HTTPError("Error")

        # Act & Assert
        try:
            await retry_with_backoff(
                failing_func,
                max_retries=3,
                delays=[0.1, 0.2, 0.4],  # Exponential: 1s, 2s, 4s scaled down
            )
        except httpx.HTTPError:
            pass

        # Verify delays between attempts
        assert len(retry_times) == 3
        if len(retry_times) >= 2:
            delay1 = (retry_times[1] - retry_times[0]).total_seconds()
            assert delay1 >= 0.1, f"First delay too short: {delay1}"
        if len(retry_times) >= 3:
            delay2 = (retry_times[2] - retry_times[1]).total_seconds()
            assert delay2 >= 0.2, f"Second delay too short: {delay2}"

    async def test_retry_with_backoff_custom_exceptions(self):
        """Test retry with custom exception types."""
        # Arrange
        call_count = 0

        async def func_raises_custom_exception():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RetryableError("Retryable")
            return "success"

        # Act
        result = await retry_with_backoff(
            func_raises_custom_exception,
            max_retries=3,
            delays=[0.1, 0.1, 0.1],
            exceptions=(RetryableError,),
        )

        # Assert
        assert result == "success"
        assert call_count == 2

    async def test_with_retry_decorator_success(self):
        """Test @with_retry decorator with successful function."""
        # Arrange
        call_count = 0

        @with_retry(max_retries=3, delays=[0.1, 0.1, 0.1])
        async def decorated_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.HTTPError("Retry once")
            return "success"

        # Act
        result = await decorated_func()

        # Assert
        assert result == "success"
        assert call_count == 2

    async def test_with_retry_decorator_exhausted(self):
        """Test @with_retry decorator with exhausted retries."""
        # Arrange
        call_count = 0

        @with_retry(max_retries=2, delays=[0.05, 0.05])
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise httpx.TimeoutException("Timeout")

        # Act & Assert
        with pytest.raises(httpx.TimeoutException):
            await always_fails()

        assert call_count == 2

    async def test_retry_with_network_error(self):
        """Test retry with network errors."""
        # Arrange
        call_count = 0

        async def network_error_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.NetworkError("Connection failed")
            return "recovered"

        # Act
        result = await retry_with_backoff(
            network_error_func,
            max_retries=3,
            delays=[0.05, 0.1, 0.15],
        )

        # Assert
        assert result == "recovered"
        assert call_count == 3

    async def test_retry_preserves_function_name(self):
        """Test that decorator preserves function metadata."""
        # Arrange
        @with_retry(max_retries=3)
        async def my_function():
            """My docstring."""
            return "test"

        # Act & Assert
        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."

    async def test_non_retryable_error_not_retried(self):
        """Test that NonRetryableError is not retried."""
        # Arrange
        call_count = 0

        async def func_raises_non_retryable():
            nonlocal call_count
            call_count += 1
            raise NonRetryableError("Don't retry")

        # Act & Assert
        # Since NonRetryableError is not in default exceptions, it should not be caught
        with pytest.raises(NonRetryableError):
            await retry_with_backoff(
                func_raises_non_retryable,
                max_retries=3,
                delays=[0.1, 0.1, 0.1],
            )

        # Should only try once
        assert call_count == 1

    async def test_retry_with_args_and_kwargs(self):
        """Test retry with function arguments."""
        # Arrange
        call_count = 0

        async def func_with_params(x, y, z=0):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.HTTPError("Retry")
            return x + y + z

        # Act
        result = await retry_with_backoff(
            func_with_params,
            max_retries=3,
            delays=[0.05, 0.05, 0.05],
            x=10,
            y=20,
            z=5,
        )

        # Assert
        assert result == 35
        assert call_count == 2
