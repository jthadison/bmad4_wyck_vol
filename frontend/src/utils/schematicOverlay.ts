/**
 * Schematic Template Overlay Utility
 * Story 11.5.1 Task 5: Render Wyckoff schematic templates on chart
 *
 * Converts normalized template coordinates to chart coordinates
 * and renders as a line series overlay.
 */

import type { IChartApi, ISeriesApi, LineData } from 'lightweight-charts'
import type { WyckoffSchematic, ChartBar } from '@/types/chart'

/**
 * Template point in normalized coordinates
 */
interface TemplatePoint {
  x_percent: number // 0-100%
  y_percent: number // 0-100% (0 = Creek, 100 = Ice)
}

/**
 * Scaled template point in chart coordinates
 */
interface ScaledPoint {
  time: number // Unix timestamp
  price: number // Actual price
}

/**
 * Calculate time range from bars
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
 * Check if template point has significant deviation (> 5%)
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
    schematic.template_data as TemplatePoint[],
    bars,
    creekLevel,
    iceLevel
  )

  // Convert to LineData format for Lightweight Charts
  const lineData: LineData[] = scaledPoints.map((point) => ({
    time: point.time,
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
 * Creates markers for points with >5% deviation
 */
export function highlightDeviations(
  templateSeries: ISeriesApi<'Line'>,
  scaledPoints: ScaledPoint[],
  bars: ChartBar[],
  priceRange: number
): void {
  // Lightweight Charts doesn't support markers on line series directly
  // We need to use the main candlestick series for markers
  // This function would need to be called from the chart component
  // with access to the candlestick series

  // For now, we can calculate which points have deviations
  // and return them for the component to render
  const deviationPoints = scaledPoints.filter((point) =>
    hasSignificantDeviation(point, bars, priceRange)
  )

  // Store deviation points for rendering (would need to be passed back)
  // This is a placeholder - actual implementation would require
  // passing the candlestick series and creating markers
}

/**
 * Remove schematic overlay from chart
 */
export function removeSchematicOverlay(
  chart: IChartApi,
  templateSeries: ISeriesApi<'Line'> | null
): void {
  if (templateSeries) {
    chart.removeSeries(templateSeries)
  }
}
