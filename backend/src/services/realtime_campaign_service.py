"""
Real-Time Campaign Detection Service (Story 16.2b)

Purpose:
--------
Provides real-time campaign detection on live market data streams.
Processes new bars, maintains bar buffers, detects patterns, and emits
campaign events within 2 seconds of bar close.

Business Context:
-----------------
Active traders need immediate notification when Wyckoff campaigns form.
This service bridges the gap between market data streams and campaign
detection, enabling sub-2-second pattern recognition for timely entries.

Integration:
------------
- Story 16.2a: Uses WebSocket client for live bar streams
- Story 15.6: Emits events via CampaignEvent system
- Pattern Engine: Detects Spring/SOS patterns in real-time
- Campaign Detector: Validates campaign formation

Author: Story 16.2b Implementation
"""

import asyncio
from collections import deque
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import structlog

from src.backtesting.campaign_detector import WyckoffCampaignDetector
from src.campaign_management.events import (
    CampaignCreatedEvent,
    CampaignUpdatedEvent,
    get_event_bus,
)
from src.models.ohlcv import OHLCVBar
from src.pattern_engine.detectors.sos_detector_orchestrator import SOSDetector
from src.pattern_engine.detectors.spring_detector import SpringDetector

logger = structlog.get_logger(__name__)


class BarBuffer:
    """
    Circular buffer for maintaining recent bars per symbol.

    Stores the most recent N bars for pattern detection, automatically
    evicting oldest bars when capacity is reached.

    Attributes:
        symbol: Trading symbol (e.g., "AAPL")
        capacity: Maximum number of bars to retain (default 50)
        bars: Deque of OHLCVBar objects
    """

    def __init__(self, symbol: str, capacity: int = 50):
        """
        Initialize bar buffer.

        Args:
            symbol: Trading symbol
            capacity: Maximum bars to store (default 50)
        """
        self.symbol = symbol
        self.capacity = capacity
        self.bars: deque[OHLCVBar] = deque(maxlen=capacity)
        self.logger = logger.bind(component="BarBuffer", symbol=symbol)

    def add_bar(self, bar: OHLCVBar) -> None:
        """
        Add new bar to buffer.

        Automatically removes oldest bar if at capacity.

        Args:
            bar: OHLCV bar to add
        """
        self.bars.append(bar)
        self.logger.debug(
            "Bar added to buffer",
            timestamp=bar.timestamp.isoformat(),
            buffer_size=len(self.bars),
        )

    def get_bars(self) -> list[OHLCVBar]:
        """
        Get all bars in buffer as list.

        Returns:
            List of OHLCV bars (oldest to newest)
        """
        return list(self.bars)

    def has_minimum_bars(self, min_bars: int = 20) -> bool:
        """
        Check if buffer has minimum bars for pattern detection.

        Args:
            min_bars: Minimum required bars (default 20)

        Returns:
            True if buffer has enough bars
        """
        return len(self.bars) >= min_bars


