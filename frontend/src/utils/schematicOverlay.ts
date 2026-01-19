/**
 * @fileoverview Schematic Template Overlay Utility - Story 11.5.1 Task 5
 *
 * Provides coordinate scaling and rendering utilities for Wyckoff schematic template overlays.
 * Converts normalized template coordinates (0-100%) to actual chart time/price coordinates
 * and renders templates as dashed line series on Lightweight Charts.
 *
 * Key Capabilities:
 * - Coordinate scaling from percentage to Unix time and price
 * - Template overlay rendering as dashed blue line series
 * - Deviation calculation between actual prices and template
 * - Overlay cleanup and removal
 *
 * @module schematicOverlay
 * @requires lightweight-charts
 * @requires @/types/chart
 */

import type { IChartApi, ISeriesApi, LineData, Time } from 'lightweight-charts'
import type { WyckoffSchematic, ChartBar } from '@/types/chart'
import { toChartTime } from '@/types/chart'

/**
 * Template point in normalized coordinates
 *
 * @interface TemplatePoint
 * @property {number} x_percent - Horizontal position as percentage (0-100%) of time range
 * @property {number} y_percent - Vertical position as percentage (0-100%), where 0 = Creek level, 100 = Ice level
 */
interface TemplatePoint {
  x_percent: number // 0-100%
  y_percent: number // 0-100% (0 = Creek, 100 = Ice)
}

/**
 * Scaled template point in chart coordinates
 *
 * @interface ScaledPoint
 * @property {number} time - Unix timestamp in seconds
 * @property {number} price - Actual price value in dollars
 */
interface ScaledPoint {
  time: number // Unix timestamp
  price: number // Actual price
}

/**
 * Calculate time range from chart bars
 *
 * Extracts the earliest and latest timestamps from the bar array
 * to determine the chart's time range for coordinate scaling.
 *
 * @param {ChartBar[]} bars - Array of OHLCV chart bars
 * @returns {{ start: number; end: number }} Time range with Unix timestamps
 * @returns {number} returns.start - Earliest bar timestamp (first bar)
 * @returns {number} returns.end - Latest bar timestamp (last bar)
 *
 * @example
 * const bars = [
 *   { time: 1640000000, open: 100, high: 110, low: 95, close: 105 },
 *   { time: 1650000000, open: 105, high: 115, low: 100, close: 110 }
 * ]
 * getTimeRange(bars) // => { start: 1640000000, end: 1650000000 }
 */
function getTimeRange(bars: ChartBar[]): { start: number; end: number } {
  if (bars.length === 0) {
    return { start: 0, end: 0 }
  }
  return {
    start: bars[0].time,
    end: bars[bars.length - 1].time,
  }
}

/**
 * Scale template x-coordinate (percentage) to chart time
 *
 * Converts a normalized horizontal position (0-100%) to an actual Unix timestamp
 * within the chart's time range. Uses linear interpolation.
 *
 * @param {number} xPercent - Horizontal position as percentage (0-100%)
 * @param {number} timeStart - Earliest timestamp in chart (Unix seconds)
 * @param {number} timeEnd - Latest timestamp in chart (Unix seconds)
 * @returns {number} Unix timestamp in seconds
 *
 * @example
 * // 50% through a time range from Jan 1 to Jan 11 (10 days)
 * scaleXCoordinate(50, 1640000000, 1640864000)
 * // => 1640432000 (approximately Jan 6, midpoint)
 */
function scaleXCoordinate(
  xPercent: number,
  timeStart: number,
  timeEnd: number
): number {
  const timeRange = timeEnd - timeStart
  return Math.floor(timeStart + (timeRange * xPercent) / 100)
}

/**
 * Scale template y-coordinate (percentage) to chart price
 *
 * Converts a normalized vertical position (0-100%) to an actual price
 * within the trading range. 0% maps to Creek level (bottom), 100% maps to Ice level (top).
 * Uses linear interpolation.
 *
 * @param {number} yPercent - Vertical position as percentage (0-100%)
 * @param {number} creekLevel - Creek level (bottom of trading range) in dollars
 * @param {number} iceLevel - Ice level (top of trading range) in dollars
 * @returns {number} Actual price in dollars
 *
 * @example
 * // 75% up from Creek ($140) to Ice ($160)
 * scaleYCoordinate(75, 140, 160)
 * // => 155 (Creek + 75% of $20 range = $140 + $15 = $155)
 */
