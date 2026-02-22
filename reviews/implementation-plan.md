# Story 25.13 Implementation Plan

## Analysis Summary

### Frontend Expectations
- Endpoint: GET /websocket/messages
- Query parameter: since={sequence_number} (integer)
- Response format: { messages: WebSocketMessage[] }
- Expected behavior: Returns array of messages with sequence_number > since
- Auth: Must use apiClient (includes JWT in Authorization header)

### Current Backend State
- ConnectionManager tracks active connections with sequence numbers
- Each connection has independent sequence counter (per-connection basis)
- send_message() increments sequence per connection before sending
- broadcast() sends to all connections with different sequence numbers
- All emit methods call broadcast() which calls send_message()
- No message persistence or buffering currently exists

### Critical Design Decision: Global vs Per-Connection Sequencing

PROBLEM: Current implementation uses per-connection sequence numbers, but recovery endpoint needs global sequence numbers for cross-connection recovery.

ANALYSIS:
- Current: Connection A gets seq 1,2,3... Connection B gets seq 1,2,3... (independent)
- Needed: Global seq 1,2,3,4,5... (shared across all connections for recovery)
- Frontend reconnection scenario:
  1. Client connects, receives messages with seq 1,2,3
  2. Client disconnects
  3. Server broadcasts messages with global seq 4,5,6
  4. Client reconnects with new connection_id
  5. Client calls /websocket/messages?since=3
  6. Server must return messages 4,5,6 from buffer

DECISION: Add global sequence counter to ConnectionManager alongside existing per-connection counters.

## Implementation Design

### 1. Ring Buffer Structure
Add to ConnectionManager.__init__():
- _message_buffer: deque[tuple[int, float, dict]] with maxlen=500
- _global_sequence: int = 0

Tuple fields:
- int: global sequence number
- float: timestamp (time.time())
- dict: complete message dictionary

### 2. Buffer Population
Modify send_message() to append to buffer after successful send:
- Increment _global_sequence
- Append (global_seq, time.time(), message.copy()) to buffer
- Override sequence_number in buffered copy with global seq

### 3. Recovery Method
Add get_messages_since(since_seq: int) -> list[dict]:
- Filter buffer for seq > since_seq AND timestamp > (now - 900)
- Return list of message dicts

### 4. REST Endpoint
Add to main.py:
- GET /websocket/messages with since query param
- Use get_current_user_id dependency for auth
- Return {"messages": manager.get_messages_since(since)}

### 5. Testing
File: backend/tests/unit/api/test_websocket_recovery.py
- AC1: Endpoint returns 200 with valid auth
- AC2: Returns only messages with seq > since
- AC3: Empty list when no new messages
- AC4: Buffer overflow - 501 messages, only 500 returned
- AC5: TTL enforcement with time.time() mock
- AC7: 401 without auth token

## Files to Modify

1. backend/src/api/websocket.py
   - Add _message_buffer and _global_sequence to __init__
   - Modify send_message() to populate buffer
   - Add get_messages_since() method

2. backend/src/api/main.py
   - Add GET /websocket/messages endpoint
   - Import manager from websocket module

3. backend/tests/unit/api/test_websocket_recovery.py (NEW)
   - All AC test cases

## Edge Cases & Assumptions

Edge Cases Handled:
1. Empty buffer: Returns empty list
2. Buffer overflow: deque maxlen handles automatically
3. TTL edge: Old messages excluded
4. No auth: 401 response
5. since=0: Returns all buffered messages

Assumptions:
1. Global sequence acceptable for frontend
2. Memory usage acceptable (500 messages * 1KB = 500KB max)
3. No persistence needed across restarts
4. Single-user deployment (no per-user filtering)

## Quality Gates

1. Linting: poetry run ruff check src/
2. Formatting: poetry run ruff format --check src/
3. Type checking: poetry run mypy src/
4. Tests: poetry run pytest tests/ -x --cov
5. Coverage: 90%+ on new code

## Next Steps

1. Reviewer approval on this plan
2. Implementer: Execute implementation in worktree
3. QA: Write tests concurrently
4. Adversarial review: Validate ring buffer math and TTL correctness
