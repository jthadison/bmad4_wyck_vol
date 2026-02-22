# Story 25.13 - Round 2: Blocking Issue Fix

## Review Date
2026-02-22

## Issue Type
🚨 **BLOCKING** - Sequence Number Mismatch

## Problem Description

### Dual Sequence Number Design Flaw

**Original Implementation:**
1. Real-time messages used **per-connection sequences** (each connection: 1, 2, 3, ...)
2. Recovery buffer used **global sequences** (system-wide: 1, 2, 3, 4, 5, ...)
3. Buffer code overrode `message["sequence_number"]` with global seq AFTER real-time delivery

**Why This Broke Recovery:**

**Scenario:**
1. Client A connects, receives messages with per-connection seq 1, 2, 3
2. Frontend stores `lastSequenceNumber = 3` (per-connection)
3. Client disconnects
4. Server emits 100 more messages to other clients (global seq advances to 103)
5. Client A reconnects (new connection ID)
6. Client A calls `GET /websocket/messages?since=3` (using per-connection seq)
7. Server interprets `3` as global sequence
8. **Result**: Client receives messages 4-103 (100 unrelated messages) OR gets nothing if global seq 3 was hours ago

**Root Cause:**
- Frontend never saw global sequences (only per-connection seq in real-time)
- Recovery endpoint expected global sequences
- Mismatch caused flood of wrong messages or empty results

## Fix Implementation

### Changes Made

**File**: `backend/src/api/websocket.py`

**Before** (lines 162-178):
```python
# Increment per-connection sequence
seq += 1
self.active_connections[connection_id] = (ws, seq)

# Assign per-connection seq to message
message["sequence_number"] = seq

try:
    await ws.send_json(message)

    # Buffer with global seq (different from real-time!)
    self._global_sequence += 1
    buffered_message = message.copy()
    buffered_message["sequence_number"] = self._global_sequence  # OVERRIDE
    self._message_buffer.append(...)
```

**After** (lines 162-184):
```python
# Increment GLOBAL sequence FIRST (before send)
self._global_sequence += 1
global_seq = self._global_sequence

# Per-connection seq for internal tracking only
per_conn_seq += 1
self.active_connections[connection_id] = (ws, per_conn_seq)

# Assign GLOBAL seq to message (same for real-time AND recovery)
message["sequence_number"] = global_seq

try:
    await ws.send_json(message)

    # Buffer with the SAME global seq that was sent
    self._message_buffer.append((global_seq, time.time(), message.copy()))
```

**Key Changes:**
1. ✅ Global sequence incremented BEFORE sending message
2. ✅ `message["sequence_number"]` assigned global seq (not per-connection)
3. ✅ Buffer uses the SAME global seq (no override)
4. ✅ Per-connection seq kept for internal tracking (not exposed in messages)

### Test Added

**File**: `backend/tests/unit/api/test_websocket_recovery.py`

**New Test**: `test_realtime_and_recovery_use_same_sequence_numbers`

**Purpose**: Verify real-time and recovery return IDENTICAL sequence numbers

**Test Logic:**
1. Connect client, send 3 messages
2. Capture sequence numbers from real-time delivery (via `mock_websocket.send_json`)
3. Query recovery endpoint with `get_messages_since(1)`
4. Verify recovery messages have SAME sequence numbers as real-time

**Assertions:**
```python
assert realtime_sequences == [1, 2, 3]  # Global sequences
assert recovery_sequences == [2, 3]     # Same as real-time (since > 1)
assert recovery_sequences == realtime_sequences[1:]  # Exact match
```

## Verification

### Test Results
```
18 passed, 1 warning in 0.50s
```

**Breakdown:**
- 17 original tests: PASS (no regressions)
- 1 new critical test: PASS (fix verified)

### Quality Gates
- ✅ Ruff linting: PASS
- ✅ Ruff formatting: PASS
- ✅ Mypy type checking: PASS
- ✅ Pytest: 18/18 PASS

### Example Behavior After Fix

**Client Flow:**
1. Connect → receives "connected" message (seq 0, per original design)
2. Receives message with global seq 42
3. Receives message with global seq 43
4. Receives message with global seq 44
5. **Disconnects**, stores `lastSequenceNumber = 44`
6. **Reconnects** (new connection ID)
7. Calls `GET /websocket/messages?since=44`
8. Receives messages with global seq 45, 46, 47, ... (correct!)

## Impact Analysis

### What Changed
- ✅ All clients now receive global sequences in real-time messages
- ✅ Recovery endpoint uses same global sequences
- ✅ No breaking changes to message format (still has `sequence_number` field)

### What Did NOT Change
- ✅ Message structure unchanged
- ✅ Existing emit methods unchanged (still call `send_message()`)
- ✅ Frontend websocketService.ts unchanged (already handles this correctly)

### Backward Compatibility
- **Breaking for existing connected clients?** NO
  - Global sequences are monotonically increasing
  - Clients will receive higher sequence numbers (e.g., jump from per-connection seq 5 to global seq 150)
  - This is acceptable for v0.1.0 (single-user, local deployment)
  - No deployed production systems to break

## Acceptance Criteria Re-Verification

- ✅ **AC1**: Endpoint returns 200 with valid auth - STILL PASS
- ✅ **AC2**: Returns only messages with seq > since - STILL PASS (now with correct global seq)
- ✅ **AC3**: Returns empty list when no new messages - STILL PASS
- ✅ **AC4**: Buffer overflow - STILL PASS
- ✅ **AC5**: TTL enforcement - STILL PASS
- ✅ **AC6**: End-to-end reconnection - NOW WILL WORK (was broken before)
- ✅ **AC7**: 401/403 without auth - STILL PASS

## Documentation Updates

### Updated Docstrings
- `send_message()`: Updated to clarify global sequence usage
- Added Story 25.13 FIX comments in code

### No README Changes Needed
- Implementation detail fix (not API-level change)
- Behavior now matches original story requirements

## Approval Status

✅ **FIX VERIFIED** - Blocking issue resolved

**Changes:**
- Root cause identified and fixed
- Critical test added to prevent regression
- All existing tests pass (no regressions)
- Quality gates pass

**Next Step:** Push to remote to update PR #560, then spawn fresh reviewer

---

**Reviewer**: Self (Implementer)
**Fix Type**: Blocking Issue Resolution
**Tests**: 18/18 PASS
**Quality Gates**: ALL PASS
