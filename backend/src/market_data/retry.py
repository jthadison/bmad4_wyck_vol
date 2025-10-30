"""
Retry logic with exponential backoff.

This module provides retry decorators and utilities for handling transient
failures in API calls and database operations.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import wraps
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    delays: list[float] | None = None,
    exceptions: tuple[type[Exception], ...] | None = None,
    **kwargs: Any,
) -> Any:
    """
    Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts (default: 3)
        delays: List of delay durations in seconds (default: [1.0, 2.0, 4.0])
        exceptions: Tuple of exception types to catch (default: httpx errors)
        **kwargs: Arguments to pass to the function

    Returns:
        Result of the function call

    Raises:
        Exception: Re-raises the last exception after all retries exhausted

    Example:
        ```python
        result = await retry_with_backoff(
            fetch_data,
            symbol="AAPL",
            max_retries=3,
            delays=[1.0, 2.0, 4.0]
        )
        ```
    """
    if delays is None:
        delays = [1.0, 2.0, 4.0]

    if exceptions is None:
        # Default: retry on HTTP errors
        exceptions = (httpx.HTTPError, httpx.TimeoutException, httpx.NetworkError)

    func_name = func.__name__ if hasattr(func, "__name__") else str(func)

    for attempt in range(max_retries):
        try:
            # Try to execute the function
            if asyncio.iscoroutinefunction(func):
                return await func(**kwargs)
            else:
                return func(**kwargs)

        except exceptions as e:
            # Check if this is the last attempt
            if attempt == max_retries - 1:
                logger.error(
                    "retry_exhausted",
                    function=func_name,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    error=str(e),
                )
                raise

            # Calculate delay for this attempt
            delay = delays[attempt] if attempt < len(delays) else delays[-1]

            logger.warning(
                "retry_attempt",
                function=func_name,
                attempt=attempt + 1,
                max_retries=max_retries,
                delay=delay,
                error=str(e),
                message=f"Retry {attempt + 1}/{max_retries} for {func_name} after {delay}s delay",
            )

            # Wait before retrying
            await asyncio.sleep(delay)

    # Should never reach here, but satisfy type checker
    raise RuntimeError("Retry logic error: exhausted retries without raising")


def with_retry(
    max_retries: int = 3,
    delays: list[float] | None = None,
    exceptions: tuple[type[Exception], ...] | None = None,
):
    """
    Decorator to add retry logic to async functions.

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        delays: List of delay durations in seconds (default: [1.0, 2.0, 4.0])
        exceptions: Tuple of exception types to catch (default: httpx errors)

    Returns:
        Decorated function with retry logic

    Example:
        ```python
        @with_retry(max_retries=3, delays=[1.0, 2.0, 4.0])
        async def fetch_data(symbol: str) -> List[OHLCVBar]:
            # ... fetch logic ...
            pass
        ```
    """
    if delays is None:
        delays = [1.0, 2.0, 4.0]

    if exceptions is None:
        exceptions = (httpx.HTTPError, httpx.TimeoutException, httpx.NetworkError)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            func_name = func.__name__

            for attempt in range(max_retries):
                try:
                    # Try to execute the function
                    return await func(*args, **kwargs)

                except exceptions as e:
                    # Check if this is the last attempt
                    if attempt == max_retries - 1:
                        logger.error(
                            "retry_exhausted",
                            function=func_name,
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            error=str(e),
                        )
                        raise

                    # Calculate delay for this attempt
                    delay = delays[attempt] if attempt < len(delays) else delays[-1]

                    logger.warning(
                        "retry_attempt",
                        function=func_name,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay=delay,
                        error=str(e),
                        message=f"Retry {attempt + 1}/{max_retries} for {func_name} after {delay}s delay",
                    )

                    # Wait before retrying
                    await asyncio.sleep(delay)

            # Should never reach here
            raise RuntimeError("Retry logic error: exhausted retries without raising")

        return wrapper

    return decorator


class RetryableError(Exception):
    """Exception that should trigger a retry."""

    pass


class NonRetryableError(Exception):
    """Exception that should NOT trigger a retry (e.g., auth failure)."""

    pass
