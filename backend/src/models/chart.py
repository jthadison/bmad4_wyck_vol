"""Chart data models for Lightweight Charts integration.

Story 11.5: Advanced Charting Integration
Provides Pydantic models for chart data API endpoint.
"""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer


class ChartBar(BaseModel):
    """Single OHLCV bar for chart display.

    Time format: Unix timestamp in seconds (Lightweight Charts requirement).
    Prices as floats: Acceptable for display purposes (not financial calculations).
    """

    time: int  # Unix timestamp in seconds
    open: float
    high: float
    low: float
    close: float
    volume: int


class PatternMarker(BaseModel):
    """Pattern detection marker for chart overlay.

    Renders as marker icon with tooltip showing confidence and entry price.
    """

    id: UUID
    pattern_type: Literal["SPRING", "UTAD", "SOS", "LPS", "TEST"]
    time: int  # Unix timestamp in seconds
    price: float  # Price where marker appears
    position: Literal["belowBar", "aboveBar"]  # Lightweight Charts position
    confidence_score: int  # 70-95%
    label_text: str  # e.g., "Spring (85%)"
    icon: str  # Unicode emoji: ⬆️, ⬇️, 🚀, 📍, ✓
    color: str  # Hex color code
    shape: Literal["circle", "square", "arrowUp", "arrowDown"]  # Lightweight Charts shape
    entry_price: float  # For tooltip
    stop_loss: float  # For tooltip
    phase: str  # Wyckoff phase


class LevelLine(BaseModel):
    """Trading range level line (Creek, Ice, Jump).

    Renders as horizontal price line with label.
    """

    level_type: Literal["CREEK", "ICE", "JUMP"]
    price: float
    label: str  # e.g., "Creek: $152.35"
    color: str  # Hex color code
    line_style: Literal["SOLID", "DASHED"]
    line_width: int = 2


class PhaseAnnotation(BaseModel):
    """Wyckoff phase background shading.

    Renders as semi-transparent background rectangle.
    """

    phase: Literal["A", "B", "C", "D", "E"]
    start_time: int  # Unix timestamp in seconds
    end_time: int  # Unix timestamp in seconds
    background_color: str  # Hex color with alpha: #9CA3AF20
    label: str  # e.g., "Phase C"


class TradingRangeLevels(BaseModel):
    """Active trading range levels for chart.

    Provides Creek/Ice/Jump levels for current trading range.
    """

    trading_range_id: UUID
    symbol: str
    creek_level: float  # Support
    ice_level: float  # Resistance
    jump_target: float  # Projected target
    range_status: Literal["ACTIVE", "COMPLETED"]


class PreliminaryEvent(BaseModel):
    """Preliminary Wyckoff events (PS, SC, AR, ST).

    Story 11.5 AC 13: Mark early events before Spring patterns.
    """

    event_type: Literal["PS", "SC", "AR", "ST"]
    time: int  # Unix timestamp in seconds
    price: float
    label: str  # e.g., "Selling Climax"
    description: str  # Tooltip text
    color: str  # Hex color
    shape: Literal["circle", "square", "triangle"]


class WyckoffSchematic(BaseModel):
    """Wyckoff schematic matching data.

    Story 11.5 AC 11: Display which schematic (#1 or #2) pattern matches.
    """

    schematic_type: Literal["ACCUMULATION_1", "ACCUMULATION_2", "DISTRIBUTION_1", "DISTRIBUTION_2"]
    confidence_score: int  # 0-100%
    template_data: list[dict[str, float]]  # Ideal price action points


class CauseBuildingData(BaseModel):
    """Point & Figure cause-building visualization data.

    Story 11.5 AC 12: Show P&F count and projected Jump target.
    """

    column_count: int  # Current accumulation columns
    target_column_count: int  # Required columns for full cause
    projected_jump: float  # Calculated Jump target
    progress_percentage: float  # Completion percentage
    count_methodology: str  # Description of calculation


class ChartDataRequest(BaseModel):
    """Query parameters for chart data endpoint."""

    symbol: str = Field(..., max_length=20)
    timeframe: Literal["1D", "1W", "1M"] = "1D"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = Field(500, ge=50, le=2000)  # Performance constraint


