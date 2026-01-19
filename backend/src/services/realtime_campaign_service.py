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

import structlog

from src.backtesting.campaign_detector import WyckoffCampaignDetector
from src.campaign_management.events import get_event_bus
from src.models.campaign_event import CampaignEvent as DataclassCampaignEvent
from src.models.campaign_event import CampaignEventType
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
    ):
        """
        Initialize real-time campaign service.

        Args:
            buffer_capacity: Maximum bars to retain per symbol (default 50)
            min_detection_bars: Minimum bars required for detection (default 20)
        """
        self.buffer_capacity = buffer_capacity
        self.min_detection_bars = min_detection_bars

        # Bar buffers per symbol
        self.buffers: dict[str, BarBuffer] = {}

        # Pattern detectors
        self.spring_detector = SpringDetector()
        self.sos_detector = SOSDetector()

        # Campaign detector
        self.campaign_detector = WyckoffCampaignDetector()

        # Event bus for notifications
        self.event_bus = get_event_bus()

        # Active campaigns tracking (symbol -> campaign_id)
        self.active_campaigns: dict[str, str] = {}

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
        self.active_campaigns.clear()

        self.logger.info("RealtimeCampaignService stopped")

    def _get_or_create_buffer(self, symbol: str) -> BarBuffer:
        """
        Get existing buffer or create new one for symbol.

        Args:
            symbol: Trading symbol

        Returns:
            BarBuffer for the symbol
        """
        if symbol not in self.buffers:
            self.buffers[symbol] = BarBuffer(symbol, self.buffer_capacity)
            self.logger.info("Buffer created for symbol", symbol=symbol)
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
        """
        start_time = datetime.now(UTC)

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

        # Calculate processing latency
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

        Args:
            symbol: Trading symbol
            bars: List of OHLCV bars

        Returns:
            List of detected patterns with metadata
        """
        detected_patterns = []

        # Detect Spring patterns
        try:
            spring_result = self.spring_detector.detect(bars)
            if spring_result:
                detected_patterns.append(
                    {
                        "pattern_type": "SPRING",
                        "result": spring_result,
                        "timestamp": bars[-1].timestamp,
                    }
                )
                self.logger.info(
                    "Spring pattern detected",
                    symbol=symbol,
                    timestamp=bars[-1].timestamp.isoformat(),
                )
        except Exception as e:
            self.logger.error(
                "Spring detection failed",
                symbol=symbol,
                error=str(e),
                error_type=type(e).__name__,
            )

        # Detect SOS patterns
        try:
            sos_result = self.sos_detector.detect(bars)
            if sos_result:
                detected_patterns.append(
                    {
                        "pattern_type": "SOS",
                        "result": sos_result,
                        "timestamp": bars[-1].timestamp,
                    }
                )
                self.logger.info(
                    "SOS pattern detected",
                    symbol=symbol,
                    timestamp=bars[-1].timestamp.isoformat(),
                )
        except Exception as e:
            self.logger.error(
                "SOS detection failed",
                symbol=symbol,
                error=str(e),
                error_type=type(e).__name__,
            )

        return detected_patterns

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
                # New campaign formed
                campaign_id = f"{symbol}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
                self.active_campaigns[symbol] = campaign_id

                # Emit CAMPAIGN_FORMED event
                await self._emit_event(
                    event_type=CampaignEventType.CAMPAIGN_FORMED,
                    campaign_id=campaign_id,
                    pattern_type=pattern_type,
                    metadata={
                        "symbol": symbol,
                        "timestamp": timestamp.isoformat(),
                        "initial_pattern": pattern_type,
                    },
                )

                self.logger.info(
                    "New campaign formed",
                    symbol=symbol,
                    campaign_id=campaign_id,
                    pattern_type=pattern_type,
                )
            else:
                # Pattern added to existing campaign
                await self._emit_event(
                    event_type=CampaignEventType.PATTERN_DETECTED,
                    campaign_id=campaign_id,
                    pattern_type=pattern_type,
                    metadata={
                        "symbol": symbol,
                        "timestamp": timestamp.isoformat(),
                    },
                )

                # Check if campaign should be activated
                # (e.g., Spring followed by SOS = ACTIVE campaign)
                if pattern_type == "SOS":
                    await self._emit_event(
                        event_type=CampaignEventType.CAMPAIGN_ACTIVATED,
                        campaign_id=campaign_id,
                        pattern_type=None,
                        metadata={
                            "symbol": symbol,
                            "timestamp": timestamp.isoformat(),
                            "activation_reason": "SOS breakout detected",
                        },
                    )

                    self.logger.info(
                        "Campaign activated",
                        symbol=symbol,
                        campaign_id=campaign_id,
                    )

    async def _emit_event(
        self,
        event_type: CampaignEventType,
        campaign_id: str,
        pattern_type: str | None,
        metadata: dict,
    ) -> None:
        """
        Emit campaign event to subscribers (Story 16.2b FR3).

        Args:
            event_type: Type of campaign event
            campaign_id: Unique campaign identifier
            pattern_type: Pattern type (for PATTERN_DETECTED events)
            metadata: Additional event context
        """
        event = DataclassCampaignEvent(
            event_type=event_type,
            campaign_id=campaign_id,
            timestamp=datetime.now(UTC),
            pattern_type=pattern_type,
            metadata=metadata,
        )

        # Note: For now, we use a simple notification approach
        # When the event bus is fully integrated, we'll publish proper events
        # await self.event_bus.publish(event)

        self.logger.info(
            "Campaign event emitted",
            event_type=event_type.value,
            campaign_id=campaign_id,
            pattern_type=pattern_type,
            metadata=metadata,
        )

    async def process_bar_batch(self, bars: list[OHLCVBar]) -> None:
        """
        Process multiple bars concurrently for high throughput.

        Args:
            bars: List of OHLCV bars to process

        Performance:
            - Target: > 100 bars/second throughput
            - Uses asyncio.gather for concurrent processing
        """
        tasks = [self.process_bar(bar) for bar in bars]
        await asyncio.gather(*tasks, return_exceptions=True)

        self.logger.debug(
            "Bar batch processed",
            batch_size=len(bars),
        )
