# SpringDetector Usage Examples

**Story 5.6 - Multi-Spring Detection with Risk Assessment**

This document provides comprehensive usage examples for the `SpringDetector` class, demonstrating single-spring detection, multi-spring accumulation patterns, and risk assessment using Wyckoff methodology.

---

## Table of Contents

1. [Basic Single Spring Detection](#1-basic-single-spring-detection)
2. [Multi-Spring Professional Accumulation (Declining Volume)](#2-multi-spring-professional-accumulation-declining-volume)
3. [Multi-Spring Distribution Warning (Rising Volume)](#3-multi-spring-distribution-warning-rising-volume)
4. [Risk Assessment Interpretation](#4-risk-assessment-interpretation)
5. [Volume Trend Analysis](#5-volume-trend-analysis)
6. [Best Spring and Signal Selection](#6-best-spring-and-signal-selection)
7. [Backward Compatibility (Legacy API)](#7-backward-compatibility-legacy-api)
8. [Integration with Trading System](#8-integration-with-trading-system)

---

## 1. Basic Single Spring Detection

### Scenario
Detect a single spring in an AAPL accumulation range during Phase C.

### Code Example

```python
from backend.src.pattern_engine.detectors.spring_detector import SpringDetector
from backend.src.models.phase_classification import WyckoffPhase

# Initialize detector
detector = SpringDetector()

# Assume we have:
# - trading_range: TradingRange with Creek at $98.00, Jump at $110.00
# - bars: 50 OHLCV bars from AAPL daily data
# - phase: WyckoffPhase.C (confirmed by PhaseDetector from Story 4.4)

# Detect all springs (returns SpringHistory)
history = detector.detect_all_springs(
    range=trading_range,
    bars=bars,
    phase=WyckoffPhase.C
)

# Analyze results
print(f"Springs detected: {history.spring_count}")  # Output: 1
print(f"Risk level: {history.risk_level}")  # Output: MODERATE
print(f"Volume trend: {history.volume_trend}")  # Output: STABLE (only 1 spring)

# Access the spring
if history.best_spring:
    spring = history.best_spring
    print(f"Spring low: ${spring.spring_low}")  # $97.50
    print(f"Penetration: {spring.penetration_pct:.2%}")  # 2.04% below Creek
    print(f"Volume: {spring.volume_ratio}x")  # 0.42x (low volume = bullish)
    print(f"Recovery: {spring.recovery_bars} bars")  # 2 bars
    print(f"Quality: {spring.quality_tier}")  # IDEAL

# Access the signal (if test confirmed)
best_signal = detector.get_best_signal(history)
if best_signal:
    print(f"\nSignal Details:")
    print(f"Entry: ${best_signal.entry_price}")  # $98.10 (0.1% above Creek)
    print(f"Stop: ${best_signal.stop_loss}")  # $95.55 (2% below spring low)
    print(f"Target: ${best_signal.target_price}")  # $110.00 (Jump level)
    print(f"R-multiple: {best_signal.r_multiple}R")  # 4.8R
    print(f"Confidence: {best_signal.confidence}%")  # 78%
    print(f"Urgency: {best_signal.urgency}")  # IMMEDIATE
```

### Expected Output

```
Springs detected: 1
Risk level: MODERATE
Volume trend: STABLE (only 1 spring)
Spring low: $97.50
Penetration: 2.04% below Creek
Volume: 0.42x (low volume = bullish)
Recovery: 2 bars
Quality: IDEAL

Signal Details:
Entry: $98.10
Stop: $95.55
Target: $110.00
R-multiple: 4.8R
Confidence: 78%
Urgency: IMMEDIATE
```

### Interpretation (Wyckoff Context)

- **Single Spring**: One final shakeout below Creek support
- **MODERATE Risk**: Volume 0.42x (ideal range 0.3-0.5x)
- **STABLE Trend**: Not enough data for trend (need 2+ springs)
- **Actionable**: Confidence 78% exceeds FR4 70% minimum
- **Good Risk/Reward**: 4.8R meets FR19 3.0R minimum

---

## 2. Multi-Spring Professional Accumulation (Declining Volume)

### Scenario
AAPL accumulation range with THREE springs showing **DECLINING volume** (professional accumulation pattern - highly bullish).

### Spring Sequence

| Spring | Date | Low | Creek | Penetration | Volume | Recovery |
|--------|------|-----|-------|-------------|--------|----------|
| 1 | 2024-01-25 | $98.00 | $100.00 | 2.0% | 0.60x | 3 bars |
| 2 | 2024-02-09 | $97.50 | $100.00 | 2.5% | 0.48x | 2 bars |
| 3 | 2024-02-24 | $97.00 | $100.00 | 3.0% | 0.32x | 1 bar |

**Wyckoff Observation**: Volume **DECLINES** with each successive spring (0.60 → 0.48 → 0.32). This is the hallmark of professional accumulation.

### Code Example

```python
from backend.src.pattern_engine.detectors.spring_detector import SpringDetector
from backend.src.models.phase_classification import WyckoffPhase

detector = SpringDetector()

# Detect all springs in 60-bar sequence
history = detector.detect_all_springs(
    range=aapl_trading_range,
    bars=aapl_bars_60_days,
    phase=WyckoffPhase.C
)

# Analyze multi-spring pattern
print(f"Springs detected: {history.spring_count}")  # 3
print(f"Volume trend: {history.volume_trend}")  # DECLINING ✅
print(f"Risk level: {history.risk_level}")  # LOW ✅ (professional pattern)

# Examine all springs chronologically
print("\nSpring Sequence:")
for i, spring in enumerate(history.springs, 1):
    print(f"Spring {i}: {spring.bar.timestamp.date()}")
    print(f"  Low: ${spring.spring_low}")
    print(f"  Volume: {spring.volume_ratio}x")
    print(f"  Quality: {spring.quality_tier}")
    print()

# Output:
# Spring 1: 2024-01-25
#   Low: $98.00
#   Volume: 0.60x
#   Quality: ACCEPTABLE
#
# Spring 2: 2024-02-09
#   Low: $97.50
#   Volume: 0.48x
#   Quality: IDEAL
#
# Spring 3: 2024-02-24
#   Low: $97.00
#   Volume: 0.32x (LOWEST - BEST) ✅
#   Quality: EXCEPTIONAL

# Best spring has LOWEST volume (Wyckoff quality hierarchy)
assert history.best_spring == history.springs[2]  # Spring 3
print(f"Best spring volume: {history.best_spring.volume_ratio}x")  # 0.32x

# All signals (if tests confirmed)
print(f"\nSignals generated: {len(history.signals)}")  # 3 (all had tests)
for i, signal in enumerate(history.signals, 1):
    print(f"Signal {i}: Confidence {signal.confidence}%, R={signal.r_multiple}R")

# Best signal selection
best_signal = detector.get_best_signal(history)
print(f"\nBest Signal (highest confidence):")
print(f"Spring timestamp: {best_signal.spring_bar_timestamp.date()}")  # Spring 3
print(f"Confidence: {best_signal.confidence}%")  # 89% (excellent)
print(f"Entry: ${best_signal.entry_price}")
print(f"R-multiple: {best_signal.r_multiple}R")
```

### Expected Output

```
Springs detected: 3
Volume trend: DECLINING ✅
Risk level: LOW ✅ (professional pattern)

Spring Sequence:
Spring 1: 2024-01-25
  Low: $98.00
  Volume: 0.60x
  Quality: ACCEPTABLE

Spring 2: 2024-02-09
  Low: $97.50
  Volume: 0.48x
  Quality: IDEAL

Spring 3: 2024-02-24
  Low: $97.00
  Volume: 0.32x (LOWEST - BEST) ✅
  Quality: EXCEPTIONAL

Best spring volume: 0.32x

Signals generated: 3

Best Signal (highest confidence):
Spring timestamp: 2024-02-24
Confidence: 89% (excellent)
Entry: $100.10
R-multiple: 5.2R
```

### Interpretation (Wyckoff Context)

**DECLINING Volume = Professional Accumulation (Highest Probability Setup)**

1. **Spring 1 (0.60x volume)**: Initial shakeout, moderate volume
2. **Spring 2 (0.48x volume)**: Second test, LOWER volume (supply decreasing) ✅
3. **Spring 3 (0.32x volume)**: Final test, ULTRA-LOW volume (supply exhausted) ✅

**Wyckoff Analysis:**
> "Each successive spring shows LESS selling pressure. The composite operator has absorbed nearly all available supply. Volume declining from 0.60x → 0.48x → 0.32x proves professional accumulation is complete. Markup (Phase D → E) is imminent."

**Risk Assessment:**
- **Volume Trend**: DECLINING (bullish) ✅
- **Risk Level**: LOW (professional pattern) ✅
- **Trade Recommendation**: **STRONG BUY** - This is a textbook accumulation setup

---

## 3. Multi-Spring Distribution Warning (Rising Volume)

### Scenario
XYZ stock with THREE springs showing **RISING volume** (distribution warning - bearish).

### Spring Sequence

| Spring | Date | Low | Creek | Penetration | Volume | Recovery |
|--------|------|-----|-------|-------------|--------|----------|
| 1 | 2024-01-10 | $48.50 | $50.00 | 3.0% | 0.32x | 2 bars |
| 2 | 2024-01-25 | $48.00 | $50.00 | 4.0% | 0.52x | 3 bars |
| 3 | 2024-02-08 | $47.50 | $50.00 | 5.0% | 0.68x | 4 bars |

**Wyckoff Warning**: Volume **RISES** with each successive spring (0.32 → 0.52 → 0.68). This suggests distribution disguised as accumulation.

### Code Example

```python
from backend.src.pattern_engine.detectors.spring_detector import SpringDetector
from backend.src.models.phase_classification import WyckoffPhase

detector = SpringDetector()

# Detect springs in XYZ
history = detector.detect_all_springs(
    range=xyz_trading_range,
    bars=xyz_bars,
    phase=WyckoffPhase.C
)

# Analyze multi-spring pattern
print(f"Springs detected: {history.spring_count}")  # 3
print(f"Volume trend: {history.volume_trend}")  # RISING ⚠️ WARNING
print(f"Risk level: {history.risk_level}")  # HIGH ⚠️

# Examine volume progression
print("\nVolume Progression (WARNING):")
for i, spring in enumerate(history.springs, 1):
    print(f"Spring {i}: {spring.volume_ratio}x volume")

# Output:
# Spring 1: 0.32x volume (LOWEST)
# Spring 2: 0.52x volume (HIGHER - warning)
# Spring 3: 0.68x volume (HIGHEST - major warning) ⚠️

# Best spring paradox: Spring 1 has lowest volume, but trend is RISING
print(f"\nBest spring (by volume): Spring 1 ({history.best_spring.volume_ratio}x)")
print(f"But volume trend is: {history.volume_trend}")  # RISING ⚠️
print(f"Risk level: {history.risk_level}")  # HIGH ⚠️

# Trade recommendation
if history.risk_level == "HIGH":
    print("\n⚠️ WARNING: Rising volume through springs")
    print("This pattern suggests DISTRIBUTION, not accumulation")
    print("RECOMMENDATION: SKIP this setup or wait for confirmation")
    print("Professional operators do NOT accumulate with RISING volume")
```

### Expected Output

```
Springs detected: 3
Volume trend: RISING ⚠️ WARNING
Risk level: HIGH ⚠️

Volume Progression (WARNING):
Spring 1: 0.32x volume (LOWEST)
Spring 2: 0.52x volume (HIGHER - warning)
Spring 3: 0.68x volume (HIGHEST - major warning) ⚠️

Best spring (by volume): Spring 1 (0.32x)
But volume trend is: RISING ⚠️
Risk level: HIGH ⚠️

⚠️ WARNING: Rising volume through springs
This pattern suggests DISTRIBUTION, not accumulation
RECOMMENDATION: SKIP this setup or wait for confirmation
Professional operators do NOT accumulate with RISING volume
```

### Interpretation (Wyckoff Context)

**RISING Volume = Distribution Warning (Avoid This Setup)**

**Wyckoff Analysis:**
> "Volume INCREASING through springs (0.32x → 0.52x → 0.68x) is NOT professional behavior. This suggests the composite operator is DISTRIBUTING (selling) into each spring, not accumulating. The 'accumulation range' may be a bull trap. Markup is UNLIKELY."

**Why This is Bearish:**
1. **Spring 1 (0.32x)**: Good start, low volume
2. **Spring 2 (0.52x)**: Volume RISES (warning sign) ⚠️
3. **Spring 3 (0.68x)**: Volume HIGHEST (major red flag) ⚠️

**Professional accumulation requires DECLINING volume**. Rising volume suggests:
- Supply is NOT being absorbed
- Sellers are becoming MORE aggressive
- Distribution disguised as accumulation
- Likely breakdown below Creek (not markup)

**Trade Recommendation:**
- **Risk Level**: HIGH ⚠️
- **Action**: **SKIP** this setup entirely
- **Alternative**: Wait for new accumulation range with proper declining volume

---

## 4. Risk Assessment Interpretation

### Risk Levels

| Risk Level | Single Spring | Multi-Spring | Wyckoff Interpretation | Trade Action |
|------------|---------------|--------------|------------------------|--------------|
| **LOW** | Volume <0.3x | DECLINING trend | Professional accumulation complete | **STRONG BUY** |
| **MODERATE** | Volume 0.3-0.7x | STABLE trend | Acceptable accumulation | BUY (monitor) |
| **HIGH** | Volume ≥0.7x | RISING trend | Distribution warning | **AVOID** |

### Code Examples

```python
# Example 1: LOW risk (single spring, ultra-low volume)
history = detector.detect_all_springs(range, bars, WyckoffPhase.C)
assert history.spring_count == 1
assert history.best_spring.volume_ratio < Decimal("0.3")
assert history.risk_level == "LOW"
# Trade: STRONG BUY ✅

# Example 2: LOW risk (multi-spring, declining volume)
history = detector.detect_all_springs(range, bars, WyckoffPhase.C)
assert history.spring_count == 3
assert history.volume_trend == "DECLINING"
assert history.risk_level == "LOW"
# Trade: STRONG BUY ✅ (professional pattern)

# Example 3: MODERATE risk (single spring, moderate volume)
history = detector.detect_all_springs(range, bars, WyckoffPhase.C)
assert history.spring_count == 1
assert Decimal("0.3") <= history.best_spring.volume_ratio <= Decimal("0.7")
assert history.risk_level == "MODERATE"
# Trade: BUY (acceptable, monitor)

# Example 4: HIGH risk (multi-spring, rising volume)
history = detector.detect_all_springs(range, bars, WyckoffPhase.C)
assert history.spring_count == 3
assert history.volume_trend == "RISING"
assert history.risk_level == "HIGH"
# Trade: AVOID ⚠️ (distribution warning)
```

---

## 5. Volume Trend Analysis

### Trend Types

| Trend | Description | Calculation | Wyckoff Meaning |
|-------|-------------|-------------|-----------------|
| **DECLINING** | Volume decreases >15% | 2nd half avg < 1st half avg by >15% | Professional accumulation ✅ |
| **STABLE** | Volume changes ±15% | Within ±15% threshold | Neutral pattern |
| **RISING** | Volume increases >15% | 2nd half avg > 1st half avg by >15% | Distribution warning ⚠️ |

### Code Example

```python
from backend.src.pattern_engine.detectors.spring_detector import analyze_volume_trend
from backend.src.models.spring import Spring
from decimal import Decimal

# Example 1: DECLINING trend (4 springs)
spring1 = Spring(..., volume_ratio=Decimal("0.6"))
spring2 = Spring(..., volume_ratio=Decimal("0.5"))
spring3 = Spring(..., volume_ratio=Decimal("0.4"))
spring4 = Spring(..., volume_ratio=Decimal("0.3"))

trend = analyze_volume_trend([spring1, spring2, spring3, spring4])
print(trend)  # "DECLINING"

# Calculation:
# First half: (0.6 + 0.5) / 2 = 0.55
# Second half: (0.4 + 0.3) / 2 = 0.35
# Change: (0.35 - 0.55) / 0.55 = -36% (>15% decrease = DECLINING ✅)

# Example 2: RISING trend (warning)
spring1 = Spring(..., volume_ratio=Decimal("0.3"))
spring2 = Spring(..., volume_ratio=Decimal("0.4"))
spring3 = Spring(..., volume_ratio=Decimal("0.5"))
spring4 = Spring(..., volume_ratio=Decimal("0.6"))

trend = analyze_volume_trend([spring1, spring2, spring3, spring4])
print(trend)  # "RISING" ⚠️

# Calculation:
# First half: 0.35, Second half: 0.55
# Change: +57% (>15% increase = RISING ⚠️)
```

---

## 6. Best Spring and Signal Selection

### Wyckoff Quality Hierarchy

SpringHistory tracks the **best spring** using Wyckoff quality criteria:

1. **Volume quality** (primary): Lower = better
2. **Penetration depth** (secondary): Deeper = better (more supply absorbed)
3. **Recovery speed** (tiebreaker): Faster = better (stronger demand)

Best **signal** is selected by:
1. **Confidence** (primary): Highest confidence score
2. **Timestamp** (tiebreaker): Most recent signal

### Code Example

```python
detector = SpringDetector()
history = detector.detect_all_springs(range, bars, WyckoffPhase.C)

# Best spring: LOWEST volume (Wyckoff primary criterion)
best_spring = history.best_spring
print(f"Best spring volume: {best_spring.volume_ratio}x")  # Lowest of all springs

# If multiple springs have same volume, use penetration depth
# If still tied, use recovery speed

# Best signal: HIGHEST confidence
best_signal = detector.get_best_signal(history)
if best_signal:
    print(f"Best signal confidence: {best_signal.confidence}%")  # Highest confidence
    print(f"Entry: ${best_signal.entry_price}")
    print(f"R-multiple: {best_signal.r_multiple}R")
```

---

## 7. Backward Compatibility (Legacy API)

For existing code using the old `detect()` method, SpringDetector maintains backward compatibility:

### Legacy API

```python
detector = SpringDetector()

# Old API: Returns List[SpringSignal]
signals = detector.detect(range, bars, WyckoffPhase.C)

# Process signals (same as before)
for signal in signals:
    print(f"Entry: ${signal.entry_price}")
    print(f"Confidence: {signal.confidence}%")
```

### Migration Recommendation

**Migrate to new API for full SpringHistory benefits:**

```python
# NEW API (recommended): Returns SpringHistory
history = detector.detect_all_springs(range, bars, WyckoffPhase.C)

# Access all new features
print(f"Spring count: {history.spring_count}")
print(f"Volume trend: {history.volume_trend}")
print(f"Risk level: {history.risk_level}")

# Get signals list (same as legacy API)
signals = history.signals

# Get best signal (enhanced selection logic)
best_signal = detector.get_best_signal(history)
```

---

## 8. Integration with Trading System

### Complete Trading Workflow

```python
from backend.src.pattern_engine.detectors.spring_detector import SpringDetector
from backend.src.models.phase_classification import WyckoffPhase

def process_spring_signals(symbol: str, range, bars, phase):
    """
    Complete spring detection workflow for trading system.
    """
    detector = SpringDetector()

    # Detect all springs
    history = detector.detect_all_springs(range, bars, phase)

    # Log detection results
    print(f"\n{'='*60}")
    print(f"Spring Detection Report: {symbol}")
    print(f"{'='*60}")
    print(f"Springs detected: {history.spring_count}")
    print(f"Volume trend: {history.volume_trend}")
    print(f"Risk level: {history.risk_level}")

    # Risk assessment
    if history.risk_level == "HIGH":
        print(f"\n⚠️ WARNING: HIGH RISK setup")
        print(f"Volume trend: {history.volume_trend} (distribution warning)")
        print(f"RECOMMENDATION: SKIP this setup")
        return None  # Don't trade HIGH risk setups

    # Get best signal
    best_signal = detector.get_best_signal(history)

    if best_signal is None:
        print("\nNo valid signals (no test confirmation or low R-multiple)")
        return None

    # Validate signal quality
    if best_signal.confidence < 75:
        print(f"\nSignal confidence {best_signal.confidence}% below 75% quality threshold")
        print("RECOMMENDATION: Monitor but don't trade yet")
        return None

    # HIGH QUALITY SIGNAL - Ready to trade
    print(f"\n✅ HIGH QUALITY SPRING SIGNAL")
    print(f"Confidence: {best_signal.confidence}%")
    print(f"Entry: ${best_signal.entry_price}")
    print(f"Stop: ${best_signal.stop_loss}")
    print(f"Target: ${best_signal.target_price}")
    print(f"R-multiple: {best_signal.r_multiple}R")
    print(f"Position size: {best_signal.position_size} shares")
    print(f"Risk amount: ${best_signal.risk_amount}")
    print(f"Urgency: {best_signal.urgency}")

    # Wyckoff context
    if history.volume_trend == "DECLINING":
        print(f"\n📊 Wyckoff Analysis: PROFESSIONAL ACCUMULATION")
        print(f"Declining volume through {history.spring_count} springs confirms")
        print(f"composite operator has absorbed supply. Markup imminent.")

    return best_signal

# Usage
signal = process_spring_signals(
    symbol="AAPL",
    range=aapl_range,
    bars=aapl_bars,
    phase=WyckoffPhase.C
)

if signal:
    # Place trade via broker API
    place_spring_trade(signal)
```

---

## Summary

### Key Takeaways

1. **Single Spring Detection**: Use `detect_all_springs()` for complete SpringHistory
2. **Multi-Spring Patterns**:
   - **DECLINING volume** = Professional accumulation (LOW risk) ✅
   - **RISING volume** = Distribution warning (HIGH risk) ⚠️
3. **Best Spring**: Lowest volume (Wyckoff quality hierarchy)
4. **Best Signal**: Highest confidence score
5. **Risk Assessment**: LOW/MODERATE = trade, HIGH = skip
6. **Backward Compatibility**: Legacy `detect()` still works

### Wyckoff Principle

> "Not all springs are equal. A sequence of springs with DECLINING volume proves professional accumulation is complete. Rising volume warns of distribution. Trust the volume trend."

---

**Author**: Story 5.6 - SpringDetector Module Integration
**Date**: 2025-11-06
**Version**: 1.0
