"""Chart data models for Lightweight Charts integration.

Story 11.5: Advanced Charting Integration
Provides Pydantic models for chart data API endpoint.
"""

from decimal import Decimal
from datetime import datetime
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, field_serializer
from uuid import UUID


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
    schematic_type: Literal[
        "ACCUMULATION_1",
        "ACCUMULATION_2",
        "DISTRIBUTION_1",
        "DISTRIBUTION_2"
    ]
    confidence_score: int  # 0-100%
    template_data: List[Dict[str, float]]  # Ideal price action points


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
    bars: List[ChartBar]
    patterns: List[PatternMarker]
    level_lines: List[LevelLine]
    phase_annotations: List[PhaseAnnotation]
    trading_ranges: List[TradingRangeLevels]
    preliminary_events: List[PreliminaryEvent]  # AC 13
    schematic_match: Optional[WyckoffSchematic]  # AC 11, 14
    cause_building: Optional[CauseBuildingData]  # AC 12
    bar_count: int
    date_range: Dict[str, str]  # {"start": "2024-01-01", "end": "2024-03-13"}

    @field_serializer('date_range')
    def serialize_date_range(self, date_range: Dict[str, str]) -> Dict[str, str]:
        """Ensure date range is serialized correctly."""
        return date_range


# Pattern type to chart marker mappings
PATTERN_MARKER_CONFIG = {
    "SPRING": {
        "icon": "⬆️",
        "color": "#16A34A",  # Green
        "position": "belowBar",
        "shape": "arrowUp"
    },
    "UTAD": {
        "icon": "⬇️",
        "color": "#DC2626",  # Red
        "position": "aboveBar",
        "shape": "arrowDown"
    },
    "SOS": {
        "icon": "🚀",
        "color": "#2563EB",  # Blue
        "position": "belowBar",
        "shape": "circle"
    },
    "LPS": {
        "icon": "📍",
        "color": "#9333EA",  # Purple
        "position": "belowBar",
        "shape": "circle"
    },
    "TEST": {
        "icon": "✓",
        "color": "#6B7280",  # Gray
        "position": "aboveBar",
        "shape": "square"
    }
}

# Level line color mappings
LEVEL_LINE_CONFIG = {
    "CREEK": {
        "color": "#DC2626",  # Red
        "label_prefix": "Creek"
    },
    "ICE": {
        "color": "#2563EB",  # Blue
        "label_prefix": "Ice"
    },
    "JUMP": {
        "color": "#16A34A",  # Green
        "label_prefix": "Jump"
    }
}

# Phase background color mappings
PHASE_COLOR_CONFIG = {
    "A": "#9CA3AF20",  # Gray, 12% opacity
    "B": "#3B82F620",  # Blue, 12% opacity
    "C": "#FCD34D20",  # Yellow, 12% opacity
    "D": "#FB923C20",  # Orange, 12% opacity
    "E": "#34D39920"   # Green, 12% opacity
}

# Preliminary event configurations
PRELIMINARY_EVENT_CONFIG = {
    "PS": {
        "label": "Preliminary Support",
        "description": "Initial buying support - first sign of demand",
        "color": "#2563EB",  # Blue
        "shape": "circle"
    },
    "SC": {
        "label": "Selling Climax",
        "description": "Panic selling exhaustion - heavy volume sell-off",
        "color": "#DC2626",  # Red
        "shape": "triangle"
    },
    "AR": {
        "label": "Automatic Rally",
        "description": "Relief rally after selling climax",
        "color": "#16A34A",  # Green
        "shape": "circle"
    },
    "ST": {
        "label": "Secondary Test",
        "description": "Retest of selling climax low",
        "color": "#9333EA",  # Purple
        "shape": "square"
    }
}
