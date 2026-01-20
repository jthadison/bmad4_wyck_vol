# Story 16.3b: Event Feed & Portfolio Risk Panels

## Story Overview

**Story ID**: STORY-16.3b
**Epic**: Epic 16 - Advanced Analytics & Integration
**Status**: Ready for Review
**Priority**: Medium
**Story Points**: 4
**Estimated Hours**: 4-5 hours

## User Story

**As an** Active Trader
**I want** live event feed and portfolio risk panels
**So that** I can see recent campaign events and current risk exposure

## Acceptance Criteria

### Functional Requirements

1. **Event Feed Panel**
   - [x] Display live campaign events
   - [x] Filter by event type
   - [x] Timestamp display (relative time)
   - [x] Auto-scroll to latest
   - [x] Event detail popup

2. **Portfolio Risk Panel**
   - [x] Display portfolio heat percentage
   - [x] Show correlation summary
   - [x] Alert badge when heat > 80%
   - [x] Color-coded risk levels
   - [x] Drill-down into details

3. **Connection Status**
   - [x] Connection status indicator (existing ConnectionStatus.vue)
   - [x] Reconnecting state display
   - [x] Disconnected warning

### Technical Requirements

4. **Implementation**
   - [x] `EventFeedPanel.vue` component
   - [x] `PortfolioRiskPanel.vue` component
   - [x] `ConnectionStatusBar.vue` component (using existing ConnectionStatus.vue)
   - [x] Event filtering logic

5. **Test Coverage**
   - [x] Component tests (Vitest) - 46 tests passing
   - [ ] E2E tests (Playwright) - Not required for MVP
   - [x] Maintain test standards

### Non-Functional Requirements

6. **Usability**
   - [x] Responsive design
   - [x] Intuitive navigation
   - [ ] Keyboard shortcuts - Deferred to future enhancement

## Dependencies

**Requires**: Story 16.3a (Dashboard Infrastructure)

## Definition of Done

- [x] Event feed operational
- [x] Portfolio risk panel showing data
- [x] Connection status indicator working
- [x] All tests passing (66 tests in campaigns/ directory)
- [ ] Code reviewed

---

## Dev Agent Record

### Agent Model Used
Claude Opus 4.5 (claude-opus-4-5-20251101)

### File List

**New Files Created:**
- `frontend/src/components/campaigns/EventFeedPanel.vue` - Live event feed with filtering
- `frontend/src/components/campaigns/PortfolioRiskPanel.vue` - Portfolio risk display
- `frontend/tests/components/campaigns/EventFeedPanel.spec.ts` - 21 tests
- `frontend/tests/components/campaigns/PortfolioRiskPanel.spec.ts` - 25 tests

**Existing Files Verified:**
- `frontend/src/components/ConnectionStatus.vue` - Already implements connection status requirements

### Debug Log References
None required - implementation proceeded without issues.

### Completion Notes
1. **EventFeedPanel.vue**: Implements real-time event feed with WebSocket subscriptions for campaign:created, campaign:updated, campaign:invalidated, signal:new, and pattern_detected events. Features include event filtering by type, relative time display, auto-scroll toggle, event detail popup, and event limiting (max 100 events).

2. **PortfolioRiskPanel.vue**: Displays portfolio heat gauge with color-coded risk levels (low/medium/high/critical), warning badge for heat > 80%, proximity warnings, and drill-down dialogs for campaign risks and correlation summaries. Integrates with existing portfolioStore.

3. **ConnectionStatus.vue**: Existing component already implements all connection status requirements (indicator, reconnecting state, disconnected warning). No new ConnectionStatusBar.vue needed.

4. **Test Coverage**: 46 new tests added (21 for EventFeedPanel, 25 for PortfolioRiskPanel). All 66 tests in campaigns/ directory passing.

### Change Log
| Date | Change | Author |
|------|--------|--------|
| 2026-01-19 | Initial implementation of EventFeedPanel and PortfolioRiskPanel | James (Dev Agent) |
| 2026-01-19 | Added component tests (46 tests) | James (Dev Agent) |
| 2026-01-19 | Fixed TypeScript errors (unused imports, type mismatches) | James (Dev Agent) |

---

**Created**: 2026-01-18
**Split From**: Story 16.3
**Author**: AI Product Owner
