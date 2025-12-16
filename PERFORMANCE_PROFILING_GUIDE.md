# Performance Profiling Guide - Story 11.5.1

**Created**: December 15, 2025
**Target**: Story 11.5.1 - Wyckoff Charting Enhancements
**Performance AC**: AC 8 - Render components in < 500ms

---

## Executive Summary

This guide provides step-by-step instructions for profiling frontend performance of the Wyckoff charting components implemented in Story 11.5.1. The acceptance criteria requires all components to render within 500ms on standard hardware.

**Components to Profile**:
- SchematicBadge.vue (modal open performance)
- CauseBuildingPanel.vue (progress bar rendering)
- schematicOverlay.ts (template coordinate scaling)
- PatternChart.vue (overlay rendering + jump line)

---

## Prerequisites

### Hardware Requirements (Standard Test Environment):
- **CPU**: Intel i5 8th gen or equivalent (4+ cores)
- **RAM**: 8GB minimum
- **Browser**: Chrome/Edge 120+ or Firefox 120+
- **Network**: No throttling for initial profiling

### Software Setup:
1. Start frontend dev server: `cd frontend && npm run dev`
2. Open browser to `http://localhost:5173`
3. Navigate to a chart with Wyckoff pattern data
4. Open Chrome DevTools: `F12` or `Ctrl+Shift+I`

---

## Method 1: Chrome DevTools Performance Tab

### Step 1: Open Performance Panel
1. Press `F12` to open DevTools
2. Click **Performance** tab
3. Click the **Settings** gear icon
4. Enable:
   - ☑ **Screenshots**
   - ☑ **CPU throttling: 4x slowdown** (to simulate mid-tier hardware)
   - ☑ **Network throttling: Fast 3G**

### Step 2: Record Component Rendering

#### Scenario A: SchematicBadge Modal Opening
```
1. Click "Record" button (circle icon)
2. Click on SchematicBadge to open modal
3. Wait 2 seconds for modal to fully render
4. Click "Stop" button
```

**Expected Timeline Events**:
- `click` event handler execution
- `showDetails()` function call
- Vue reactivity update (`detailsVisible = true`)
- PrimeVue Dialog component mount
- ProgressBar, Tag components render
- Paint/Composite events

**Performance Target**:
- **Time to Interactive (Modal)**: < 200ms
- **Total Render Time**: < 500ms

#### Scenario B: CauseBuildingPanel Initial Render
```
1. Reload page with Performance panel open
2. Click "Record" immediately
3. Wait for chart page to fully load
4. Click "Stop" after 5 seconds
```

**Expected Timeline Events**:
- API call to `/api/v1/charts/data`
- Response parsing (schematic_match, cause_building)
- Vue component mount (CauseBuildingPanel)
- Progress bar calculation + rendering
- Mini chart histogram rendering

**Performance Target**:
- **Component Mount**: < 100ms
- **Progress Bar Render**: < 50ms
- **Mini Chart (18 bars)**: < 30ms
- **Total**: < 200ms

#### Scenario C: Schematic Overlay Rendering
```
1. Enable "Schematic Overlay" toggle in chart controls
2. Click "Record"
3. Toggle overlay ON
4. Wait 2 seconds
5. Click "Stop"
```

**Expected Timeline Events**:
- `updateSchematicOverlay()` function call
- `scaleTemplateToChart()` coordinate transformation (6-8 template points)
- `renderSchematicOverlay()` Lightweight Charts line series creation
- Canvas paint events

**Performance Target**:
- **Coordinate Scaling**: < 10ms (O(n) where n = 6-8 points)
- **Line Series Creation**: < 50ms
- **Total Overlay Render**: < 100ms

### Step 3: Analyze Results

#### Key Metrics to Check:
1. **Main Thread Blocking**:
   - Look for yellow blocks > 50ms
   - Identify function calls in Call Tree
   - Check for layout thrashing (multiple reflows)

2. **JavaScript Execution Time**:
   - Expand "Main" thread in flame chart
   - Look for `scaleTemplateToChart()`, `renderSchematicOverlay()`, computed properties
   - Measure from function entry to exit

3. **Rendering Performance**:
   - **FP (First Paint)**: Time to first pixel rendered
   - **FCP (First Contentful Paint)**: Time to first content visible
   - **LCP (Largest Contentful Paint)**: Modal or panel fully visible
   - **TBT (Total Blocking Time)**: Sum of long tasks > 50ms

