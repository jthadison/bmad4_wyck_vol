"""
Unit tests for YahooAdapter._format_symbol.

Tests Yahoo Finance symbol formatting across asset classes.
"""

from src.market_data.adapters.yahoo_adapter import YahooAdapter


class TestYahooFormatSymbol:
    """Tests for YahooAdapter._format_symbol."""

    def setup_method(self):
        self.adapter = YahooAdapter()

    def test_none_asset_class_returns_bare_symbol(self):
        """asset_class=None should return the symbol unchanged."""
        assert self.adapter._format_symbol("AAPL", None) == "AAPL"

    def test_stock_asset_class_returns_bare_symbol(self):
        """asset_class='stock' should return the symbol unchanged."""
        assert self.adapter._format_symbol("AAPL", "stock") == "AAPL"

    def test_forex_adds_equals_x_suffix(self):
        """Forex symbols get the =X suffix for Yahoo Finance."""
        assert self.adapter._format_symbol("EURUSD", "forex") == "EURUSD=X"

    def test_index_adds_caret_prefix(self):
        """Index symbols get the ^ prefix for Yahoo Finance."""
        assert self.adapter._format_symbol("DJI", "index") == "^DJI"

    def test_crypto_inserts_dash(self):
        """Crypto symbols are dash-separated (e.g. BTCUSD -> BTC-USD)."""
        assert self.adapter._format_symbol("BTCUSD", "crypto") == "BTC-USD"

    def test_crypto_with_existing_dash_unchanged(self):
        """A crypto symbol that already contains a dash should not be changed."""
        assert self.adapter._format_symbol("BTC-USD", "crypto") == "BTC-USD"

    def test_unknown_asset_class_returns_bare_symbol(self):
        """An unrecognised asset class should return the symbol unchanged."""
        assert self.adapter._format_symbol("FOO", "futures") == "FOO"

    def test_already_formatted_forex_no_double_suffix(self):
        """A symbol that already carries the =X suffix should not be doubled."""
        assert self.adapter._format_symbol("EURUSD=X", "forex") == "EURUSD=X"

    def test_already_formatted_index_no_double_prefix(self):
        """A symbol that already carries the ^ prefix should not be doubled."""
        assert self.adapter._format_symbol("^DJI", "index") == "^DJI"

    def test_crypto_exactly_three_chars_returns_unchanged(self):
        """A crypto symbol with exactly 3 characters cannot be split and is returned unchanged."""
        assert self.adapter._format_symbol("BTC", "crypto") == "BTC"

    def test_crypto_fewer_than_three_chars_returns_unchanged(self):
        """A crypto symbol shorter than 3 characters cannot be split and is returned unchanged."""
        assert self.adapter._format_symbol("AB", "crypto") == "AB"

    def test_empty_string_forex_appends_suffix(self):
        """An empty symbol with forex asset class still receives the =X suffix."""
        assert self.adapter._format_symbol("", "forex") == "=X"