class RealtimeCampaignService:
    """
    Real-time campaign detection service.

    Processes live market data bars, detects patterns (Spring, SOS),
    validates campaign formation, and emits events for subscriber notification.

    Performance:
        - Pattern detection latency: < 2 seconds from bar close
        - Throughput: > 100 bars/second
        - Concurrent symbol processing supported

    Example:
        service = RealtimeCampaignService()
        await service.start()
        await service.process_bar(bar)  # Detects patterns, emits events
        await service.stop()
    """

    def __init__(
        self,
        buffer_capacity: int = 50,
        min_detection_bars: int = 20,
        max_symbols: int = 100,
    ):
        """
        Initialize real-time campaign service.

        Args:
            buffer_capacity: Maximum bars to retain per symbol (default 50, max 200)
            min_detection_bars: Minimum bars required for detection (default 20, min 10)
            max_symbols: Maximum number of symbols to track concurrently (default 100)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        # Validate parameters
        if buffer_capacity < 20 or buffer_capacity > 200:
            raise ValueError("buffer_capacity must be between 20 and 200")
        if min_detection_bars < 10 or min_detection_bars > buffer_capacity:
            raise ValueError("min_detection_bars must be between 10 and buffer_capacity")
        if max_symbols < 1 or max_symbols > 1000:
            raise ValueError("max_symbols must be between 1 and 1000")

        self.buffer_capacity = buffer_capacity
        self.min_detection_bars = min_detection_bars
        self.max_symbols = max_symbols

        # Bar buffers per symbol
        self.buffers: dict[str, BarBuffer] = {}

        # Symbol locks for concurrent processing safety
        self._symbol_locks: dict[str, asyncio.Lock] = {}

        # Pattern detectors
        self.spring_detector = SpringDetector()
        self.sos_detector = SOSDetector()

        # Campaign detector
        self.campaign_detector = WyckoffCampaignDetector()

        # Event bus for notifications
        self.event_bus = get_event_bus()

        # Active campaigns tracking (symbol -> campaign_id UUID)
        self.active_campaigns: dict[str, UUID] = {}

        # Campaign metadata (campaign_id -> symbol, pattern_count)
        self.campaign_metadata: dict[UUID, dict] = {}

        # Running state
        self._running = False

        self.logger = logger.bind(component="RealtimeCampaignService")

    async def start(self) -> None:
        """
        Start real-time campaign service.

        Initializes event bus and prepares for bar processing.
        """
        if self._running:
            self.logger.warning("Service already running")
            return

        self._running = True

        # Ensure event bus is started
        await self.event_bus.start()

        self.logger.info(
            "RealtimeCampaignService started",
            buffer_capacity=self.buffer_capacity,
            min_detection_bars=self.min_detection_bars,
            max_symbols=self.max_symbols,
        )

    async def stop(self) -> None:
        """
        Stop real-time campaign service.

        Clears buffers and stops event processing.
        """
        if not self._running:
            return

        self._running = False
        self.buffers.clear()
        self._symbol_locks.clear()
        self.active_campaigns.clear()
        self.campaign_metadata.clear()

        self.logger.info("RealtimeCampaignService stopped")

    def _get_symbol_lock(self, symbol: str) -> asyncio.Lock:
        """
        Get or create lock for symbol to prevent race conditions.

        Args:
            symbol: Trading symbol

        Returns:
            asyncio.Lock for the symbol
        """
        if symbol not in self._symbol_locks:
            self._symbol_locks[symbol] = asyncio.Lock()
        return self._symbol_locks[symbol]

    def _get_or_create_buffer(self, symbol: str) -> BarBuffer:
        """
        Get existing buffer or create new one for symbol.

        Args:
            symbol: Trading symbol

        Returns:
            BarBuffer for the symbol

        Raises:
            RuntimeError: If max_symbols limit reached
        """
        if symbol not in self.buffers:
            # Check symbol limit before creating new buffer
            if len(self.buffers) >= self.max_symbols:
                self.logger.error(
                    "Max symbols limit reached",
                    current_symbols=len(self.buffers),
                    max_symbols=self.max_symbols,
                    rejected_symbol=symbol,
                )
                raise RuntimeError(
                    f"Maximum symbol limit ({self.max_symbols}) reached. "
                    f"Cannot track symbol: {symbol}"
                )

            self.buffers[symbol] = BarBuffer(symbol, self.buffer_capacity)
            self.logger.info(
                "Buffer created for symbol",
                symbol=symbol,
                total_symbols=len(self.buffers),
                max_symbols=self.max_symbols,
            )
        return self.buffers[symbol]

    async def process_bar(self, bar: OHLCVBar) -> None:
        """
        Process new bar and detect patterns (Story 16.2b FR1, FR2).

        Adds bar to buffer, runs pattern detection, validates campaigns,
        and emits events if patterns detected.

        Args:
            bar: New OHLCV bar from market data stream

        Performance:
            - Target latency: < 2 seconds from bar close
            - Concurrent processing supported for multiple symbols

        Raises:
            RuntimeError: If max_symbols limit reached or service not running
        """
        # Check service state before processing
        if not self._running:
            self.logger.warning(
                "Bar processing skipped: service not running",
                symbol=bar.symbol,
                timestamp=bar.timestamp.isoformat(),
            )
            return

        start_time = datetime.now(UTC)
        patterns_detected = []

        # Acquire symbol lock to prevent race conditions on same-symbol concurrent processing
        async with self._get_symbol_lock(bar.symbol):
            try:
                # Add bar to buffer
                buffer = self._get_or_create_buffer(bar.symbol)
                buffer.add_bar(bar)

                # Check if we have enough bars for detection
                if not buffer.has_minimum_bars(self.min_detection_bars):
                    self.logger.debug(
                        "Insufficient bars for detection",
                        symbol=bar.symbol,
                        current_bars=len(buffer.bars),
                        required_bars=self.min_detection_bars,
                    )
                    return

                # Run pattern detection
                bars_list = buffer.get_bars()
                patterns_detected = await self._detect_patterns(bar.symbol, bars_list)

                # Process detected patterns
                if patterns_detected:
                    await self._process_detected_patterns(bar.symbol, patterns_detected, bars_list)

            except RuntimeError as e:
                # Max symbols limit reached - this is a service-level error
                self.logger.error(
                    "Bar processing failed: service limit reached",
                    symbol=bar.symbol,
                    error=str(e),
                    error_type="RuntimeError",
                )
                raise  # Re-raise to notify caller of limit condition

            except Exception as e:
                # Unexpected error during processing
                self.logger.error(
                    "Bar processing failed with unexpected error",
                    symbol=bar.symbol,
                    timestamp=bar.timestamp.isoformat(),
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,  # Include full stack trace
                )
                # Don't re-raise - allow service to continue processing other bars

            finally:
                # Always calculate and log processing metrics
                end_time = datetime.now(UTC)
                latency_ms = (end_time - start_time).total_seconds() * 1000

                self.logger.debug(
                    "Bar processed",
                    symbol=bar.symbol,
                    timestamp=bar.timestamp.isoformat(),
                    patterns_detected=len(patterns_detected),
                    latency_ms=f"{latency_ms:.2f}",
                )

    async def _detect_patterns(self, symbol: str, bars: list[OHLCVBar]) -> list[dict]:
        """
        Detect Spring and SOS patterns in bar list (Story 16.2b FR2).

        PLACEHOLDER: Full pattern detection requires context from Story 16.2a.
        Pattern detectors need TradingRange, WyckoffPhase, and volume analysis
        which will be provided by the WebSocket client integration.

        TODO (Story 16.2a Integration):
        - SpringDetector.detect(range: TradingRange, bars: list[OHLCVBar], phase: WyckoffPhase)
        - SOSDetector.detect(symbol: str, range: TradingRange, bars: list[OHLCVBar],
                           volume_analysis: dict, phase: WyckoffPhase, lps_detector: LPSDetector)

        Args:
            symbol: Trading symbol
            bars: List of OHLCV bars

        Returns:
            List of detected patterns with metadata (empty until Story 16.2a integration)
        """
        # Pattern detection deferred until Story 16.2a provides required context
        self.logger.debug(
            "Pattern detection deferred pending Story 16.2a integration",
            symbol=symbol,
            bars_available=len(bars),
        )
        return []

    async def _process_detected_patterns(
        self, symbol: str, patterns: list[dict], bars: list[OHLCVBar]
    ) -> None:
        """
        Process detected patterns and emit campaign events (Story 16.2b FR3).

        Validates campaign formation, tracks campaign state, and broadcasts
        events to subscribers.

        Args:
            symbol: Trading symbol
            patterns: List of detected patterns
            bars: OHLCV bar list
        """
        for pattern_info in patterns:
            pattern_type = pattern_info["pattern_type"]
            timestamp = pattern_info["timestamp"]

            # Check if this starts a new campaign or adds to existing
            campaign_id = self.active_campaigns.get(symbol)

            if campaign_id is None:
                # New campaign formed - create UUID and metadata
                campaign_id = uuid4()
                self.active_campaigns[symbol] = campaign_id

                # Initialize campaign metadata
                self.campaign_metadata[campaign_id] = {
                    "symbol": symbol,
                    "pattern_count": 1,
                    "initial_pattern": pattern_type,
                    "created_at": timestamp,
                }

                # Emit CampaignCreatedEvent using proper Pydantic model
                # TODO (Story 16.2a): Replace placeholder trading_range_id with actual TradingRange.id
                # from campaign detector when pattern detection is active
                event = CampaignCreatedEvent(
                    campaign_id=campaign_id,
                    symbol=symbol,
                    trading_range_id=uuid4(),  # Placeholder - will be set by campaign detector
                    initial_pattern_type=pattern_type,
                    campaign_id_str=f"{symbol}_{timestamp.strftime('%Y%m%d_%H%M%S')}",
                )

                await self.event_bus.publish(event)

                self.logger.info(
                    "New campaign formed",
                    symbol=symbol,
                    campaign_id=str(campaign_id),
                    pattern_type=pattern_type,
                )
            else:
                # Pattern added to existing campaign
                metadata = self.campaign_metadata[campaign_id]
                metadata["pattern_count"] += 1

                # Emit CampaignUpdatedEvent for pattern addition
                # TODO (Story 16.2a): Replace placeholder risk/pnl with actual campaign metrics
                # from risk manager and position tracker
                event = CampaignUpdatedEvent(
                    campaign_id=campaign_id,
                    status="ACCUMULATION" if pattern_type == "SPRING" else "MARKUP",
                    phase="PHASE_C" if pattern_type == "SPRING" else "PHASE_D",
                    total_risk=Decimal("0.02"),  # Placeholder
                    total_pnl=Decimal("0.00"),  # Placeholder
                    change_description=f"{pattern_type} pattern detected",
                )

                await self.event_bus.publish(event)

                # Check if campaign should be activated (Spring followed by SOS)
                if pattern_type == "SOS":
                    # TODO (Story 16.2a): Replace placeholder risk/pnl with actual campaign metrics
                    activation_event = CampaignUpdatedEvent(
                        campaign_id=campaign_id,
                        status="ACTIVE",
                        phase="PHASE_D",
                        total_risk=Decimal("0.02"),  # Placeholder
                        total_pnl=Decimal("0.00"),  # Placeholder
                        change_description="Campaign activated: SOS breakout detected",
                    )

                    await self.event_bus.publish(activation_event)

                    self.logger.info(
                        "Campaign activated",
                        symbol=symbol,
                        campaign_id=str(campaign_id),
                    )

    async def process_bar_batch(self, bars: list[OHLCVBar]) -> None:
        """
        Process multiple bars concurrently for high throughput.

        Args:
            bars: List of OHLCV bars to process

        Performance:
            - Target: > 100 bars/second throughput
            - Uses asyncio.gather for concurrent processing

        Note:
            Exceptions are captured per-bar and logged. The batch continues
            processing even if individual bars fail. If service is not running,
            all bars are skipped.
        """
        # Check service state before processing batch
        if not self._running:
            self.logger.warning(
                "Bar batch processing skipped: service not running",
                batch_size=len(bars),
            )
            return

        tasks = [self.process_bar(bar) for bar in bars]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successes and failures
        error_count = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_count += 1
                self.logger.error(
                    "Bar failed in batch processing",
                    symbol=bars[i].symbol,
                    timestamp=bars[i].timestamp.isoformat(),
                    error=str(result),
                    error_type=type(result).__name__,
                )

        self.logger.debug(
            "Bar batch processed",
            batch_size=len(bars),
            successful=len(bars) - error_count,
            failed=error_count,
        )
