"""
Campaign ID Generation Utility (Story 18.5)

Provides centralized campaign ID generation and parsing functions.
Extracted from duplicate implementations in campaign_manager.py and service.py.

Campaign ID Format:
    {SYMBOL}-{DATE}
    Example: "AAPL-2024-10-15"

The format creates human-readable, unique identifiers that:
- Are sortable chronologically
- Can be parsed back to components
- Link campaigns to their originating trading ranges
"""

from datetime import datetime


def generate_campaign_id(
    symbol: str,
    range_start_date: str | datetime,
) -> str:
    """
    Generate human-readable campaign identifier.

    Format: {SYMBOL}-{YYYY-MM-DD}
    Example: "AAPL-2024-10-15"

    Args:
        symbol: Trading symbol (e.g., "AAPL", "EURUSD")
        range_start_date: Either:
            - A string in "YYYY-MM-DD" format
            - A datetime object (will be formatted to "YYYY-MM-DD")

    Returns:
        Campaign ID string in format "{SYMBOL}-{YYYY-MM-DD}"

    Examples:
        >>> generate_campaign_id("AAPL", "2024-10-15")
        'AAPL-2024-10-15'

        >>> from datetime import datetime
        >>> generate_campaign_id("EURUSD", datetime(2024, 10, 15))
        'EURUSD-2024-10-15'
    """
    if isinstance(range_start_date, datetime):
        date_str = range_start_date.strftime("%Y-%m-%d")
    else:
        date_str = range_start_date

    return f"{symbol}-{date_str}"


def parse_campaign_id(campaign_id: str) -> dict[str, str]:
    """
    Parse campaign ID into its components.

    Args:
        campaign_id: Campaign ID string (e.g., "AAPL-2024-10-15")

    Returns:
        Dictionary with:
            - symbol: The trading symbol
            - date: The date string (YYYY-MM-DD)

    Raises:
        ValueError: If campaign_id format is invalid

    Examples:
        >>> parse_campaign_id("AAPL-2024-10-15")
        {'symbol': 'AAPL', 'date': '2024-10-15'}

        >>> parse_campaign_id("EURUSD-2024-10-15")
        {'symbol': 'EURUSD', 'date': '2024-10-15'}
    """
    # Split from the right to handle symbols with hyphens (though uncommon)
    # Format is SYMBOL-YYYY-MM-DD, so we need the last 3 parts for date
    parts = campaign_id.rsplit("-", 3)

    if len(parts) != 4:
        raise ValueError(
            f"Invalid campaign ID format: '{campaign_id}'. " f"Expected format: SYMBOL-YYYY-MM-DD"
        )

    symbol = parts[0]
    date = f"{parts[1]}-{parts[2]}-{parts[3]}"

    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(
            f"Invalid date in campaign ID: '{campaign_id}'. " f"Date '{date}' is not valid: {e}"
        ) from e

    return {
        "symbol": symbol,
        "date": date,
    }