4. **Memory Usage**:
   - Check for memory leaks (saw-tooth pattern in Memory panel)
   - Verify overlay cleanup when toggled off
   - Check modal cleanup when closed

#### How to Read the Flame Chart:
- **Top-down**: Earlier events at top, later events at bottom
- **Width**: Duration of function execution
- **Color**:
  - Yellow: JavaScript execution
  - Purple: Rendering/Layout
  - Green: Painting
  - Gray: System/Other

### Step 4: Identify Performance Bottlenecks

**Common Issues & Solutions**:

| Issue | Symptom | Solution |
|-------|---------|----------|
| Long computed property calculation | Yellow block in `schematicLabel`, `expectedSequence` | Memoize with Vue `computed()` (already done) |
| Excessive DOM updates | Multiple purple "Layout" blocks | Batch updates, use `v-show` instead of `v-if` |
| Template scaling slow | `scaleTemplateToChart()` > 10ms | Already O(n), ensure no nested loops |
| Progress bar re-render | Multiple ProgressBar paint events | Add `key` attribute, avoid prop mutations |
| Mini chart flickering | Rapid "Composite Layers" events | Use CSS transitions, debounce updates |

---

## Method 2: Vue DevTools Performance

### Step 1: Install Vue DevTools
1. Install [Vue DevTools browser extension](https://devtools.vuejs.org/)
2. Open DevTools → **Vue** tab
3. Click **Performance** sub-tab

### Step 2: Record Component Lifecycle

#### Profiling SchematicBadge:
```
1. Click "Start Recording"
2. Click SchematicBadge to open modal
3. Click "Stop Recording"
4. View Component Timeline
```

**Metrics to Check**:
- **Mount Time**: Time from component creation to DOM insertion
- **Update Time**: Time for reactivity updates (detailsVisible change)
- **Computed Properties**: Execution time for 7 computed props
  - `schematicLabel`, `schematicIcon`, `confidenceClass`
  - `modalTitle`, `schematicDescription`
  - `expectedSequence`, `interpretationGuide`

**Performance Target**:
- Each computed property: < 1ms
- Total computed execution: < 10ms
- Mount time: < 50ms

#### Profiling CauseBuildingPanel:
```
1. Reload page with Vue DevTools open
2. Click "Start Recording"
3. Let page load
4. Click "Stop Recording"
5. Filter by "CauseBuildingPanel" component
```

**Metrics to Check**:
- **Render Count**: Should be 1 for initial load
- **Computed Properties**: `statusBadge`, `statusSeverity`, `progressBarClass`
- **Watcher Triggers**: Check if unnecessary re-renders occur

**Performance Target**:
- Computed properties: < 2ms total
- No unnecessary re-renders (render count = 1)

---

## Method 3: Lighthouse Audit

### Step 1: Run Lighthouse
1. Open Chrome DevTools
2. Click **Lighthouse** tab
3. Select:
   - ☑ **Performance**
   - ☑ **Accessibility** (verify ARIA labels)
   - Device: **Desktop**
   - Throttling: **Simulated throttling**
4. Click **Analyze page load**

### Step 2: Review Metrics

**Target Scores** (Story 11.5.1 components):
- **Performance**: 90+ (overall page)
- **Accessibility**: 95+ (ARIA labels should boost score)
- **First Contentful Paint**: < 1.5s
- **Time to Interactive**: < 3.5s
- **Speed Index**: < 3.0s

**Component-Specific Diagnostics**:
- Check "Avoid enormous network payloads" - API response size
- Check "Minimize main-thread work" - JavaScript execution time
- Check "Reduce JavaScript execution time" - Identify slow functions

---

## Method 4: Manual Timing with Performance API

### Add Timing Code to Components

#### Example: Measure `scaleTemplateToChart()` Performance

```typescript
// In schematicOverlay.ts
export function scaleTemplateToChart(
  template: TemplatePoint[],
  bars: ChartBar[],
  creekLevel: number,
  iceLevel: number
): ScaledPoint[] {
  performance.mark('scale-template-start')

  const { start: timeStart, end: timeEnd } = getTimeRange(bars)

  const scaledPoints = template.map((point) => ({
    time: scaleXCoordinate(point.x_percent, timeStart, timeEnd),
    price: scaleYCoordinate(point.y_percent, creekLevel, iceLevel),
  }))

  performance.mark('scale-template-end')
  performance.measure(
    'scale-template',
    'scale-template-start',
    'scale-template-end'
  )

  const measure = performance.getEntriesByName('scale-template')[0]
  console.log(`scaleTemplateToChart: ${measure.duration.toFixed(2)}ms`)

  return scaledPoints
}
```

#### Example: Measure Modal Open Performance

```typescript
// In SchematicBadge.vue
function showDetails() {
  if (props.schematic) {
    performance.mark('modal-open-start')
    detailsVisible.value = true

    nextTick(() => {
      performance.mark('modal-open-end')
      performance.measure('modal-open', 'modal-open-start', 'modal-open-end')

      const measure = performance.getEntriesByName('modal-open')[0]
      console.log(`Modal open time: ${measure.duration.toFixed(2)}ms`)
    })
  }
}
```

### View Results
1. Open Console tab
2. Click badge or toggle overlay
3. Read timing output

**Expected Console Output**:
```
scaleTemplateToChart: 2.34ms  ✅ (Target: < 10ms)
Modal open time: 142.67ms     ✅ (Target: < 200ms)
```

---

## Optimization Strategies

### If Components Exceed 500ms Target:

#### 1. Debounce Overlay Rendering (300ms)
```typescript
// In PatternChart.vue
import { debounce } from 'lodash-es'

const updateSchematicOverlayDebounced = debounce(updateSchematicOverlay, 300)

watch(
  () => chartStore.visibility.schematicOverlay,
  () => updateSchematicOverlayDebounced()
)
```

#### 2. Memoize Pattern Sequences
```typescript
// In SchematicBadge.vue (already using computed, verify no redundant calls)
const expectedSequence = computed(() => {
  if (!props.schematic) return []

  // Memoized by Vue's computed() - only recalculates when schematic changes
  return sequences[props.schematic.schematic_type] || []
})
```

#### 3. Lazy Load Modal Content
```typescript
// In SchematicBadge.vue
const loadModalContent = ref(false)

function showDetails() {
  if (props.schematic) {
    detailsVisible.value = true

    // Defer heavy content rendering
    setTimeout(() => {
      loadModalContent.value = true
    }, 0)
  }
}

// In template
<div v-if="loadModalContent" class="schematic-details">
  <!-- Heavy content here -->
</div>
```

#### 4. Virtual Scrolling for Large Pattern Lists
```typescript
// If expectedSequence has > 20 items (unlikely, but future-proof)
import { useVirtualList } from '@vueuse/core'

const { list, containerProps, wrapperProps } = useVirtualList(
  expectedSequence,
  { itemHeight: 32 }
)
```

#### 5. Optimize Template Scaling (Already O(n), But Verify)
```typescript
// Ensure no nested loops in scaleTemplateToChart()
// Current: O(n) where n = template points (6-8)
// Already optimal ✅
```

---

## Performance Baseline (Before Optimization)

**Expected Performance** (Based on Implementation):

| Component | Operation | Expected Time | Target | Status |
|-----------|-----------|---------------|--------|--------|
| SchematicBadge | Modal open | 100-150ms | < 200ms | ✅ Expected Pass |
| SchematicBadge | Computed props (all 7) | 5-10ms | < 20ms | ✅ Expected Pass |
| CauseBuildingPanel | Initial render | 50-80ms | < 100ms | ✅ Expected Pass |
| CauseBuildingPanel | Progress bar | 10-20ms | < 50ms | ✅ Expected Pass |
| CauseBuildingPanel | Mini chart (18 bars) | 15-25ms | < 30ms | ✅ Expected Pass |
| schematicOverlay | Coordinate scaling | 2-5ms | < 10ms | ✅ Expected Pass |
| schematicOverlay | Line series render | 30-50ms | < 100ms | ✅ Expected Pass |
| PatternChart | Projected jump line | 10-20ms | < 50ms | ✅ Expected Pass |

**Total Page Render** (with Wyckoff components): 250-350ms < 500ms ✅

---

## Reporting Results

### Performance Report Template

```markdown
## Performance Profiling Results - Story 11.5.1

**Date**: [Date]
**Hardware**: [CPU, RAM]
**Browser**: Chrome [Version]
**Test Environment**: Dev server (localhost:5173)

### Methodology
- Chrome DevTools Performance tab
- CPU throttling: 4x slowdown
- Network throttling: Fast 3G
- 5 test runs, median values reported

### Results Summary

| Component | Metric | Measured | Target | Pass/Fail |
|-----------|--------|----------|--------|-----------|
| SchematicBadge | Modal open | XXms | < 200ms | ✅/❌ |
| SchematicBadge | Computed props | XXms | < 20ms | ✅/❌ |
| CauseBuildingPanel | Initial render | XXms | < 100ms | ✅/❌ |
| CauseBuildingPanel | Progress bar | XXms | < 50ms | ✅/❌ |
| schematicOverlay | Coordinate scaling | XXms | < 10ms | ✅/❌ |
| schematicOverlay | Line series render | XXms | < 100ms | ✅/❌ |
| **TOTAL** | **Combined Render** | **XXms** | **< 500ms** | **✅/❌** |

### Bottlenecks Identified
- [List any operations > 50ms]
- [List unnecessary re-renders]
- [List layout thrashing events]

### Optimizations Applied
- [If any optimizations were needed]

### Lighthouse Score
- Performance: XX/100
- Accessibility: XX/100 (ARIA labels verified)

### Conclusion
[Pass/Fail AC 8, summary of results]
```

---

## Automated Performance Testing (Future Enhancement)

### Playwright Performance Test Example

```typescript
// frontend/tests/smoke/wyckoff-performance.spec.ts
import { test, expect } from '@playwright/test'

test('Wyckoff components render within 500ms', async ({ page }) => {
  await page.goto('http://localhost:5173/charts/AAPL')

  // Measure modal open performance
  await page.evaluate(() => performance.mark('modal-start'))
  await page.click('.schematic-badge')
  await page.waitForSelector('.p-dialog', { state: 'visible' })
  const modalTime = await page.evaluate(() => {
    performance.mark('modal-end')
    performance.measure('modal', 'modal-start', 'modal-end')
    return performance.getEntriesByName('modal')[0].duration
  })

  expect(modalTime).toBeLessThan(200) // Modal open < 200ms

  // Measure overlay rendering
  await page.evaluate(() => performance.mark('overlay-start'))
  await page.click('[aria-label="Toggle schematic overlay"]')
  await page.waitForTimeout(100) // Wait for render
  const overlayTime = await page.evaluate(() => {
    performance.mark('overlay-end')
    performance.measure('overlay', 'overlay-start', 'overlay-end')
    return performance.getEntriesByName('overlay')[0].duration
  })

  expect(overlayTime).toBeLessThan(100) // Overlay render < 100ms

  // Total should be well under 500ms
  expect(modalTime + overlayTime).toBeLessThan(500)
})
```

---

## Troubleshooting Common Issues

### Issue 1: Modal Opens Slowly (> 200ms)

**Diagnosis**:
- Check computed property execution time (should be < 10ms total)
- Check PrimeVue Dialog component mount time
- Look for unnecessary data fetching in `showDetails()`

**Fix**:
- Memoize heavy computed properties
- Lazy load modal content
- Preload schematic data on page load

### Issue 2: Progress Bar Re-renders Constantly

**Diagnosis**:
- Check if `causeBuildingData` prop mutates frequently
- Look for watchers triggering on every tick
- Check if parent component re-renders excessively

**Fix**:
- Add `:key` to ProgressBar component
- Use `shallowRef` for causeBuildingData in store
- Debounce data updates from API

### Issue 3: Template Overlay Flickers

**Diagnosis**:
- Check if `updateSchematicOverlay()` called multiple times
- Look for rapid toggle on/off events
- Check if bars array changes frequently

**Fix**:
- Debounce overlay updates (300ms)
- Cache scaled template points
- Only re-scale when template or trading range changes

### Issue 4: Mini Chart Slow with Many Columns

**Diagnosis**:
- Check if `target_column_count` > 50 (unlikely, max is 18)
- Look for excessive DOM manipulation
- Check CSS transitions on chart-bar elements

**Fix**:
- Limit `target_column_count` to 18 (already done)
- Use CSS `will-change` for chart-bar transitions
- Batch DOM updates with `v-for` + `:key`

---

## Next Steps

1. **Run Initial Profile**: Follow Method 1 (Chrome DevTools) to establish baseline
2. **Document Results**: Fill out Performance Report Template
3. **Identify Bottlenecks**: Note any operations > 50ms
4. **Apply Optimizations**: Use strategies from Optimization section
5. **Re-test**: Verify optimizations meet < 500ms target
6. **Update Documentation**: Add final performance metrics to Story 11.5.1 docs

---

**🤖 Generated with [Claude Code](https://claude.com/claude-code)**

**Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>**
