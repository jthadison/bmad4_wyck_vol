# Story 25.17 Security Review - WebSocket JWT Authentication

## Review Date
2026-02-22

## Reviewer
Lead Coordinator (Automated Security Review)

## Files Reviewed
- `backend/src/api/websocket.py` - WebSocket endpoint with JWT auth
- `frontend/src/services/websocketService.ts` - Frontend WebSocket client with token
- `backend/tests/unit/api/test_websocket_auth.py` - Authentication tests

## Security Analysis

### 1. Race Condition Analysis: Pool Addition Before Auth
**Status: ✅ SECURE**

**Finding**: The implementation correctly prevents pool addition before authentication completes.

**Evidence**:
```python
# Line 663-705 in websocket.py
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(default=None)) -> None:
    # Accept connection first (WebSocket protocol requirement)
    await websocket.accept()

    # Validate JWT token
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return  # ← CRITICAL: return prevents pool addition

    # Decode and validate token
    payload = decode_access_token(token)
    if payload is None:
        await websocket.close(code=1008, reason="Invalid or expired token")
        return  # ← CRITICAL: return prevents pool addition

    # Token is valid - proceed with connection (pass already_accepted=True)
    connection_id = await manager.connect(websocket, already_accepted=True)
```

**Verification**:
- Every auth failure path calls `return` after `websocket.close()`
- `manager.connect()` is ONLY called after successful token validation
- No code path exists where an unauthenticated client enters the pool
- Tests confirm: `assert len(manager.active_connections) == 0` after auth failure

**Risk**: NONE - Pool addition is gated behind successful authentication.

---

### 2. Token in URL - Logging Exposure
**Status: ⚠️ NOTED (Acceptable Trade-off)**

**Finding**: JWT tokens are passed as query parameters, which may be logged.

**Standard Practice**: Query parameter auth is the standard WebSocket authentication pattern because browser WebSocket clients cannot set custom headers on the initial HTTP upgrade request.

**Exposure Risk**:
- Query params appear in server access logs (nginx, uvicorn)
- Query params may appear in browser history/devtools
- JWT tokens in logs could be replayed if leaked

**Mitigations in Place**:
1. JWTs have expiration times (configured in settings.jwt_access_token_expire_minutes)
2. Local deployment (MVP) - minimal external attack surface
3. Token rotation on refresh (existing auth infrastructure)
4. No alternative exists for browser-based WebSocket auth

**Recommendation for Production**:
- Consider short-lived WebSocket tokens (5-15 min expiry)
- Implement token rotation/refresh for long-lived connections
- Sanitize access logs to redact `?token=` query params
- Use WSS (WebSocket Secure) over TLS in production

**Accepted**: This is a known limitation of WebSocket authentication in browsers. The accept-then-close pattern is correct and standard.

---

### 3. Close Before Pool - Code Path Verification
**Status: ✅ SECURE**

**Finding**: All auth failure paths correctly `return` after `websocket.close()`.

**Code Paths Verified**:
1. **Missing token**:
   ```python
   if not token:
       await websocket.close(code=1008, reason="Authentication required")
       return  # ← Exits function
   ```

2. **Invalid/expired token**:
   ```python
   if payload is None:
       await websocket.close(code=1008, reason="Invalid or expired token")
       return  # ← Exits function
   ```

3. **Valid token** (only path to pool):
   ```python
   connection_id = await manager.connect(websocket, already_accepted=True)
   # ... continues with connection lifecycle
   ```

**Test Coverage**:
- `test_missing_token_closes_connection` - verifies pool empty after missing token
- `test_invalid_token_closes_connection` - verifies pool empty after invalid token
- `test_no_signal_data_sent_to_unauthenticated` - verifies no signal leakage

**Risk**: NONE - Explicit `return` statements prevent execution continuation.

---

### 4. Exception Handling - Auth Failure Edge Cases
**Status: ✅ ROBUST**

**Finding**: Exception handling correctly prevents unintended authentication bypass.

**Current Implementation**:
```python
payload = decode_access_token(token)
if payload is None:
    await websocket.close(code=1008, reason="Invalid or expired token")
    return
```

**Analysis**:
- `decode_access_token()` (from `dependencies.py`) returns `None` on any decode failure
- Includes: expired tokens, invalid signatures, malformed JWTs, missing claims
- No exception types leak through - all failures → `None` → close(1008)

**Edge Cases Tested**:
1. Missing token (`token=None`) - handled
2. Invalid token (bad signature) - handled (returns None)
3. Expired token (exp claim in past) - handled (returns None)
4. Malformed JWT (not parsable) - handled (returns None)

**Potential Risk (Low)**: If `decode_access_token()` raises an unexpected exception (e.g., network error during key fetch in future JWKS implementation), the exception would bubble up and close the connection via FastAPI's exception handler. This is safe (connection closes) but should return 1008 explicitly.

**Recommendation**: Wrap `decode_access_token()` in try/except for defense-in-depth:
```python
try:
    payload = decode_access_token(token)
except Exception as e:
    print(f"[WebSocket] Token decode error: {e}")
    await websocket.close(code=1008, reason="Invalid or expired token")
    return
```

