# IntradayCampaignDetector API Documentation

## Table of Contents

1. [Overview](#overview)
2. [Class: IntradayCampaignDetector](#class-intradaycampaigndetector)
3. [Dataclass: Campaign](#dataclass-campaign)
4. [Enums](#enums)
5. [Helper Functions](#helper-functions)
6. [Integration Examples](#integration-examples)
7. [Error Handling](#error-handling)
8. [Best Practices](#best-practices)

---

## Overview

The `IntradayCampaignDetector` class implements multi-pattern campaign detection for intraday Wyckoff trading. It groups detected patterns (Spring, AR, SOS, LPS) into cohesive campaigns, tracks campaign lifecycle, enforces risk limits, and provides comprehensive volume analysis.

**Module**: `backend/src/backtesting/intraday_campaign_detector.py`

**Key Features**:
- Pattern integration and time-window grouping
- Wyckoff phase progression tracking
- Position sizing and portfolio heat management
- Volume profile analysis (DECLINING/INCREASING/NEUTRAL)
- Effort vs. Result divergence detection
- Absorption quality scoring

**Use Cases**:
- Backtesting Wyckoff strategies
- Live trading signal generation
- Portfolio risk monitoring
- Campaign-based position management

---

## Class: IntradayCampaignDetector

### Constructor

```python
def __init__(
    self,
    campaign_window_hours: int = 48,
    max_pattern_gap_hours: int = 48,
    min_patterns_for_active: int = 2,
    expiration_hours: int = 72,
    max_concurrent_campaigns: int = 3,
    max_portfolio_heat_pct: Decimal = Decimal("10.0"),
) -> None
```

Creates a new campaign detector with specified configuration.

#### Parameters

| Parameter | Type | Default | Valid Range | Description |
|-----------|------|---------|-------------|-------------|
| `campaign_window_hours` | int | 48 | 1-240 | Maximum hours between first and last pattern in a campaign |
| `max_pattern_gap_hours` | int | 48 | 1-120 | Maximum hours between consecutive patterns |
| `min_patterns_for_active` | int | 2 | 2-5 | Minimum patterns required to transition FORMING → ACTIVE |
| `expiration_hours` | int | 72 | 24-360 | Hours before FORMING campaign expires and transitions to FAILED |
| `max_concurrent_campaigns` | int | 3 | 1-10 | Maximum number of ACTIVE campaigns allowed simultaneously |
| `max_portfolio_heat_pct` | Decimal | 10.0 | 5.0-50.0 | Maximum portfolio risk as percentage of account (FR7.7) |

#### Example

```python
from src.backtesting.intraday_campaign_detector import IntradayCampaignDetector
from decimal import Decimal

# Standard intraday detector
detector = IntradayCampaignDetector(
    campaign_window_hours=48,
    min_patterns_for_active=2,
    max_concurrent_campaigns=3,
    max_portfolio_heat_pct=Decimal("10.0")
)

# Aggressive short-term detector
aggressive_detector = IntradayCampaignDetector(
    campaign_window_hours=24,
    max_pattern_gap_hours=12,
    min_patterns_for_active=2,
    expiration_hours=48,
    max_concurrent_campaigns=5,
    max_portfolio_heat_pct=Decimal("15.0")
)

# Conservative long-term detector
conservative_detector = IntradayCampaignDetector(
    campaign_window_hours=120,
    max_pattern_gap_hours=72,
    min_patterns_for_active=3,
    expiration_hours=240,
    max_concurrent_campaigns=2,
    max_portfolio_heat_pct=Decimal("8.0")
)
```

---

### Public Methods

#### add_pattern()

```python
def add_pattern(
    self,
    pattern: WyckoffPattern,
    account_size: Optional[Decimal] = None,
    risk_pct_per_trade: Decimal = Decimal("2.0"),
) -> Optional[Campaign]
```

Adds a detected pattern to campaign tracking. Creates new campaigns or extends existing ones based on time windows and sequence validation.

**Parameters**:
- `pattern` (WyckoffPattern): Detected pattern instance (Spring, AutomaticRally, SOSBreakout, or LPS)
- `account_size` (Decimal, optional): Total account size for position sizing and portfolio heat calculation
- `risk_pct_per_trade` (Decimal): Risk percentage per trade, max 2.0% (default: 2.0%)

**Returns**:
- `Campaign | None`: Updated or created campaign, or `None` if rejected due to limits

**Behavior**:
1. Expires stale campaigns (> `expiration_hours`)
2. Finds existing campaign within time windows or checks portfolio limits
3. Validates pattern sequence (Spring → AR → SOS → LPS)
4. Calculates position sizing and portfolio heat
5. Updates campaign metadata (support/resistance, strength score, risk metrics)
6. Performs volume analysis (profile, effort vs. result, climax detection)
7. Transitions campaign state (FORMING → ACTIVE if threshold met)

**Example**:

```python
from src.models.spring import Spring
from decimal import Decimal
from datetime import datetime

# Create pattern
spring = Spring(
    bar_number=100,
    bar_index=100,
    detection_timestamp=datetime.utcnow(),
    spring_low=Decimal("98.50"),
    recovery_price=Decimal("100.00"),
    volume_ratio=Decimal("0.45"),
    quality_tier="EXCELLENT",
    quality_score=0.88,
    # ... other fields
)

# Add to detector
campaign = detector.add_pattern(
    pattern=spring,
    account_size=Decimal("100000"),
    risk_pct_per_trade=Decimal("2.0")
)

if campaign:
    print(f"Campaign {campaign.campaign_id}: {campaign.state.value}")
    print(f"Support: ${campaign.support_level}")
    print(f"Position Size: {campaign.position_size} shares")
    print(f"Dollar Risk: ${campaign.dollar_risk}")
else:
    print("Pattern rejected - portfolio limits exceeded")
```

**Rejection Scenarios**:
- Too many active campaigns (≥ `max_concurrent_campaigns`)
- Portfolio heat would exceed `max_portfolio_heat_pct`
- Invalid pattern sequence (e.g., Spring after SOS)

---

#### get_active_campaigns()

```python
def get_active_campaigns(self) -> list[Campaign]
```

Returns all campaigns in FORMING or ACTIVE state.

**Returns**:
- `list[Campaign]`: List of campaigns that are FORMING or ACTIVE

**Example**:

```python
active = detector.get_active_campaigns()

print(f"Active campaigns: {len(active)}")

for campaign in active:
    print(f"\nCampaign {campaign.campaign_id}:")
    print(f"  State: {campaign.state.value}")
    print(f"  Phase: {campaign.current_phase.value if campaign.current_phase else 'UNKNOWN'}")
    print(f"  Patterns: {len(campaign.patterns)}")
    print(f"  Strength: {campaign.strength_score:.2f}")
    print(f"  Volume Profile: {campaign.volume_profile.value}")
    print(f"  Dollar Risk: ${campaign.dollar_risk}")
```

**Use Cases**:
- Portfolio heat calculation
- Risk monitoring dashboards
- Signal prioritization
- Campaign summary reports

---

#### expire_stale_campaigns()

```python
def expire_stale_campaigns(self, current_time: datetime) -> None
```

Marks campaigns as FAILED if they exceed expiration time without completing.

**Parameters**:
- `current_time` (datetime): Current timestamp for expiration check

**Behavior**:
- Checks all FORMING and ACTIVE campaigns
- Transitions to FAILED if `(current_time - start_time) > expiration_hours`
- Sets `failure_reason` field with details
- Logs expiration event

**Example**:

```python
from datetime import datetime

# Manual expiration check
detector.expire_stale_campaigns(datetime.utcnow())

# Check for expired campaigns
for campaign in detector.campaigns:
    if campaign.state == CampaignState.FAILED:
        print(f"Campaign {campaign.campaign_id} expired")
        print(f"Reason: {campaign.failure_reason}")
```

**Note**: `add_pattern()` automatically calls this method, so manual calls are typically unnecessary unless you need to check expirations between pattern detections.

---

#### update_phase_with_bar_index()

```python
def update_phase_with_bar_index(
    self,
    campaign: Campaign,
    new_phase: WyckoffPhase,
    bar_index: int,
    timestamp: Optional[datetime] = None,
) -> None
```

Updates campaign phase and tracks bar indices for phase transitions. Used in backtesting when bar_index is available.

**Parameters**:
- `campaign` (Campaign): Campaign to update
- `new_phase` (WyckoffPhase): New Wyckoff phase (A, B, C, D, E)
- `bar_index` (int): Current bar index in backtest dataset
- `timestamp` (datetime, optional): Timestamp for phase history (defaults to `utcnow()`)

**Updates**:
- `campaign.current_phase`
- `campaign.phase_history` (appends tuple of (timestamp, phase))
- `campaign.phase_transition_count`
- Phase start bar indices (`phase_c_start_bar`, `phase_d_start_bar`, `phase_e_start_bar`)

**Example**:

```python
from src.models.wyckoff_phase import WyckoffPhase
from datetime import datetime

# Backtest loop
for i, bar in enumerate(historical_data):
    # Detect patterns
    patterns = pattern_detector.detect(bar)

    for pattern in patterns:
        campaign = detector.add_pattern(pattern, account_size)

        if campaign and campaign.state == CampaignState.ACTIVE:
            # Update phase with bar tracking
            new_phase = WyckoffPhase.D
            detector.update_phase_with_bar_index(
                campaign=campaign,
                new_phase=new_phase,
                bar_index=i,
                timestamp=bar.timestamp
            )

            # Check phase duration
            if campaign.phase_d_start_bar:
                bars_in_phase_d = i - campaign.phase_d_start_bar
                print(f"Campaign in Phase D for {bars_in_phase_d} bars")
```

---

## Dataclass: Campaign

### Overview

The `Campaign` dataclass represents a Wyckoff campaign with all associated metadata, risk metrics, and volume analysis.

```python
@dataclass
class Campaign:
    """Micro-campaign tracking detected Wyckoff patterns."""
```

### Fields

#### Identity Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `campaign_id` | str | UUID | Unique campaign identifier |
| `start_time` | datetime | utcnow() | First pattern timestamp |
| `patterns` | list[WyckoffPattern] | [] | List of patterns in chronological order |
| `state` | CampaignState | FORMING | Current lifecycle state |
| `current_phase` | WyckoffPhase \| None | None | Current Wyckoff phase |
| `failure_reason` | str \| None | None | Reason for FAILED state |

#### Risk Metadata Fields (AC4.9)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `support_level` | Decimal \| None | None | Lowest Spring low (Creek level) |
| `resistance_level` | Decimal \| None | None | Highest AR/SOS resistance (Ice level) |
| `strength_score` | float | 0.0 | Campaign quality score (0.0-1.0) |
| `risk_per_share` | Decimal \| None | None | Entry price - support_level |
| `range_width_pct` | Decimal \| None | None | (resistance - support) / support * 100 |

#### Position Sizing Fields (Story 14.3)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `position_size` | Decimal | 0 | Shares/contracts for this campaign |
| `dollar_risk` | Decimal | 0 | Total dollar risk (risk_per_share × position_size) |

#### Exit Logic Fields (FR6.1, Story 13.6.1)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `jump_level` | Decimal \| None | None | Measured move target (Ice + range_width) |
| `original_ice_level` | Decimal \| None | None | Ice level at campaign start |
| `original_jump_level` | Decimal \| None | None | Jump level at campaign start |
| `ice_expansion_count` | int | 0 | Number of Ice level expansions detected |
| `last_ice_update_bar` | int \| None | None | Bar index of last Ice update |
| `phase_e_progress_percent` | Decimal | 0 | Progress toward Jump Level (0-100%) |
| `entry_atr` | Decimal \| None | None | ATR at entry |
| `max_atr_seen` | Decimal \| None | None | Highest ATR during campaign |
| `timeframe` | str | "1d" | Timeframe for intraday adjustments |

#### Phase Tracking Fields (FR7.3, Story 13.7)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `phase_c_start_bar` | int \| None | None | Bar index when Phase C started |
| `phase_d_start_bar` | int \| None | None | Bar index when Phase D started |
| `phase_e_start_bar` | int \| None | None | Bar index when Phase E started |
| `phase_history` | list[tuple[datetime, WyckoffPhase]] | [] | All phase transitions with timestamps |
| `phase_transition_count` | int | 0 | Total number of phase transitions |

#### Volume Analysis Fields (Story 14.4)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `volume_profile` | VolumeProfile | UNKNOWN | Volume trend classification |
| `volume_trend_quality` | float | 0.0 | Confidence in volume trend (0.0-1.0) |
| `effort_vs_result` | EffortVsResult | UNKNOWN | Effort/result relationship |
| `climax_detected` | bool | False | Whether climactic volume event detected |
| `absorption_quality` | float | 0.0 | Spring absorption quality (0.0-1.0) |
| `volume_history` | list[Decimal] | [] | Recent volume ratios from patterns |

### Field Type Reference

#### Calculated vs. Set Fields

**Set by User/Pattern**:
- `patterns` (appended via `add_pattern()`)
- `start_time` (from first pattern)
- `account_size` (via `add_pattern()` parameter)

**Calculated by Detector**:
- All risk metadata fields (`support_level`, `resistance_level`, `strength_score`, etc.)
- All position sizing fields (`position_size`, `dollar_risk`)
- All volume analysis fields (`volume_profile`, `effort_vs_result`, etc.)
- All phase tracking fields (`phase_history`, `phase_transition_count`, etc.)

### Usage Example

```python
# Access campaign fields
if campaign.state == CampaignState.ACTIVE:
    # Risk metrics
    entry_price = campaign.patterns[-1].close
    stop_loss = campaign.support_level
    target = campaign.jump_level

    # Position sizing
    shares = campaign.position_size
    risk_dollars = campaign.dollar_risk

    # Volume analysis
    if campaign.volume_profile == VolumeProfile.DECLINING:
        print("✓ Bullish volume profile - accumulation detected")

    if campaign.effort_vs_result == EffortVsResult.DIVERGENCE:
        if isinstance(campaign.patterns[-1], Spring):
            print("✓ Bullish divergence - absorption at Spring")
        else:
            print("✗ Bearish divergence - potential distribution")

    # Quality metrics
    if campaign.strength_score > 0.75 and campaign.absorption_quality > 0.7:
        print("✓ High-quality campaign - favorable entry")

    # Phase tracking
    print(f"Current Phase: {campaign.current_phase.value}")
    print(f"Phase History: {campaign.phase_history}")
```

---

## Enums

### CampaignState

Campaign lifecycle states.

```python
class CampaignState(Enum):
    FORMING = "FORMING"      # 1 pattern detected, waiting for confirmation
    ACTIVE = "ACTIVE"        # 2+ patterns, campaign is actionable
    COMPLETED = "COMPLETED"  # Successfully reached Phase E or exit
    FAILED = "FAILED"        # Exceeded expiration time without completion
```

**State Transitions**:
```
FORMING → ACTIVE    (when pattern count ≥ min_patterns_for_active)
FORMING → FAILED    (when exceeds expiration_hours)
ACTIVE → COMPLETED  (when reaches exit criteria)
ACTIVE → FAILED     (when exceeds expiration_hours)
```

---

### VolumeProfile

Volume trend classification for campaign progression.

```python
class VolumeProfile(Enum):
    INCREASING = "INCREASING"  # Volume rising (potential distribution)
    DECLINING = "DECLINING"    # Volume declining (professional accumulation)
    NEUTRAL = "NEUTRAL"        # No clear trend
    UNKNOWN = "UNKNOWN"        # Insufficient data (< 3 patterns)
```

**Interpretation**:
- **DECLINING**: Bullish in accumulation - professionals accumulating quietly
- **INCREASING**: Bearish warning - potential distribution
- **NEUTRAL**: Mixed signals - market in balance
- **UNKNOWN**: Need more patterns for classification

See [Volume Analysis Guide](../guides/volume-analysis-guide.md#4-volume-profile-interpretation) for detailed interpretation.

---

### EffortVsResult

Wyckoff effort (volume) vs. result (price movement) relationship.

```python
class EffortVsResult(Enum):
    HARMONY = "HARMONY"          # Volume and price align (normal)
    DIVERGENCE = "DIVERGENCE"    # Volume/price diverge (absorption or distribution)
    UNKNOWN = "UNKNOWN"          # Insufficient data
```

**Context-Dependent Interpretation**:
- **DIVERGENCE at Spring**: Bullish (absorption)
- **DIVERGENCE at Rally/SOS**: Bearish (distribution)
- **HARMONY**: Normal market behavior

See [Volume Analysis Guide](../guides/volume-analysis-guide.md#5-effort-vs-result-analysis) for examples.

---

### WyckoffPhase

```python
class WyckoffPhase(Enum):
    A = "A"  # Stopping action (SC, PS, AR)
    B = "B"  # Building cause (tests, accumulation)
    C = "C"  # Spring test (final shakeout)
    D = "D"  # SOS and markup preparation
    E = "E"  # LPS and markup continuation
    UNKNOWN = "UNKNOWN"  # Phase not yet determined
```

---

## Helper Functions

### calculate_position_size()

```python
def calculate_position_size(
    account_size: Decimal,
    risk_pct_per_trade: Decimal,
    risk_per_share: Decimal,
) -> Decimal
```

Calculates position size based on risk parameters.

**Formula**: `position_size = (account_size × risk_pct) / risk_per_share`

**Parameters**:
- `account_size` (Decimal): Total account size in dollars
- `risk_pct_per_trade` (Decimal): Risk percentage (max 2.0%)
- `risk_per_share` (Decimal): Dollar risk per share (entry - stop)

**Returns**:
- `Decimal`: Position size in whole shares

**Raises**:
- `ValueError`: If `risk_pct_per_trade` exceeds 2.0% hard limit

**Example**:

```python
from src.backtesting.intraday_campaign_detector import calculate_position_size
from decimal import Decimal

position = calculate_position_size(
    account_size=Decimal("100000"),
    risk_pct_per_trade=Decimal("2.0"),
    risk_per_share=Decimal("5.00")
)

print(f"Position Size: {position} shares")  # 400 shares
print(f"Dollar Risk: ${position * Decimal('5.00')}")  # $2,000
```

---

### create_timeframe_optimized_detector()

```python
def create_timeframe_optimized_detector(timeframe: str) -> IntradayCampaignDetector
```

Factory function to create timeframe-optimized campaign detector.

**Parameters**:
- `timeframe` (str): Timeframe code ("15m", "1h", "1d", etc.)

**Returns**:
- `IntradayCampaignDetector`: Configured detector

**Configurations**:

**Intraday ("1m", "5m", "15m", "1h")**:
- `campaign_window_hours`: 48
- `max_pattern_gap_hours`: 48
- `expiration_hours`: 72
- `max_concurrent_campaigns`: 3
- `max_portfolio_heat_pct`: 10.0%

**Daily and longer ("1d", "1w", etc.)**:
- `campaign_window_hours`: 240 (10 days)
- `max_pattern_gap_hours`: 120 (5 days)
- `expiration_hours`: 360 (15 days)
- `max_concurrent_campaigns`: 5
- `max_portfolio_heat_pct`: 10.0%

**Example**:

```python
from src.backtesting.intraday_campaign_detector import create_timeframe_optimized_detector

# Create intraday detector
intraday_detector = create_timeframe_optimized_detector("15m")

# Create daily detector
daily_detector = create_timeframe_optimized_detector("1d")

# Use detector
campaign = intraday_detector.add_pattern(spring_pattern, account_size)
```

---

## Integration Examples

### Example 1: Basic Pattern Detection and Campaign Tracking

```python
from src.backtesting.intraday_campaign_detector import IntradayCampaignDetector
from src.models.spring import Spring
from src.models.sos_breakout import SOSBreakout
from decimal import Decimal
from datetime import datetime

# Initialize detector
detector = IntradayCampaignDetector(
    campaign_window_hours=48,
    min_patterns_for_active=2,
    max_concurrent_campaigns=3
)

# Simulate pattern detection
spring = Spring(
    bar_number=100,
    bar_index=100,
    detection_timestamp=datetime.utcnow(),
    spring_low=Decimal("98.50"),
    recovery_price=Decimal("100.00"),
    volume_ratio=Decimal("0.45"),
    quality_tier="EXCELLENT",
    # ... other fields
)

sos = SOSBreakout(
    bar_number=110,
    bar_index=110,
    detection_timestamp=datetime.utcnow(),
    breakout_price=Decimal("102.50"),
    volume_ratio=Decimal("2.15"),
    quality_tier="EXCELLENT",
    # ... other fields
)

# Add patterns
campaign1 = detector.add_pattern(spring, account_size=Decimal("100000"))
if campaign1:
    print(f"Spring added to campaign {campaign1.campaign_id}")
    print(f"State: {campaign1.state.value}")  # FORMING

campaign2 = detector.add_pattern(sos, account_size=Decimal("100000"))
if campaign2:
    print(f"SOS added to campaign {campaign2.campaign_id}")
    print(f"State: {campaign2.state.value}")  # ACTIVE
    print(f"Phase: {campaign2.current_phase.value}")  # D
    print(f"Position Size: {campaign2.position_size} shares")

# Retrieve active campaigns
active = detector.get_active_campaigns()
print(f"\nActive Campaigns: {len(active)}")
```

---

### Example 2: Backtesting Integration

```python
from src.backtesting.intraday_campaign_detector import create_timeframe_optimized_detector
from src.pattern_engine.detectors.spring_detector import SpringDetector
from src.pattern_engine.detectors.sos_detector import SOSDetector
from decimal import Decimal
import pandas as pd

# Load historical data
df = pd.read_parquet("historical_data.parquet")

# Initialize components
detector = create_timeframe_optimized_detector("15m")
spring_detector = SpringDetector()
sos_detector = SOSDetector()

account_size = Decimal("100000")
signals = []

# Backtest loop
for i, row in df.iterrows():
    bar = convert_row_to_ohlcv(row)  # Your conversion logic

    # Detect Spring patterns
    spring_results = spring_detector.detect(bar, historical_bars)
    for spring in spring_results:
        campaign = detector.add_pattern(spring, account_size)

        if campaign and campaign.state == CampaignState.ACTIVE:
            # Generate BUY signal
            signals.append({
                "timestamp": bar.timestamp,
                "action": "BUY",
                "price": spring.recovery_price,
                "stop_loss": campaign.support_level,
                "target": campaign.jump_level,
                "position_size": campaign.position_size,
                "campaign_id": campaign.campaign_id,
                "strength_score": campaign.strength_score,
                "volume_profile": campaign.volume_profile.value
            })

    # Detect SOS patterns
    sos_results = sos_detector.detect(bar, historical_bars)
    for sos in sos_results:
        campaign = detector.add_pattern(sos, account_size)

        if campaign and campaign.state == CampaignState.ACTIVE:
            # Generate ADD signal
            signals.append({
                "timestamp": bar.timestamp,
                "action": "ADD",
                "price": sos.breakout_price,
                "stop_loss": campaign.support_level,
                "target": campaign.jump_level,
                "position_size": campaign.position_size,
                "campaign_id": campaign.campaign_id
            })

# Analyze results
signals_df = pd.DataFrame(signals)
print(f"Total Signals: {len(signals_df)}")
print(f"Buy Signals: {len(signals_df[signals_df['action'] == 'BUY'])}")
print(f"Add Signals: {len(signals_df[signals_df['action'] == 'ADD'])}")
```

---

### Example 3: Live Trading Integration with Portfolio Heat Monitoring

```python
from src.backtesting.intraday_campaign_detector import IntradayCampaignDetector
from src.backtesting.intraday_campaign_detector import CampaignState, VolumeProfile
from decimal import Decimal

class TradingSystem:
    def __init__(self, account_size: Decimal):
        self.detector = IntradayCampaignDetector(
            max_concurrent_campaigns=3,
            max_portfolio_heat_pct=Decimal("10.0")
        )
        self.account_size = account_size

    def on_pattern_detected(self, pattern):
        """Called when pattern detector finds a pattern."""
        campaign = self.detector.add_pattern(
            pattern=pattern,
            account_size=self.account_size,
            risk_pct_per_trade=Decimal("2.0")
        )

        if campaign is None:
            print("Pattern rejected - portfolio limits exceeded")
            return

        # Check if we should take action
        if campaign.state == CampaignState.ACTIVE:
            # Quality checks
            if campaign.strength_score < 0.6:
                print(f"Campaign {campaign.campaign_id} quality too low, skipping")
                return

            # Volume profile check
            if campaign.volume_profile == VolumeProfile.INCREASING:
                print(f"Campaign {campaign.campaign_id} shows distribution, skipping")
                return

            # Volume divergence check
            if campaign.effort_vs_result == EffortVsResult.DIVERGENCE:
                if not isinstance(pattern, Spring):
                    print(f"Campaign {campaign.campaign_id} bearish divergence, skipping")
                    return

            # Execute trade
            self.execute_trade(campaign)

    def execute_trade(self, campaign):
        """Execute trade based on campaign."""
        entry = campaign.patterns[-1].close
        stop = campaign.support_level
        target = campaign.jump_level
        shares = campaign.position_size

        print(f"\n=== Trade Execution ===")
        print(f"Campaign: {campaign.campaign_id}")
        print(f"Entry: ${entry}")
        print(f"Stop: ${stop}")
        print(f"Target: ${target}")
        print(f"Shares: {shares}")
        print(f"Risk: ${campaign.dollar_risk}")
        print(f"Phase: {campaign.current_phase.value}")
        print(f"Volume Profile: {campaign.volume_profile.value}")
        print(f"Strength: {campaign.strength_score:.2f}")
        print(f"Absorption Quality: {campaign.absorption_quality:.2f}")

        # Submit order to broker (your implementation)
        # order = self.broker.submit_order(...)

    def get_portfolio_status(self):
        """Get current portfolio heat and active campaigns."""
        active = self.detector.get_active_campaigns()

        total_risk = sum(c.dollar_risk for c in active)
        heat_pct = (total_risk / self.account_size) * Decimal("100")

        print(f"\n=== Portfolio Status ===")
        print(f"Active Campaigns: {len(active)}/{self.detector.max_concurrent_campaigns}")
        print(f"Portfolio Heat: {heat_pct:.2f}%/{self.detector.max_portfolio_heat_pct}%")
        print(f"Total Risk: ${total_risk}")

        for campaign in active:
            print(f"\nCampaign {campaign.campaign_id}:")
            print(f"  Patterns: {len(campaign.patterns)}")
            print(f"  Phase: {campaign.current_phase.value if campaign.current_phase else 'UNKNOWN'}")
            print(f"  Risk: ${campaign.dollar_risk}")
            print(f"  Volume: {campaign.volume_profile.value}")

# Usage
system = TradingSystem(account_size=Decimal("100000"))

# In your pattern detection loop
for pattern in detected_patterns:
    system.on_pattern_detected(pattern)

# Check portfolio status
system.get_portfolio_status()
```

---

### Example 4: Campaign Quality Filtering

```python
def filter_high_quality_campaigns(detector: IntradayCampaignDetector) -> list[Campaign]:
    """
    Filter campaigns to only high-quality setups.

    Quality Criteria:
    - Strength score > 0.75
    - DECLINING volume profile (accumulation)
    - Absorption quality > 0.7 (if Spring present)
    - No bearish divergences
    - Phase C or D (optimal entry phases)
    """
    active = detector.get_active_campaigns()
    high_quality = []

    for campaign in active:
        # Strength check
        if campaign.strength_score < 0.75:
            continue

        # Volume profile check
        if campaign.volume_profile != VolumeProfile.DECLINING:
            continue

        # Absorption quality check (if Spring present)
        has_spring = any(isinstance(p, Spring) for p in campaign.patterns)
        if has_spring and campaign.absorption_quality < 0.7:
            continue

        # Divergence check (reject bearish divergences)
        if campaign.effort_vs_result == EffortVsResult.DIVERGENCE:
            latest_pattern = campaign.patterns[-1]
            if not isinstance(latest_pattern, Spring):
                # Bearish divergence at rally
                continue

        # Phase check (C or D optimal)
        if campaign.current_phase not in [WyckoffPhase.C, WyckoffPhase.D]:
            continue

        high_quality.append(campaign)

    return high_quality

# Usage
detector = IntradayCampaignDetector()

# ... add patterns ...

best_campaigns = filter_high_quality_campaigns(detector)
print(f"High-Quality Campaigns: {len(best_campaigns)}")

for campaign in best_campaigns:
    print(f"\nCampaign {campaign.campaign_id}:")
    print(f"  Strength: {campaign.strength_score:.2f}")
    print(f"  Volume Profile: {campaign.volume_profile.value}")
    print(f"  Absorption: {campaign.absorption_quality:.2f}")
    print(f"  Phase: {campaign.current_phase.value}")
```

---

## Error Handling

### Common Errors and Solutions

#### 1. ValueError: risk_pct_per_trade exceeds 2.0% hard limit

**Cause**: Attempted to use `risk_pct_per_trade` > 2.0%

**Solution**:
```python
try:
    campaign = detector.add_pattern(
        pattern,
        account_size=Decimal("100000"),
        risk_pct_per_trade=Decimal("2.5")  # TOO HIGH
    )
except ValueError as e:
    print(f"Error: {e}")
    # Use valid risk percentage
    campaign = detector.add_pattern(
        pattern,
        account_size=Decimal("100000"),
        risk_pct_per_trade=Decimal("2.0")  # MAX ALLOWED
    )
```

---

#### 2. Portfolio Heat Limit Exceeded

**Symptom**: `add_pattern()` returns `None`, logs show "Portfolio heat limit exceeded"

**Cause**: Adding pattern would push portfolio heat above `max_portfolio_heat_pct`

**Solution**:
```python
campaign = detector.add_pattern(pattern, account_size)

if campaign is None:
    # Check current heat
    active = detector.get_active_campaigns()
    total_risk = sum(c.dollar_risk for c in active)
    heat_pct = (total_risk / account_size) * Decimal("100")

    print(f"Portfolio heat at {heat_pct:.2f}%, max is {detector.max_portfolio_heat_pct}%")
    print(f"Consider closing existing campaigns or reducing position sizes")

    # Option 1: Wait for existing campaigns to close
    # Option 2: Increase max_portfolio_heat_pct (careful!)
    # Option 3: Close weakest campaign to free up risk budget
```

---

#### 3. Invalid Pattern Sequence

**Symptom**: Pattern added but phase doesn't update, warning logged

**Cause**: Pattern doesn't follow valid Wyckoff progression (e.g., Spring after SOS)

**Valid Transitions**:
```
Spring → [Spring, AutomaticRally, SOSBreakout]
AutomaticRally → [SOSBreakout, LPS]
SOSBreakout → [SOSBreakout, LPS]
LPS → [LPS]
```

**Solution**:
```python
# Check sequence before adding
def is_valid_next_pattern(campaign, new_pattern) -> bool:
    if not campaign.patterns:
        return True  # First pattern always valid

    last_pattern = campaign.patterns[-1]

    if isinstance(last_pattern, Spring):
        return isinstance(new_pattern, (Spring, AutomaticRally, SOSBreakout))
    elif isinstance(last_pattern, AutomaticRally):
        return isinstance(new_pattern, (SOSBreakout, LPS))
    elif isinstance(last_pattern, SOSBreakout):
        return isinstance(new_pattern, (SOSBreakout, LPS))
    elif isinstance(last_pattern, LPS):
        return isinstance(new_pattern, LPS)

    return False

# Validate before adding
if is_valid_next_pattern(campaign, pattern):
    detector.add_pattern(pattern, account_size)
else:
    print("Invalid pattern sequence, creating new campaign")
```

---

#### 4. Campaign Expiration

**Symptom**: Campaign transitions to FAILED state unexpectedly

**Cause**: Campaign exceeded `expiration_hours` without completing

**Solution**:
```python
# Monitor campaign age
for campaign in detector.campaigns:
    if campaign.state in [CampaignState.FORMING, CampaignState.ACTIVE]:
        age_hours = (datetime.utcnow() - campaign.start_time).total_seconds() / 3600

        if age_hours > detector.expiration_hours * 0.8:  # 80% warning
            print(f"Campaign {campaign.campaign_id} approaching expiration")
            print(f"Age: {age_hours:.1f}h / {detector.expiration_hours}h")
            print(f"Consider taking action or adjusting expiration_hours")

# Adjust expiration if needed
detector.expiration_hours = 120  # Extend to 120 hours
```

---

## Best Practices

### 1. Always Provide account_size for Position Sizing

```python
# ✓ GOOD - Position sizing enabled
campaign = detector.add_pattern(
    pattern,
    account_size=Decimal("100000"),
    risk_pct_per_trade=Decimal("2.0")
)

# ✗ BAD - No position sizing
campaign = detector.add_pattern(pattern)  # position_size will be 0
```

---

### 2. Monitor Portfolio Heat Regularly

```python
def check_portfolio_health(detector, account_size):
    active = detector.get_active_campaigns()
    total_risk = sum(c.dollar_risk for c in active)
    heat_pct = (total_risk / account_size) * Decimal("100")

    if heat_pct > detector.max_portfolio_heat_pct * Decimal("0.8"):
        print(f"⚠️ WARNING: Portfolio heat at {heat_pct:.2f}%")
        print(f"Approaching limit of {detector.max_portfolio_heat_pct}%")

    return heat_pct

# Call regularly
heat = check_portfolio_health(detector, account_size)
```

---

### 3. Filter by Volume Profile and Quality Metrics

```python
# Prioritize DECLINING volume profiles (accumulation)
active = detector.get_active_campaigns()

for campaign in active:
    if campaign.volume_profile == VolumeProfile.DECLINING:
        if campaign.strength_score > 0.75:
            print(f"✓ High-quality campaign: {campaign.campaign_id}")
            # Take trade
    elif campaign.volume_profile == VolumeProfile.INCREASING:
        print(f"✗ Distribution warning: {campaign.campaign_id}")
        # Consider exiting
```

---

### 4. Use Timeframe-Optimized Detectors

```python
# ✓ GOOD - Use factory function for optimal settings
detector_15m = create_timeframe_optimized_detector("15m")
detector_1d = create_timeframe_optimized_detector("1d")

# ✗ BAD - Same settings for all timeframes
detector = IntradayCampaignDetector()  # Uses intraday defaults
```

---

### 5. Check Sequence Validity Before Making Trading Decisions

```python
def should_trade(campaign):
    # Verify complete sequence: Spring → AR → SOS
    has_spring = any(isinstance(p, Spring) for p in campaign.patterns)
    has_ar = any(isinstance(p, AutomaticRally) for p in campaign.patterns)
    has_sos = any(isinstance(p, SOSBreakout) for p in campaign.patterns)

    if has_spring and has_ar and has_sos:
        print("✓ Complete Wyckoff progression - HIGH PROBABILITY")
        return True
    elif has_spring and has_sos:
        print("✓ Valid progression (no AR) - MEDIUM PROBABILITY")
        return True
    else:
        print("✗ Incomplete progression - WAIT")
        return False
```

---

## Related Documentation

- **Volume Analysis Guide**: [docs/guides/volume-analysis-guide.md](../guides/volume-analysis-guide.md)
- **Pattern Detectors**: `backend/src/pattern_engine/detectors/`
- **Risk Management**: `backend/src/risk_management/`
- **Backtesting Engine**: `backend/src/backtesting/`
- **Story 14.3**: Portfolio Heat Calculation
- **Story 14.4**: Volume Profile Tracking

---

**Last Updated**: 2026-01-17
**Version**: 1.0
**Story**: STORY-14.6 - Volume Analysis Guide & API Documentation
**Module**: `backend/src/backtesting/intraday_campaign_detector.py`