function scaleYCoordinate(
  yPercent: number,
  creekLevel: number,
  iceLevel: number
): number {
  const priceRange = iceLevel - creekLevel
  return creekLevel + (priceRange * yPercent) / 100
}

/**
 * Convert template points to chart coordinates
 *
 * Scales an entire Wyckoff schematic template from normalized coordinates (0-100%)
 * to actual chart coordinates (Unix time and price). Each template point's x_percent
 * is mapped to the chart's time range, and y_percent is mapped to the Creek-Ice price range.
 *
 * @param {TemplatePoint[]} template - Array of template points in normalized coordinates
 * @param {ChartBar[]} bars - Chart bars defining the time range
 * @param {number} creekLevel - Creek level (bottom of trading range) in dollars
 * @param {number} iceLevel - Ice level (top of trading range) in dollars
 * @returns {ScaledPoint[]} Array of scaled points with Unix time and actual price
 *
 * @example
 * const template = [
 *   { x_percent: 10, y_percent: 20 },  // PS (Preliminary Support)
 *   { x_percent: 20, y_percent: 5 },   // SC (Selling Climax)
 *   { x_percent: 50, y_percent: 15 }   // Spring
 * ]
 * const bars = [{ time: 1640000000, ... }, { time: 1650000000, ... }]
 * scaleTemplateToChart(template, bars, 140, 160)
 * // => [
 * //   { time: 1641000000, price: 144 },
 * //   { time: 1642000000, price: 141 },
 * //   { time: 1645000000, price: 143 }
 * // ]
 */
export function scaleTemplateToChart(
  template: TemplatePoint[],
  bars: ChartBar[],
  creekLevel: number,
  iceLevel: number
): ScaledPoint[] {
  const { start: timeStart, end: timeEnd } = getTimeRange(bars)

  return template.map((point) => ({
    time: scaleXCoordinate(point.x_percent, timeStart, timeEnd),
    price: scaleYCoordinate(point.y_percent, creekLevel, iceLevel),
  }))
}

/**
 * Calculate deviation between actual price and template price
 *
 * Measures how far the actual price deviates from the expected template price,
 * expressed as a percentage of the trading range. Used to identify significant
 * pattern deviations that may indicate template mismatch.
 *
 * @param {number} actualPrice - Actual bar price (typically close price) in dollars
 * @param {number} templatePrice - Expected template price in dollars
 * @param {number} priceRange - Total price range (Ice - Creek) in dollars
 * @returns {number} Deviation as percentage of price range (0-100+)
 *
 * @example
 * // Actual price $150, template expects $145, range is $20
 * calculateDeviation(150, 145, 20)
 * // => 25.0 (deviation of $5 is 25% of $20 range)
 *
 * @example
 * // Actual price exactly matches template
 * calculateDeviation(145, 145, 20)
 * // => 0.0 (no deviation)
 */
export function calculateDeviation(
  actualPrice: number,
  templatePrice: number,
  priceRange: number
): number {
  const deviation = Math.abs(actualPrice - templatePrice)
  return (deviation / priceRange) * 100 // Percentage deviation
}

/**
 * Find nearest bar to template point time
 *
 * Searches for the chart bar with timestamp closest to the given time.
 * Used for comparing actual prices with template prices at corresponding points.
 * Uses linear search with O(n) complexity.
 *
 * @param {number} time - Target Unix timestamp in seconds
 * @param {ChartBar[]} bars - Array of chart bars to search
 * @returns {ChartBar | null} Nearest bar, or null if bars array is empty
 *
 * @example
 * const bars = [
 *   { time: 1640000000, close: 100, ... },
 *   { time: 1641000000, close: 105, ... },
 *   { time: 1642000000, close: 110, ... }
 * ]
 * findNearestBar(1640500000, bars)
 * // => { time: 1641000000, close: 105, ... } (closest match)
 */