**Accepted for MVP**: Current implementation is safe (None check handles all current failure modes). Future enhancement for JWKS/remote validation.

---

### 5. Token=None Case - Explicit vs Absent Query Param
**Status: ✅ SECURE**

**Finding**: Both missing query param and empty token are correctly rejected.

**Test Cases**:
1. No query param: `/ws` → `token=None` (FastAPI default)
2. Empty query param: `/ws?token=` → `token=""` (falsy, caught by `if not token`)
3. Null value: `/ws?token=null` → `token="null"` (string, fails decode)

**Verification**:
```python
if not token:  # Catches None and ""
    await websocket.close(code=1008, reason="Authentication required")
    return
```

**Risk**: NONE - Both absent and empty tokens trigger the same rejection path.

---

### 6. Frontend Token Availability - Undefined/Null at Connection Time
**Status: ⚠️ EDGE CASE - Graceful Degradation

**Finding**: Frontend gracefully handles missing token.

**Current Implementation** (`websocketService.ts`):
```typescript
const token = localStorage.getItem('auth_token')
if (token) {
  const separator = baseUrl.includes('?') ? '&' : '?'
  return `${baseUrl}${separator}token=${token}`
}
return baseUrl  // ← Connects without token
```

**Risk**: If `auth_token` is not in localStorage, WebSocket connects without token → server closes with 1008 → frontend reconnection loop.

**Observed Behavior**:
- Frontend attempts connection without token
- Backend closes with 1008 "Authentication required"
- Frontend's reconnection logic triggers
- If token never appears, connection never succeeds (correct behavior)

**Recommendation for Production**:
1. Check token presence before initiating WebSocket connection:
   ```typescript
   connect(): void {
     const token = localStorage.getItem('auth_token')
     if (!token) {
       console.warn('[WebSocket] No auth token available, delaying connection')
       this.connectionStatus.value = 'error'
       return
     }
     // ... proceed with connection
   }
   ```

2. Listen for auth state changes and connect only when authenticated:
   ```typescript
   // In auth store or main.ts
   watchEffect(() => {
     if (authStore.isAuthenticated) {
       websocketService.connect()
     } else {
       websocketService.disconnect()
     }
   })
   ```

**Accepted for MVP**: Current behavior is safe (connection fails, no data leaks). Enhancement for user experience in future sprint.

---

### 7. Accept-Then-Close Pattern - WebSocket Protocol Compliance
**Status: ✅ CORRECT**

**Finding**: Accept-then-close-1008 pattern is correct and required by WebSocket spec.

**Why This Pattern**:
1. **WebSocket Handshake**: HTTP upgrade request must complete (101 Switching Protocols) before any WebSocket frames can be sent.
2. **FastAPI Requirement**: `websocket.accept()` must be called before any `send_json()` or `close()` operations.
3. **Close Frame**: Close code 1008 (Policy Violation) and reason are sent as WebSocket close frames, which require an established connection.

**Alternative (Incorrect) Approach**:
```python
# WRONG - Cannot reject at HTTP level after upgrade request
if not token:
    raise HTTPException(401, "Unauthorized")  # ← Does not work for WebSocket
```

**Verification**: This is the standard pattern documented in:
- [RFC 6455 - WebSocket Protocol](https://datatracker.ietf.org/doc/html/rfc6455#section-7.4.1)
- [FastAPI WebSocket docs](https://fastapi.tiangolo.com/advanced/websockets/)
- [Starlette WebSocket docs](https://www.starlette.io/websockets/)

**Risk**: NONE - Pattern is correct and standard.

---

## Summary

### Security Posture: ✅ SECURE

All 6 acceptance criteria are met:
- ✅ AC1: Valid token → connection accepted, client in pool
- ✅ AC2: Missing token → close 1008, not in pool
- ✅ AC3: Invalid/expired token → close 1008, not in pool
- ✅ AC4: No signal data sent to unauthenticated clients
- ✅ AC5: Authenticated clients receive signals normally
- ✅ AC6: Token passed as query parameter (browser limitation)

### Critical Security Properties:
1. **No race condition**: Pool addition is gated behind authentication
2. **No signal leakage**: Unauthenticated clients never enter broadcast pool
3. **Explicit returns**: All auth failure paths exit before pool operations
4. **Correct close codes**: 1008 (Policy Violation) with descriptive reasons
5. **Protocol compliance**: Accept-then-close pattern is correct

### Recommendations for Production (Future Enhancements):
1. ⚠️ Implement short-lived WebSocket tokens (5-15 min expiry)
2. ⚠️ Sanitize access logs to redact `?token=` query params
3. ⚠️ Add try/except around `decode_access_token()` for defense-in-depth
4. ⚠️ Frontend: Delay WebSocket connection until token is available

### Blocking Issues: NONE

All critical security requirements are satisfied. The implementation correctly prevents unauthorized access to signal broadcasts.

---

## Approval

**Security Review**: ✅ APPROVED

**Reviewed By**: Lead Coordinator (Story 25.17)
**Date**: 2026-02-22
**Next Steps**: Proceed with PR creation