class ChartDataResponse(BaseModel):
    """Complete chart data payload for Lightweight Charts.

    Story 11.5: Provides all data needed for charting component.
    Includes OHLCV bars, pattern markers, level lines, phase annotations,
    and Wyckoff enhancements (schematics, cause-building, preliminary events).
    """

    symbol: str
    timeframe: str
    bars: list[ChartBar]
    patterns: list[PatternMarker]
    level_lines: list[LevelLine]
    phase_annotations: list[PhaseAnnotation]
    trading_ranges: list[TradingRangeLevels]
    preliminary_events: list[PreliminaryEvent]  # AC 13
    schematic_match: Optional[WyckoffSchematic]  # AC 11, 14
    cause_building: Optional[CauseBuildingData]  # AC 12
    bar_count: int
    date_range: dict[str, str]  # {"start": "2024-01-01", "end": "2024-03-13"}

    @field_serializer("date_range")
    def serialize_date_range(self, date_range: dict[str, str]) -> dict[str, str]:
        """Ensure date range is serialized correctly."""
        return date_range


# Pattern type to chart marker mappings
PATTERN_MARKER_CONFIG = {
    "SPRING": {
        "icon": "⬆️",
        "color": "#16A34A",  # Green
        "position": "belowBar",
        "shape": "arrowUp",
    },
    "UTAD": {
        "icon": "⬇️",
        "color": "#DC2626",  # Red
        "position": "aboveBar",
        "shape": "arrowDown",
    },
    "SOS": {
        "icon": "🚀",
        "color": "#2563EB",  # Blue
        "position": "belowBar",
        "shape": "circle",
    },
    "LPS": {
        "icon": "📍",
        "color": "#9333EA",  # Purple
        "position": "belowBar",
        "shape": "circle",
    },
    "TEST": {
        "icon": "✓",
        "color": "#6B7280",  # Gray
        "position": "aboveBar",
        "shape": "square",
    },
}

# Level line color mappings
LEVEL_LINE_CONFIG = {
    "CREEK": {
        "color": "#DC2626",  # Red
        "label_prefix": "Creek",
    },
    "ICE": {
        "color": "#2563EB",  # Blue
        "label_prefix": "Ice",
    },
    "JUMP": {
        "color": "#16A34A",  # Green
        "label_prefix": "Jump",
    },
}

# Phase background color mappings
PHASE_COLOR_CONFIG = {
    "A": "#9CA3AF20",  # Gray, 12% opacity
    "B": "#3B82F620",  # Blue, 12% opacity
    "C": "#FCD34D20",  # Yellow, 12% opacity
    "D": "#FB923C20",  # Orange, 12% opacity
    "E": "#34D39920",  # Green, 12% opacity
}

# Preliminary event configurations
PRELIMINARY_EVENT_CONFIG = {
    "PS": {
        "label": "Preliminary Support",
        "description": "Initial buying support - first sign of demand",
        "color": "#2563EB",  # Blue
        "shape": "circle",
    },
    "SC": {
        "label": "Selling Climax",
        "description": "Panic selling exhaustion - heavy volume sell-off",
        "color": "#DC2626",  # Red
        "shape": "triangle",
    },
    "AR": {
        "label": "Automatic Rally",
        "description": "Relief rally after selling climax",
        "color": "#16A34A",  # Green
        "shape": "circle",
    },
    "ST": {
        "label": "Secondary Test",
        "description": "Retest of selling climax low",
        "color": "#9333EA",  # Purple
        "shape": "square",
    },
}

# Wyckoff Schematic Template Data
# Story 11.5.1 Task 1: Template coordinates for schematic matching
# Format: List of {x_percent, y_percent} normalized to 0-100%
# X-axis: Timeline percentage through trading range
# Y-axis: Price level (0% = Creek, 100% = Ice)

