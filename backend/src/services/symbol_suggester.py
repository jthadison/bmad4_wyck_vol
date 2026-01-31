"""
Symbol Suggester Service (Story 21.3)

Provides symbol suggestions for typo corrections using string similarity.
Uses difflib's SequenceMatcher for similarity scoring.

Features:
- Finds similar symbols from static lists
- Returns top N suggestions sorted by similarity score
- Supports all asset classes (forex, index, crypto, stock)
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import TYPE_CHECKING

import structlog

from src.data.static_symbols import get_static_symbols

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)

# Minimum similarity threshold to include in suggestions
MIN_SIMILARITY_THRESHOLD = 0.4

# Default maximum number of suggestions to return
DEFAULT_MAX_SUGGESTIONS = 3


class SymbolSuggester:
    """
    Service for suggesting similar symbols when validation fails.

    Uses string similarity algorithms to find potential matches
    from static symbol lists.
    """

    def __init__(self, min_similarity: float = MIN_SIMILARITY_THRESHOLD):
        """
        Initialize Symbol Suggester.

        Args:
            min_similarity: Minimum similarity score (0-1) to include in suggestions
        """
        self._min_similarity = min_similarity
        logger.info(
            "symbol_suggester_initialized",
            min_similarity=min_similarity,
        )

    def get_suggestions(
        self,
        symbol: str,
        asset_class: str,
        max_suggestions: int = DEFAULT_MAX_SUGGESTIONS,
    ) -> list[str]:
        """
        Get similar symbols sorted by similarity score.

        Args:
            symbol: Symbol that failed validation (e.g., "EURSUD")
            asset_class: Asset class to search (forex, index, crypto, stock)
            max_suggestions: Maximum number of suggestions to return

        Returns:
            List of similar symbols sorted by similarity (highest first)
        """
        symbol_upper = symbol.upper().strip()
        asset_class_lower = asset_class.lower().strip()

        # Get known symbols for this asset class
        known_symbols = self._get_known_symbols(asset_class_lower)

        if not known_symbols:
            logger.debug(
                "no_known_symbols_for_asset_class",
                asset_class=asset_class_lower,
            )
            return []

        # Calculate similarity scores
        scored: list[tuple[float, str]] = []
        for known in known_symbols:
            # Normalize for comparison (remove slashes)
            known_normalized = known.replace("/", "")
            symbol_normalized = symbol_upper.replace("/", "")

            score = SequenceMatcher(None, symbol_normalized, known_normalized).ratio()

            if score >= self._min_similarity:
                scored.append((score, known))

        # Sort by score descending, take top N
        scored.sort(key=lambda x: x[0], reverse=True)
        suggestions = [s[1] for s in scored[:max_suggestions]]

        logger.debug(
            "symbol_suggestions_generated",
            input_symbol=symbol_upper,
            asset_class=asset_class_lower,
            suggestions=suggestions,
            total_matches=len(scored),
        )

        return suggestions

    def _get_known_symbols(self, asset_class: str) -> list[str]:
        """
        Get all known symbols from static lists for an asset class.

        Args:
            asset_class: Asset class (forex, index, crypto, stock)

        Returns:
            List of symbol strings
        """
        symbols = get_static_symbols(asset_class)
        return [s["symbol"] for s in symbols]