function findNearestBar(time: number, bars: ChartBar[]): ChartBar | null {
  if (bars.length === 0) return null

  let nearest = bars[0]
  let minDiff = Math.abs(bars[0].time - time)

  for (const bar of bars) {
    const diff = Math.abs(bar.time - time)
    if (diff < minDiff) {
      minDiff = diff
      nearest = bar
    }
  }

  return nearest
}

/**
 * Check if template point has significant deviation
 *
 * Determines whether a scaled template point deviates significantly from the actual price
 * at the nearest bar. By default, deviations greater than 5% of the trading range are
 * considered significant, indicating potential template mismatch.
 *
 * @param {ScaledPoint} scaledPoint - Template point in chart coordinates
 * @param {ChartBar[]} bars - Chart bars for finding nearest actual price
 * @param {number} priceRange - Total price range (Ice - Creek) in dollars
 * @param {number} [threshold=5.0] - Deviation threshold as percentage (default: 5%)
 * @returns {boolean} True if deviation exceeds threshold, false otherwise
 *
 * @example
 * const scaledPoint = { time: 1640500000, price: 145 }
 * const bars = [{ time: 1640500000, close: 150, ... }]
 * const priceRange = 20 // Ice $160 - Creek $140
 *
 * hasSignificantDeviation(scaledPoint, bars, priceRange, 5.0)
 * // => true (deviation of $5 is 25% of $20 range, exceeds 5% threshold)
 *
 * @example
 * // With custom threshold
 * hasSignificantDeviation(scaledPoint, bars, priceRange, 30.0)
 * // => false (25% deviation is below 30% threshold)
 */
export function hasSignificantDeviation(
  scaledPoint: ScaledPoint,
  bars: ChartBar[],
  priceRange: number,
  threshold: number = 5.0
): boolean {
  const nearestBar = findNearestBar(scaledPoint.time, bars)
  if (!nearestBar) return false

  // Use close price for comparison
  const deviation = calculateDeviation(
    nearestBar.close,
    scaledPoint.price,
    priceRange
  )

  return deviation > threshold
}

/**
 * Render schematic template overlay on chart
 *
 * Creates a dashed blue line series overlay on the Lightweight Charts instance
 * representing the Wyckoff schematic template. The template is scaled to match
 * the chart's time range (first to last bar) and price range (Creek to Ice levels).
 *
 * **Visual Styling**:
 * - Color: Blue (#3B82F6)
 * - Line width: 2px
 * - Line style: Dashed
 * - No crosshair marker, price line, or last value label
 *
 * @param {IChartApi} chart - Lightweight Charts API instance
 * @param {WyckoffSchematic} schematic - Wyckoff schematic data with template points
 * @param {ChartBar[]} bars - Chart bars defining the time range
 * @param {number} creekLevel - Creek level (bottom of trading range) in dollars
 * @param {number} iceLevel - Ice level (top of trading range) in dollars
 * @returns {ISeriesApi<'Line'> | null} Line series API for template overlay, or null if invalid input
 *
 * @example
 * // Render ACCUMULATION_1 template overlay
 * const schematic = {
 *   schematic_type: 'ACCUMULATION_1',
 *   confidence_score: 85,
 *   template_data: [
 *     { x_percent: 10, y_percent: 20 },
 *     { x_percent: 20, y_percent: 5 },
 *     { x_percent: 50, y_percent: 15 }
 *   ]
 * }
 * const templateSeries = renderSchematicOverlay(
 *   chartInstance,
 *   schematic,
 *   bars,
 *   140, // Creek
 *   160  // Ice
 * )
 * // => Returns line series with dashed blue overlay
 */