ACCUMULATION_SCHEMATIC_1_TEMPLATE = [
    # PS - Preliminary Support (10% into timeline, 20% above Creek)
    {"x_percent": 10.0, "y_percent": 20.0},
    # SC - Selling Climax (20% into timeline, 5% above Creek - lowest point)
    {"x_percent": 20.0, "y_percent": 5.0},
    # AR - Automatic Rally (30% into timeline, 60% to Ice)
    {"x_percent": 30.0, "y_percent": 60.0},
    # ST - Secondary Test (45% into timeline, 15% above Creek)
    {"x_percent": 45.0, "y_percent": 15.0},
    # Spring - Shakeout below Creek (60% into timeline, -5% below Creek)
    {"x_percent": 60.0, "y_percent": -5.0},
    # Test after Spring (70% into timeline, 25% above Creek)
    {"x_percent": 70.0, "y_percent": 25.0},
    # SOS - Sign of Strength (85% into timeline, 90% to Ice - breakout)
    {"x_percent": 85.0, "y_percent": 90.0},
    # Backup/LPS (95% into timeline, 55% - pullback)
    {"x_percent": 95.0, "y_percent": 55.0},
]

ACCUMULATION_SCHEMATIC_2_TEMPLATE = [
    # PS - Preliminary Support
    {"x_percent": 10.0, "y_percent": 25.0},
    # SC - Selling Climax
    {"x_percent": 20.0, "y_percent": 8.0},
    # AR - Automatic Rally
    {"x_percent": 30.0, "y_percent": 65.0},
    # ST - Secondary Test
    {"x_percent": 45.0, "y_percent": 20.0},
    # LPS - Last Point of Support (no Spring, stays above Creek)
    {"x_percent": 65.0, "y_percent": 30.0},
    # SOS - Sign of Strength
    {"x_percent": 85.0, "y_percent": 92.0},
    # Backup
    {"x_percent": 95.0, "y_percent": 60.0},
]

DISTRIBUTION_SCHEMATIC_1_TEMPLATE = [
    # PSY - Preliminary Supply (10% into timeline, 75% to Ice)
    {"x_percent": 10.0, "y_percent": 75.0},
    # BC - Buying Climax (20% into timeline, 95% - highest point)
    {"x_percent": 20.0, "y_percent": 95.0},
    # AR - Automatic Reaction (30% into timeline, 40% drop)
    {"x_percent": 30.0, "y_percent": 40.0},
    # ST - Secondary Test (45% into timeline, 85% retest high)
    {"x_percent": 45.0, "y_percent": 85.0},
    # UTAD - Upthrust After Distribution (60% into timeline, 105% above Ice)
    {"x_percent": 60.0, "y_percent": 105.0},
    # Test after UTAD (70% into timeline, 70%)
    {"x_percent": 70.0, "y_percent": 70.0},
    # SOW - Sign of Weakness (85% into timeline, 10% - breakdown)
    {"x_percent": 85.0, "y_percent": 10.0},
    # LPSY (95% into timeline, 45% rally attempt)
    {"x_percent": 95.0, "y_percent": 45.0},
]

DISTRIBUTION_SCHEMATIC_2_TEMPLATE = [
    # PSY - Preliminary Supply
    {"x_percent": 10.0, "y_percent": 70.0},
    # BC - Buying Climax
    {"x_percent": 20.0, "y_percent": 92.0},
    # AR - Automatic Reaction
    {"x_percent": 30.0, "y_percent": 35.0},
    # ST - Secondary Test
    {"x_percent": 45.0, "y_percent": 80.0},
    # LPSY - Last Point of Supply (no UTAD, stays below Ice)
    {"x_percent": 65.0, "y_percent": 70.0},
    # SOW - Sign of Weakness
    {"x_percent": 85.0, "y_percent": 12.0},
    # Rally attempt
    {"x_percent": 95.0, "y_percent": 40.0},
]

SCHEMATIC_TEMPLATES = {
    "ACCUMULATION_1": ACCUMULATION_SCHEMATIC_1_TEMPLATE,
    "ACCUMULATION_2": ACCUMULATION_SCHEMATIC_2_TEMPLATE,
    "DISTRIBUTION_1": DISTRIBUTION_SCHEMATIC_1_TEMPLATE,
    "DISTRIBUTION_2": DISTRIBUTION_SCHEMATIC_2_TEMPLATE,
}