export function renderSchematicOverlay(
  chart: IChartApi,
  schematic: WyckoffSchematic,
  bars: ChartBar[],
  creekLevel: number,
  iceLevel: number
): ISeriesApi<'Line'> | null {
  if (!schematic || bars.length === 0) return null

  // Convert template points to chart coordinates
  const scaledPoints = scaleTemplateToChart(
    schematic.template_data as unknown as TemplatePoint[],
    bars,
    creekLevel,
    iceLevel
  )

  // Convert to LineData format for Lightweight Charts
  const lineData: LineData<Time>[] = scaledPoints.map((point) => ({
    time: toChartTime(point.time),
    value: point.price,
  }))

  // Create line series for template
  const templateSeries = chart.addLineSeries({
    color: '#3B82F6', // Blue
    lineWidth: 2,
    lineStyle: 2, // Dashed (LightweightCharts LineStyle enum: 0=Solid, 1=Dotted, 2=Dashed, 3=LargeDashed, 4=SparseDotted)
    crosshairMarkerVisible: false,
    lastValueVisible: false,
    priceLineVisible: false,
    title: `${schematic.schematic_type} Template`,
  })

  // Set template line data
  templateSeries.setData(lineData)

  return templateSeries
}

/**
 * Highlight deviation points on template
 *
 * **NOTE**: Placeholder function for future enhancement.
 *
 * Identifies template points with significant deviations (>5% by default) from actual prices.
 * Lightweight Charts does not support markers on line series directly, so actual marker
 * rendering would require access to the main candlestick series from the parent component.
 *
 * **Future Implementation**:
 * - Filter template points by deviation threshold
 * - Create markers on candlestick series at deviation points
 * - Use distinctive marker shapes (e.g., warning triangles)
 * - Add tooltips explaining the deviation percentage
 *
 * @param {ISeriesApi<'Line'>} templateSeries - Template line series (currently unused)
 * @param {ScaledPoint[]} scaledPoints - Scaled template points in chart coordinates
 * @param {ChartBar[]} bars - Chart bars for deviation calculation
 * @param {number} priceRange - Total price range (Ice - Creek) in dollars
 * @returns {void} Currently does not return or render anything
 *
 * @see hasSignificantDeviation for deviation threshold logic
 * @see calculateDeviation for deviation calculation
 */
/* eslint-disable @typescript-eslint/no-unused-vars */
export function highlightDeviations(
  _templateSeries: ISeriesApi<'Line'>,
  _scaledPoints: ScaledPoint[],
  _bars: ChartBar[],
  _priceRange: number
): void {
  /* eslint-enable @typescript-eslint/no-unused-vars */
  // Lightweight Charts doesn't support markers on line series directly
  // We need to use the main candlestick series for markers
  // This function would need to be called from the chart component
  // with access to the candlestick series
  // For now, we can calculate which points have deviations
  // and return them for the component to render
  // Store deviation points for rendering (would need to be passed back)
  // This is a placeholder - actual implementation would require
  // passing the candlestick series and creating markers
  // const _deviationPoints = scaledPoints.filter((point) =>
  //   hasSignificantDeviation(point, bars, priceRange)
  // )
}

/**
 * Remove schematic overlay from chart
 *
 * Safely removes the template overlay line series from the chart instance.
 * Call this function when toggling overlay visibility off or when switching
 * to a different schematic template.
 *
 * **Usage Pattern**:
 * 1. Store the series returned by `renderSchematicOverlay()` in a ref
 * 2. Call this function to clean up before rendering a new overlay
 * 3. Set the ref to `null` after removal
 *
 * @param {IChartApi} chart - Lightweight Charts API instance
 * @param {ISeriesApi<'Line'> | null} templateSeries - Template line series to remove, or null
 * @returns {void}
 *
 * @example
 * // In Vue component with template overlay
 * const templateSeries = ref<ISeriesApi<'Line'> | null>(null)
 *
 * function updateOverlay() {
 *   // Remove existing overlay
 *   if (templateSeries.value) {
 *     removeSchematicOverlay(chart.value, templateSeries.value)
 *     templateSeries.value = null
 *   }
 *
 *   // Render new overlay
 *   if (chartStore.visibility.schematicOverlay) {
 *     templateSeries.value = renderSchematicOverlay(...)
 *   }
 * }
 */
export function removeSchematicOverlay(
  chart: IChartApi,
  templateSeries: ISeriesApi<'Line'> | null
): void {
  if (templateSeries) {
    chart.removeSeries(templateSeries)
  }
}
