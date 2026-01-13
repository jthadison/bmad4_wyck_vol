# Memory-Related Issues - Implementation Plan

**Project:** BMAD Wyckoff Automated Trading System
**Document Version:** 1.0
**Created:** 2026-01-12
**Status:** Ready for Implementation

---

## Executive Summary

This document provides a detailed implementation plan to address **42 memory-related issues** identified in the code audit. Issues are categorized by severity (Critical, High, Medium, Low) and organized into 4 implementation phases spanning 12 weeks.

### Impact Summary
- **Total Issues:** 42 (12 Critical, 8 High, 15 Medium, 7 Low)
- **Estimated Memory Savings:** 40-50% reduction under typical load
- **Current State:** Backend 500-800MB under load, Frontend 150-300MB active
- **Target State:** Backend 300-500MB under load, Frontend 80-150MB active
- **Implementation Timeline:** 12 weeks (3 months)

---

## Table of Contents

1. [Phase 1: Critical WebSocket & Connection Issues (Week 1-2)](#phase-1-critical-websocket--connection-issues-week-1-2)
2. [Phase 2: Critical Cache & Data Loading Issues (Week 3-4)](#phase-2-critical-cache--data-loading-issues-week-3-4)
3. [Phase 3: High Severity Issues (Week 5-8)](#phase-3-high-severity-issues-week-5-8)
4. [Phase 4: Medium Severity Issues (Week 9-12)](#phase-4-medium-severity-issues-week-9-12)
5. [Low Severity Issues (Backlog)](#low-severity-issues-backlog)
6. [Testing Strategy](#testing-strategy)
7. [Monitoring & Validation](#monitoring--validation)
8. [Rollback Plan](#rollback-plan)

---

## Phase 1: Critical WebSocket & Connection Issues (Week 1-2)

**Goal:** Fix connection leaks and unbounded growth in real-time communication layer

### Issue C1: WebSocket Connection Leak (Backend)

**File:** `backend/src/api/websocket.py`
**Lines:** 84, 103, 529-547
**Severity:** Critical
**Estimated Effort:** 6 hours

#### Current Code Problem
```python
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, tuple[WebSocket, int]] = {}
        # No cleanup mechanism for stale connections
```

#### Implementation Steps

1. **Add Connection Tracking with Timestamp** (2 hours)
   ```python
   from datetime import datetime, timedelta
   from typing import Optional

   class ConnectionManager:
       def __init__(self):
           # Store: user_id -> (websocket, sequence, last_activity_time)
           self.active_connections: dict[str, tuple[WebSocket, int, datetime]] = {}
           self._cleanup_task: Optional[asyncio.Task] = None
           self._stale_timeout_seconds = 300  # 5 minutes

       async def connect(self, websocket: WebSocket, user_id: str):
           await websocket.accept()
           sequence = self.active_connections.get(user_id, (None, 0, None))[1] + 1
           self.active_connections[user_id] = (websocket, sequence, datetime.now())
           logger.info(f"WebSocket connected: {user_id}, sequence: {sequence}")

           # Start cleanup task if not running
           if self._cleanup_task is None or self._cleanup_task.done():
               self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

       async def update_activity(self, user_id: str):
           """Update last activity timestamp for heartbeat"""
           if user_id in self.active_connections:
               ws, seq, _ = self.active_connections[user_id]
               self.active_connections[user_id] = (ws, seq, datetime.now())
   ```

2. **Implement Periodic Cleanup Task** (2 hours)
   ```python
   async def _periodic_cleanup(self):
       """Remove stale connections every 60 seconds"""
       while True:
           try:
               await asyncio.sleep(60)  # Check every minute
               await self._cleanup_stale_connections()
           except asyncio.CancelledError:
               break
           except Exception as e:
               logger.error(f"Error in cleanup task: {e}")

   async def _cleanup_stale_connections(self):
       """Remove connections with no activity in last N seconds"""
       now = datetime.now()
       stale_threshold = timedelta(seconds=self._stale_timeout_seconds)
       stale_users = []

       for user_id, (ws, seq, last_activity) in self.active_connections.items():
           if now - last_activity > stale_threshold:
               stale_users.append(user_id)
               try:
                   await ws.close(code=1000, reason="Connection timeout")
               except Exception as e:
                   logger.warning(f"Error closing stale connection {user_id}: {e}")

       for user_id in stale_users:
           del self.active_connections[user_id]
           logger.info(f"Removed stale connection: {user_id}")

       if stale_users:
           logger.info(f"Cleanup: removed {len(stale_users)} stale connections")
   ```

3. **Add Heartbeat/Ping-Pong Mechanism** (2 hours)
   ```python
   async def send_ping(self, user_id: str):
       """Send ping to client, update activity on pong"""
       if user_id in self.active_connections:
           ws, _, _ = self.active_connections[user_id]
           try:
               await ws.send_json({"type": "ping", "timestamp": datetime.now().isoformat()})
               await self.update_activity(user_id)
           except Exception as e:
               logger.error(f"Ping failed for {user_id}: {e}")
               await self.disconnect(user_id)

   async def handle_pong(self, user_id: str):
       """Handle pong response from client"""
       await self.update_activity(user_id)
   ```

4. **Update WebSocket Endpoint** (30 minutes)
   ```python
   @router.websocket("/ws")
   async def websocket_endpoint(websocket: WebSocket):
       user_id = await authenticate_websocket(websocket)
       await manager.connect(websocket, user_id)

       try:
           while True:
               data = await websocket.receive_json()

               # Handle pong responses
               if data.get("type") == "pong":
                   await manager.handle_pong(user_id)
               else:
                   # Process normal messages
                   await process_message(user_id, data)
       except WebSocketDisconnect:
           await manager.disconnect(user_id)
       except Exception as e:
           logger.error(f"WebSocket error for {user_id}: {e}")
           await manager.disconnect(user_id)
   ```

5. **Add Shutdown Cleanup** (30 minutes)
   ```python
   async def shutdown(self):
       """Cleanup on application shutdown"""
       if self._cleanup_task and not self._cleanup_task.done():
           self._cleanup_task.cancel()
           try:
               await self._cleanup_task
           except asyncio.CancelledError:
               pass

       # Close all remaining connections
       for user_id in list(self.active_connections.keys()):
           await self.disconnect(user_id)
   ```

#### Testing Requirements
- [ ] Unit test: Connection tracked with timestamp
- [ ] Unit test: Stale connections removed after timeout
- [ ] Integration test: Heartbeat keeps connection alive
- [ ] Integration test: No heartbeat causes cleanup
- [ ] Load test: 100 concurrent connections with reconnects
- [ ] Memory test: No growth over 1-hour soak test

#### Success Criteria
- Active connections dictionary size remains stable over time
- Stale connections removed within 6 minutes (5min timeout + 1min cleanup interval)
- Memory usage stable at 50-100KB per active connection
- No connection leaks in 24-hour soak test

---

### Issue C2: Message Buffer Unbounded Growth (Frontend)

**File:** `frontend/src/services/websocketService.ts`
**Lines:** 72, 154, 266
**Severity:** Critical
**Estimated Effort:** 4 hours

#### Current Code Problem
```typescript
class WebSocketService {
  private messageBuffer: WebSocketMessage[] = []
  // No max size enforcement, grows unbounded during reconnections
}
```

#### Implementation Steps

1. **Add Buffer Size Limits** (1 hour)
   ```typescript
   class WebSocketService {
     private readonly MAX_BUFFER_SIZE = 1000
     private readonly BUFFER_HIGH_WATER_MARK = 800  // 80% threshold for warning
     private messageBuffer: WebSocketMessage[] = []
     private droppedMessageCount = 0

     private addToBuffer(message: WebSocketMessage): void {
       // Check if buffer is at capacity
       if (this.messageBuffer.length >= this.MAX_BUFFER_SIZE) {
         // FIFO eviction: remove oldest message
         const dropped = this.messageBuffer.shift()
         this.droppedMessageCount++

         console.warn(
           `Message buffer full (${this.MAX_BUFFER_SIZE}). ` +
           `Dropped oldest message. Total dropped: ${this.droppedMessageCount}`,
           dropped
         )
       }

       // Warn when approaching capacity
       if (this.messageBuffer.length >= this.BUFFER_HIGH_WATER_MARK) {
         console.warn(
           `Message buffer at ${this.messageBuffer.length}/${this.MAX_BUFFER_SIZE} ` +
           `(${Math.round(this.messageBuffer.length / this.MAX_BUFFER_SIZE * 100)}%)`
         )
       }

       this.messageBuffer.push(message)
     }
   ```

2. **Add Buffer Metrics** (1 hour)
   ```typescript
   interface BufferMetrics {
     currentSize: number
     maxSize: number
     droppedCount: number
     utilizationPercent: number
   }

   public getBufferMetrics(): BufferMetrics {
     return {
       currentSize: this.messageBuffer.length,
       maxSize: this.MAX_BUFFER_SIZE,
       droppedCount: this.droppedMessageCount,
       utilizationPercent: Math.round(
         (this.messageBuffer.length / this.MAX_BUFFER_SIZE) * 100
       )
     }
   }
   ```

3. **Implement Smart Buffer Clearing** (1 hour)
   ```typescript
   private clearBufferOnSuccessfulReconnect(): void {
     const bufferSize = this.messageBuffer.length

     if (bufferSize > 0) {
       console.info(`Clearing ${bufferSize} buffered messages after reconnect`)
       this.messageBuffer = []
       this.droppedMessageCount = 0
     }
   }

   private async flushBuffer(): Promise<void> {
     if (this.messageBuffer.length === 0) return

     console.info(`Flushing ${this.messageBuffer.length} buffered messages`)

     // Process in chunks to avoid blocking
     const CHUNK_SIZE = 50
     while (this.messageBuffer.length > 0) {
       const chunk = this.messageBuffer.splice(0, CHUNK_SIZE)

       for (const message of chunk) {
         try {
           await this.sendMessage(message)
         } catch (error) {
           console.error('Failed to flush buffered message:', error)
           // Re-add failed messages to front of buffer
           this.messageBuffer.unshift(message)
           break
         }
       }

       // Yield to event loop between chunks
       await new Promise(resolve => setTimeout(resolve, 0))
     }
   }
   ```

4. **Add Configuration Options** (1 hour)
   ```typescript
   interface WebSocketConfig {
     maxBufferSize?: number
     bufferStrategy?: 'fifo' | 'priority' | 'discard'
     flushOnReconnect?: boolean
   }

   constructor(config: WebSocketConfig = {}) {
     this.MAX_BUFFER_SIZE = config.maxBufferSize ?? 1000
     this.bufferStrategy = config.bufferStrategy ?? 'fifo'
     this.flushOnReconnect = config.flushOnReconnect ?? true
   }

   private addToBuffer(message: WebSocketMessage): void {
     if (this.bufferStrategy === 'discard' &&
         this.messageBuffer.length >= this.MAX_BUFFER_SIZE) {
       console.warn('Buffer full, discarding new message')
       return
     }

     // ... FIFO or priority logic
   }
   ```

#### Testing Requirements
- [ ] Unit test: Buffer enforces max size (1000 messages)
- [ ] Unit test: FIFO eviction when buffer full
- [ ] Unit test: Buffer metrics accurate
- [ ] Integration test: Buffer cleared on successful reconnect
- [ ] Load test: 5000 messages during 10 reconnects
- [ ] Memory test: Buffer stays under 2MB (1000 × 2KB)

#### Success Criteria
- Buffer never exceeds MAX_BUFFER_SIZE
- Memory usage capped at ~2MB for buffer
- Metrics accurately report buffer state
- No memory leaks during reconnection cycles

---

### Issue C3: Event Subscriber Memory Leak (Frontend)

**File:** `frontend/src/services/websocketService.ts`
**Lines:** 68, 360-367
**Severity:** Critical
**Estimated Effort:** 8 hours

#### Current Code Problem
```typescript
class WebSocketService {
  private subscribers: Map<string, EventHandler[]> = new Map()

  subscribe(event: string, handler: EventHandler): void {
    // Handlers added but never automatically removed
    const handlers = this.subscribers.get(event) || []
    handlers.push(handler)
    this.subscribers.set(event, handlers)
  }
}
```

#### Implementation Steps

1. **Add Subscription Token System** (2 hours)
   ```typescript
   type SubscriptionToken = string

   class WebSocketService {
     private subscribers: Map<string, Map<SubscriptionToken, EventHandler>> = new Map()
     private tokenCounter = 0

     subscribe(event: string, handler: EventHandler): SubscriptionToken {
       const token = `sub_${++this.tokenCounter}_${Date.now()}`

       if (!this.subscribers.has(event)) {
         this.subscribers.set(event, new Map())
       }

       const eventHandlers = this.subscribers.get(event)!
       eventHandlers.set(token, handler)

       console.debug(`Subscribed to ${event}, token: ${token}, total: ${eventHandlers.size}`)

       return token
     }

     unsubscribe(token: SubscriptionToken): boolean {
       for (const [event, handlers] of this.subscribers.entries()) {
         if (handlers.delete(token)) {
           console.debug(`Unsubscribed ${token} from ${event}, remaining: ${handlers.size}`)

           // Clean up empty event maps
           if (handlers.size === 0) {
             this.subscribers.delete(event)
           }

           return true
         }
       }

       console.warn(`Attempted to unsubscribe unknown token: ${token}`)
       return false
     }
   }
   ```

2. **Create Composable for Auto-Cleanup** (2 hours)
   ```typescript
   // frontend/src/composables/useWebSocketSubscription.ts
   import { onUnmounted } from 'vue'
   import { websocketService } from '@/services/websocketService'
   import type { EventHandler } from '@/types/websocket'

   export function useWebSocketSubscription() {
     const subscriptions: SubscriptionToken[] = []

     function subscribe(event: string, handler: EventHandler): SubscriptionToken {
       const token = websocketService.subscribe(event, handler)
       subscriptions.push(token)
       return token
     }

     function unsubscribe(token: SubscriptionToken): void {
       const index = subscriptions.indexOf(token)
       if (index > -1) {
         subscriptions.splice(index, 1)
         websocketService.unsubscribe(token)
       }
     }

     function unsubscribeAll(): void {
       subscriptions.forEach(token => websocketService.unsubscribe(token))
       subscriptions.length = 0
     }

     // Automatic cleanup on component unmount
     onUnmounted(() => {
       if (subscriptions.length > 0) {
         console.debug(`Auto-unsubscribing ${subscriptions.length} subscriptions`)
         unsubscribeAll()
       }
     })

     return {
       subscribe,
       unsubscribe,
       unsubscribeAll
     }
   }
   ```

3. **Add Subscription Monitoring** (2 hours)
   ```typescript
   class WebSocketService {
     private readonly MAX_HANDLERS_PER_EVENT = 50

     subscribe(event: string, handler: EventHandler): SubscriptionToken {
       const token = `sub_${++this.tokenCounter}_${Date.now()}`

       if (!this.subscribers.has(event)) {
         this.subscribers.set(event, new Map())
       }

       const eventHandlers = this.subscribers.get(event)!

       // Warn if approaching limit
       if (eventHandlers.size >= this.MAX_HANDLERS_PER_EVENT - 10) {
         console.warn(
           `High subscriber count for event '${event}': ${eventHandlers.size}. ` +
           `Possible memory leak!`
         )
       }

       // Hard limit to prevent runaway growth
       if (eventHandlers.size >= this.MAX_HANDLERS_PER_EVENT) {
         console.error(
           `Maximum handlers (${this.MAX_HANDLERS_PER_EVENT}) reached for ` +
           `event '${event}'. Rejecting new subscription.`
         )
         throw new Error(`Too many subscribers for event: ${event}`)
       }

       eventHandlers.set(token, handler)
       return token
     }

     getSubscriberCount(event?: string): number | Record<string, number> {
       if (event) {
         return this.subscribers.get(event)?.size ?? 0
       }

       const counts: Record<string, number> = {}
       for (const [evt, handlers] of this.subscribers.entries()) {
         counts[evt] = handlers.size
       }
       return counts
     }
   }
   ```

4. **Update All Components Using WebSocket** (2 hours)
   ```typescript
   // Example: frontend/src/components/SignalDashboard.vue
   <script setup lang="ts">
   import { useWebSocketSubscription } from '@/composables/useWebSocketSubscription'

   const { subscribe } = useWebSocketSubscription()

   // Old (WRONG):
   // websocketService.subscribe('signal_update', handleSignal)

   // New (CORRECT):
   subscribe('signal_update', (data) => {
     console.log('Signal update:', data)
     // Handle signal
   })

   // No need for manual unsubscribe - composable handles it
   </script>
   ```

   **Components to audit and update:**
   - `frontend/src/components/SignalDashboard.vue`
   - `frontend/src/components/LiveMonitor.vue`
   - `frontend/src/components/CampaignList.vue`
   - `frontend/src/components/PatternChart.vue`
   - `frontend/src/views/Dashboard.vue`
   - Any component using `websocketService.subscribe()`

#### Testing Requirements
- [ ] Unit test: Subscribe returns token
- [ ] Unit test: Unsubscribe removes handler
- [ ] Unit test: Multiple subscribes to same event
- [ ] Unit test: Subscription limit enforced
- [ ] Component test: Auto-cleanup on unmount
- [ ] Integration test: No handlers remain after component destroy
- [ ] Memory test: 100 component mount/unmount cycles

#### Success Criteria
- All components use `useWebSocketSubscription` composable
- Subscriber count returns to 0 after all components unmounted
- No warnings about high subscriber counts in normal operation
- Memory stable during component navigation (route changes)

---

### Issue C4: Database Connection Pool Exhaustion

**File:** `backend/src/database.py`
**Lines:** 48-56, 119-123
**Severity:** Critical
**Estimated Effort:** 4 hours

#### Current Code Problem
```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
    # If exception occurs before yield, session may not close properly
```

#### Implementation Steps

1. **Add Robust Session Cleanup** (1 hour)
   ```python
   import contextlib
   from sqlalchemy.exc import SQLAlchemyError

   async def get_db() -> AsyncGenerator[AsyncSession, None]:
       """Database session dependency with robust cleanup"""
       session: Optional[AsyncSession] = None

       try:
           session = async_session_maker()
           yield session
           await session.commit()
       except SQLAlchemyError as e:
           if session:
               await session.rollback()
           logger.error(f"Database error: {e}")
           raise
       except Exception as e:
           if session:
               await session.rollback()
           logger.error(f"Unexpected error in database session: {e}")
           raise
       finally:
           if session:
               await session.close()
               logger.debug("Database session closed")
   ```

2. **Add Session Timeout Configuration** (1 hour)
   ```python
   # Update engine configuration
   engine = create_async_engine(
       DATABASE_URL,
       echo=False,
       pool_size=10,
       max_overflow=10,
       pool_timeout=30,  # Wait 30s for connection from pool
       pool_recycle=3600,  # Recycle connections after 1 hour
       pool_pre_ping=True,  # Verify connection before using
       connect_args={
           "timeout": 30,  # Connection timeout
           "command_timeout": 60,  # Query timeout
       }
   )
   ```

3. **Add Pool Monitoring** (1.5 hours)
   ```python
   from sqlalchemy.pool import Pool
   from sqlalchemy import event
   import time

   # Track connection usage
   connection_metrics = {
       "checked_out": 0,
       "checked_in": 0,
       "pool_size": 0,
       "overflow": 0,
       "checkout_errors": 0
   }

   @event.listens_for(Pool, "connect")
   def receive_connect(dbapi_conn, connection_record):
       """Track new connections"""
       connection_metrics["pool_size"] += 1
       logger.debug(f"New connection created. Pool size: {connection_metrics['pool_size']}")

   @event.listens_for(Pool, "checkout")
   def receive_checkout(dbapi_conn, connection_record, connection_proxy):
       """Track connection checkout"""
       connection_metrics["checked_out"] += 1
       connection_record.checkout_time = time.time()

   @event.listens_for(Pool, "checkin")
   def receive_checkin(dbapi_conn, connection_record):
       """Track connection checkin and duration"""
       connection_metrics["checked_in"] += 1

       if hasattr(connection_record, "checkout_time"):
           duration = time.time() - connection_record.checkout_time
           if duration > 10:  # Warn if held for >10 seconds
               logger.warning(f"Long-lived connection: {duration:.2f}s")

   # Add API endpoint to monitor pool
   @router.get("/health/database")
   async def database_health():
       pool = engine.pool
       return {
           "pool_size": pool.size(),
           "checked_in": pool.checkedin(),
           "checked_out": pool.checkedout(),
           "overflow": pool.overflow(),
           "metrics": connection_metrics
       }
   ```

4. **Add Automatic Session Cleanup Task** (30 minutes)
   ```python
   import asyncio
   from datetime import datetime, timedelta

   class SessionManager:
       def __init__(self):
           self._active_sessions: dict[str, tuple[AsyncSession, datetime]] = {}
           self._cleanup_task: Optional[asyncio.Task] = None

       async def start_cleanup_task(self):
           """Start periodic cleanup of stale sessions"""
           self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

       async def _periodic_cleanup(self):
           """Clean up sessions older than 5 minutes"""
           while True:
               try:
                   await asyncio.sleep(60)  # Check every minute
                   now = datetime.now()
                   stale_sessions = []

                   for session_id, (session, created) in self._active_sessions.items():
                       if now - created > timedelta(minutes=5):
                           stale_sessions.append(session_id)
                           try:
                               await session.close()
                           except Exception as e:
                               logger.error(f"Error closing stale session {session_id}: {e}")

                   for session_id in stale_sessions:
                       del self._active_sessions[session_id]

                   if stale_sessions:
                       logger.warning(f"Cleaned up {len(stale_sessions)} stale sessions")
               except asyncio.CancelledError:
                   break
               except Exception as e:
                   logger.error(f"Error in session cleanup: {e}")
   ```

#### Testing Requirements
- [ ] Unit test: Session closes on normal operation
- [ ] Unit test: Session closes on exception
- [ ] Integration test: Pool doesn't exhaust under load
- [ ] Load test: 50 concurrent requests × 5 seconds
- [ ] Monitor test: Pool metrics endpoint returns data
- [ ] Timeout test: Long query times out properly

#### Success Criteria
- No connection pool exhaustion errors in logs
- Pool metrics show healthy checkin/checkout ratio
- No sessions held longer than 60 seconds
- 503 errors eliminated during normal operation

---

## Phase 2: Critical Cache & Data Loading Issues (Week 3-4)

**Goal:** Fix unbounded cache growth and inefficient data loading

### Issue C7: Chart Data Cache Map Unbounded

**File:** `frontend/src/stores/chartStore.ts`
**Lines:** 44, 112, 252-255
**Severity:** Critical
**Estimated Effort:** 6 hours

#### Implementation Steps

1. **Implement LRU Cache** (3 hours)
   ```typescript
   // frontend/src/utils/LRUCache.ts
   interface CacheEntry<T> {
     data: T
     timestamp: number
     accessCount: number
     lastAccess: number
   }

   export class LRUCache<K, V> {
     private cache: Map<K, CacheEntry<V>>
     private readonly maxSize: number
     private readonly ttlMs: number

     constructor(maxSize = 20, ttlMs = 5 * 60 * 1000) {
       this.cache = new Map()
       this.maxSize = maxSize
       this.ttlMs = ttlMs
     }

     get(key: K): V | undefined {
       const entry = this.cache.get(key)

       if (!entry) return undefined

       // Check TTL
       const now = Date.now()
       if (now - entry.timestamp > this.ttlMs) {
         this.cache.delete(key)
         return undefined
       }

       // Update access tracking
       entry.accessCount++
       entry.lastAccess = now

       return entry.data
     }

     set(key: K, value: V): void {
       const now = Date.now()

       // If at capacity, evict least recently used
       if (this.cache.size >= this.maxSize && !this.cache.has(key)) {
         this.evictLRU()
       }

       this.cache.set(key, {
         data: value,
         timestamp: now,
         accessCount: 1,
         lastAccess: now
       })
     }

     private evictLRU(): void {
       let lruKey: K | undefined
       let lruTime = Infinity

       for (const [key, entry] of this.cache.entries()) {
         if (entry.lastAccess < lruTime) {
           lruTime = entry.lastAccess
           lruKey = key
         }
       }

       if (lruKey !== undefined) {
         console.debug(`LRU eviction: ${String(lruKey)}`)
         this.cache.delete(lruKey)
       }
     }

     clear(): void {
       this.cache.clear()
     }

     size(): number {
       return this.cache.size
     }

     // Proactive cleanup of expired entries
     cleanup(): number {
       const now = Date.now()
       let removed = 0

       for (const [key, entry] of this.cache.entries()) {
         if (now - entry.timestamp > this.ttlMs) {
           this.cache.delete(key)
           removed++
         }
       }

       return removed
     }
   }
   ```

2. **Update Chart Store** (2 hours)
   ```typescript
   // frontend/src/stores/chartStore.ts
   import { LRUCache } from '@/utils/LRUCache'

   export const useChartStore = defineStore('chart', () => {
     const cache = new LRUCache<string, ChartData>(20, 5 * 60 * 1000)
     let cleanupInterval: number | undefined

     // Start periodic cleanup
     onMounted(() => {
       cleanupInterval = window.setInterval(() => {
         const removed = cache.cleanup()
         if (removed > 0) {
           console.debug(`Chart cache cleanup: removed ${removed} expired entries`)
         }
       }, 60 * 1000) // Every minute
     })

     onUnmounted(() => {
       if (cleanupInterval) {
         clearInterval(cleanupInterval)
       }
     })

     async function fetchChartData(symbol: string, timeframe: string) {
       const cacheKey = `${symbol}-${timeframe}`

       // Check cache
       const cached = cache.get(cacheKey)
       if (cached) {
         console.debug(`Cache hit: ${cacheKey}`)
         return cached
       }

       // Fetch from API
       console.debug(`Cache miss: ${cacheKey}`)
       const data = await chartApi.fetchData(symbol, timeframe)

       // Store in cache
       cache.set(cacheKey, data)

       return data
     }

     function clearCache() {
       cache.clear()
       console.info('Chart cache cleared')
     }

     function getCacheStats() {
       return {
         size: cache.size(),
         maxSize: 20
       }
     }

     return {
       fetchChartData,
       clearCache,
       getCacheStats
     }
   })
   ```

3. **Add Cache Monitoring UI** (1 hour)
   ```typescript
   // Add to settings or debug panel
   <template>
     <div class="cache-stats">
       <h3>Chart Cache</h3>
       <div>Size: {{ cacheStats.size }} / {{ cacheStats.maxSize }}</div>
       <div>Usage: {{ cacheUsagePercent }}%</div>
       <button @click="clearCache">Clear Cache</button>
     </div>
   </template>

   <script setup lang="ts">
   import { computed } from 'vue'
   import { useChartStore } from '@/stores/chartStore'

   const chartStore = useChartStore()
   const cacheStats = computed(() => chartStore.getCacheStats())
   const cacheUsagePercent = computed(() =>
     Math.round((cacheStats.value.size / cacheStats.value.maxSize) * 100)
   )

   function clearCache() {
     chartStore.clearCache()
   }
   </script>
   ```

#### Testing Requirements
- [ ] Unit test: LRU eviction works correctly
- [ ] Unit test: TTL expiration removes entries
- [ ] Unit test: Max size enforced (20 entries)
- [ ] Integration test: Cache hit/miss tracking
- [ ] Memory test: Memory stays under 40MB (20 × 2MB)
- [ ] UI test: Cache stats display correctly

#### Success Criteria
- Cache never exceeds 20 entries
- Memory usage caps at ~40MB for chart cache
- LRU eviction works correctly under load
- Expired entries cleaned up within 1 minute

---

### Issue C5: Redis Cache Unbounded Growth

**File:** `backend/src/cache/bar_cache.py`
**Lines:** 220-251
**Severity:** Critical
**Estimated Effort:** 3 hours

#### Implementation Steps

1. **Batch Delete Implementation** (2 hours)
   ```python
   async def clear_all_bars(self, symbol: str) -> int:
       """Clear all cached bars for a symbol with batched deletion"""
       pattern = f"{self.KEY_PREFIX}:{symbol}:*"
       deleted_count = 0
       batch_size = 1000

       try:
           # Use scan_iter to avoid loading all keys at once
           batch = []
           async for key in self.redis.scan_iter(match=pattern, count=100):
               batch.append(key)

               # Delete in batches
               if len(batch) >= batch_size:
                   deleted = await self.redis.delete(*batch)
                   deleted_count += deleted
                   logger.debug(f"Deleted batch of {deleted} keys for {symbol}")
                   batch = []

           # Delete remaining keys
           if batch:
               deleted = await self.redis.delete(*batch)
               deleted_count += deleted

           logger.info(f"Cleared {deleted_count} cached bars for {symbol}")
           return deleted_count

       except Exception as e:
           logger.error(f"Error clearing bars for {symbol}: {e}")
           raise
   ```

2. **Add Pipeline for Bulk Operations** (1 hour)
   ```python
   async def clear_multiple_symbols(self, symbols: list[str]) -> dict[str, int]:
       """Clear cache for multiple symbols efficiently"""
       results = {}

       for symbol in symbols:
           pattern = f"{self.KEY_PREFIX}:{symbol}:*"
           batch = []
           deleted_count = 0

           # Use pipeline for efficiency
           pipe = self.redis.pipeline()

           async for key in self.redis.scan_iter(match=pattern, count=100):
               batch.append(key)

               if len(batch) >= 1000:
                   for key in batch:
                       pipe.delete(key)

                   await pipe.execute()
                   deleted_count += len(batch)
                   batch = []

           # Execute remaining
           if batch:
               for key in batch:
                   pipe.delete(key)
               await pipe.execute()
               deleted_count += len(batch)

           results[symbol] = deleted_count

       return results
   ```

#### Testing Requirements
- [ ] Unit test: Batch deletion works correctly
- [ ] Unit test: Pipeline handles 10K keys
- [ ] Integration test: Memory stable during bulk delete
- [ ] Load test: Clear 100K keys without OOM
- [ ] Performance test: 100K deletes < 10 seconds

#### Success Criteria
- No memory spikes during key deletion
- Batch operations complete without timeout
- Memory usage during deletion < 50MB
- Performance meets requirements (100K/10s)

---

### Issue C9: Backtest Trade Accumulation

**File:** `backend/src/backtesting/engine.py`
**Lines:** 184, 199-201
**Severity:** Critical
**Estimated Effort:** 5 hours

#### Implementation Steps

1. **Implement Streaming Trade Storage** (3 hours)
   ```python
   class BacktestEngine:
       def __init__(
           self,
           repository: BacktestRepository,
           batch_size: int = 100
       ):
           self.repository = repository
           self.batch_size = batch_size

       async def run_backtest(
           self,
           strategy_config: StrategyConfig,
           historical_bars: list[OHLCVBar]
       ) -> BacktestResult:
           """Run backtest with streaming trade persistence"""

           backtest_id = uuid.uuid4()
           trade_batch = []
           total_trades = 0

           # Create backtest record
           await self.repository.create_backtest(backtest_id, strategy_config)

           try:
               for idx, bar in enumerate(historical_bars):
                   # Generate signals and execute trades
                   trades = await self._process_bar(bar, strategy_config)

                   for trade in trades:
                       trade_batch.append(trade)

                       # Flush batch when full
                       if len(trade_batch) >= self.batch_size:
                           await self._flush_trade_batch(backtest_id, trade_batch)
                           total_trades += len(trade_batch)
                           trade_batch = []

                           logger.debug(
                               f"Backtest {backtest_id}: {total_trades} trades persisted, "
                               f"progress: {idx}/{len(historical_bars)} bars"
                           )

               # Flush remaining trades
               if trade_batch:
                   await self._flush_trade_batch(backtest_id, trade_batch)
                   total_trades += len(trade_batch)

               # Calculate metrics from database
               metrics = await self._calculate_metrics(backtest_id)

               return BacktestResult(
                   backtest_id=backtest_id,
                   total_trades=total_trades,
                   metrics=metrics
               )

           except Exception as e:
               logger.error(f"Backtest {backtest_id} failed: {e}")
               await self.repository.mark_failed(backtest_id, str(e))
               raise

       async def _flush_trade_batch(
           self,
           backtest_id: uuid.UUID,
           trades: list[Trade]
       ) -> None:
           """Persist trade batch to database"""
           try:
               await self.repository.insert_trades(backtest_id, trades)
               trades.clear()  # Clear list to free memory
           except Exception as e:
               logger.error(f"Failed to persist trade batch: {e}")
               raise
   ```

2. **Add Streaming Metrics Calculation** (2 hours)
   ```python
   async def _calculate_metrics(self, backtest_id: uuid.UUID) -> BacktestMetrics:
       """Calculate metrics from database without loading all trades"""

       # Use SQL aggregations for efficiency
       metrics = await self.repository.calculate_aggregates(backtest_id)

       return BacktestMetrics(
           total_trades=metrics['trade_count'],
           win_rate=metrics['win_rate'],
           profit_factor=metrics['profit_factor'],
           total_pnl=metrics['total_pnl'],
           max_drawdown=metrics['max_drawdown'],
           sharpe_ratio=await self._calculate_sharpe_streaming(backtest_id)
       )

   async def _calculate_sharpe_streaming(
       self,
       backtest_id: uuid.UUID
   ) -> float:
       """Calculate Sharpe ratio using streaming approach"""

       # Fetch PNL values in chunks
       returns = []
       offset = 0
       chunk_size = 1000

       while True:
           chunk = await self.repository.get_trade_returns(
               backtest_id,
               offset=offset,
               limit=chunk_size
           )

           if not chunk:
               break

           returns.extend(chunk)
           offset += chunk_size

       if not returns:
           return 0.0

       return calculate_sharpe_ratio(returns)
   ```

#### Testing Requirements
- [ ] Unit test: Trade batch flushing
- [ ] Unit test: Metrics calculation from DB
- [ ] Integration test: 10K trade backtest
- [ ] Memory test: Memory stable during long backtest
- [ ] Performance test: Batch insert <100ms

#### Success Criteria
- Memory usage stays under 50MB during backtest
- No trade list accumulation in memory
- Backtest completes without OOM
- Performance acceptable for 10K+ trades

---

### Issue C10: DataFrame Loading Without Chunking

**File:** `backend/src/backtesting/dataset_loader.py`
**Lines:** 75
**Severity:** Critical
**Estimated Effort:** 4 hours

#### Implementation Steps

1. **Implement Chunked Reading** (2 hours)
   ```python
   class DatasetLoader:
       def __init__(self, chunk_size: int = 1000):
           self.chunk_size = chunk_size

       async def load_dataset_chunked(
           self,
           dataset_path: Path,
           filters: Optional[list] = None
       ) -> AsyncIterator[pd.DataFrame]:
           """Load Parquet dataset in chunks"""

           try:
               # Use PyArrow for efficient chunked reading
               import pyarrow.parquet as pq

               parquet_file = pq.ParquetFile(dataset_path)

               # Apply filters if provided
               if filters:
                   row_groups = self._filter_row_groups(parquet_file, filters)
               else:
                   row_groups = range(parquet_file.num_row_groups)

               for i in row_groups:
                   table = parquet_file.read_row_group(i)
                   df = table.to_pandas()

                   logger.debug(
                       f"Loaded row group {i+1}/{len(row_groups)}, "
                       f"rows: {len(df)}"
                   )

                   yield df

                   # Allow other tasks to run
                   await asyncio.sleep(0)

           except Exception as e:
               logger.error(f"Error loading dataset {dataset_path}: {e}")
               raise

       async def load_dataset_filtered(
           self,
           dataset_path: Path,
           symbol: Optional[str] = None,
           start_date: Optional[datetime] = None,
           end_date: Optional[datetime] = None
       ) -> pd.DataFrame:
           """Load dataset with column filters to reduce memory"""

           # Build PyArrow filters
           filters = []
           if symbol:
               filters.append(('symbol', '=', symbol))
           if start_date:
               filters.append(('timestamp', '>=', start_date))
           if end_date:
               filters.append(('timestamp', '<=', end_date))

           # Read with filters - Parquet will skip irrelevant row groups
           df = pd.read_parquet(
               dataset_path,
               filters=filters if filters else None,
               columns=[
                   'timestamp', 'open', 'high', 'low', 'close', 'volume',
                   'pattern_type', 'phase', 'confidence'
               ]  # Only load needed columns
           )

           logger.info(
               f"Loaded {len(df)} rows from {dataset_path.name} "
               f"(filtered: {filters})"
           )

           return df
   ```

2. **Update Accuracy Tester** (2 hours)
   ```python
   class AccuracyTester:
       async def test_pattern_accuracy(
           self,
           dataset_path: Path,
           pattern_type: PatternType
       ) -> AccuracyMetrics:
           """Test accuracy using chunked processing"""

           loader = DatasetLoader(chunk_size=1000)

           true_positives = 0
           false_positives = 0
           false_negatives = 0
           total_processed = 0

           # Process in chunks
           async for chunk in loader.load_dataset_chunked(
               dataset_path,
               filters=[('pattern_type', '=', pattern_type.value)]
           ):
               # Process chunk
               chunk_metrics = await self._process_chunk(chunk)

               true_positives += chunk_metrics.true_positives
               false_positives += chunk_metrics.false_positives
               false_negatives += chunk_metrics.false_negatives
               total_processed += len(chunk)

               logger.debug(
                   f"Processed {total_processed} patterns, "
                   f"TP: {true_positives}, FP: {false_positives}, "
                   f"FN: {false_negatives}"
               )

               # Free chunk memory
               del chunk

           return AccuracyMetrics(
               true_positives=true_positives,
               false_positives=false_positives,
               false_negatives=false_negatives,
               precision=true_positives / (true_positives + false_positives),
               recall=true_positives / (true_positives + false_negatives)
           )
   ```

#### Testing Requirements
- [ ] Unit test: Chunked reading produces same results
- [ ] Unit test: Filtered reading reduces data loaded
- [ ] Integration test: 10K pattern dataset processing
- [ ] Memory test: Peak memory < 100MB
- [ ] Performance test: Chunked vs full load comparison

#### Success Criteria
- Memory usage < 100MB during dataset processing
- Chunked processing produces identical results
- Filters reduce memory proportionally
- No OOM errors with large datasets

---

## Phase 3: High Severity Issues (Week 5-8)

### Issue H1: Pattern Chart Not Disposed

**File:** `frontend/src/components/charts/PatternChart.vue`
**Lines:** 125-127, 200+
**Severity:** High
**Estimated Effort:** 2 hours

#### Implementation Steps

1. **Add Proper Cleanup** (1.5 hours)
   ```typescript
   <script setup lang="ts">
   import { ref, onMounted, onUnmounted, watch } from 'vue'
   import { createChart, IChartApi, ISeriesApi } from 'lightweight-charts'

   const chartContainer = ref<HTMLElement>()
   const chart = ref<IChartApi>()
   const candlestickSeries = ref<ISeriesApi<'Candlestick'>>()
   const volumeSeries = ref<ISeriesApi<'Histogram'>>()

   function initializeChart() {
     if (!chartContainer.value) return

     // Create chart
     chart.value = createChart(chartContainer.value, {
       width: chartContainer.value.clientWidth,
       height: 600,
       // ... other options
     })

     // Create series
     candlestickSeries.value = chart.value.addCandlestickSeries()
     volumeSeries.value = chart.value.addHistogramSeries()
   }

   function cleanupChart() {
     try {
       // Remove series first
       if (candlestickSeries.value && chart.value) {
         chart.value.removeSeries(candlestickSeries.value)
         candlestickSeries.value = undefined
       }

       if (volumeSeries.value && chart.value) {
         chart.value.removeSeries(volumeSeries.value)
         volumeSeries.value = undefined
       }

       // Remove chart
       if (chart.value) {
         chart.value.remove()
         chart.value = undefined
       }

       console.debug('Chart cleaned up successfully')
     } catch (error) {
       console.error('Error cleaning up chart:', error)
     }
   }

   onMounted(() => {
     initializeChart()
   })

   onUnmounted(() => {
     cleanupChart()
   })

   // Also cleanup on route changes
   watch(() => route.path, () => {
     cleanupChart()
   })
   </script>
   ```

2. **Add Resize Observer Cleanup** (30 minutes)
   ```typescript
   const resizeObserver = ref<ResizeObserver>()

   function initializeChart() {
     // ... chart creation

     // Setup resize observer
     resizeObserver.value = new ResizeObserver(entries => {
       if (chart.value && chartContainer.value) {
         chart.value.applyOptions({
           width: chartContainer.value.clientWidth,
           height: chartContainer.value.clientHeight
         })
       }
     })

     resizeObserver.value.observe(chartContainer.value)
   }

   function cleanupChart() {
     // Disconnect resize observer
     if (resizeObserver.value) {
       resizeObserver.value.disconnect()
       resizeObserver.value = undefined
     }

     // ... rest of cleanup
   }
   ```

#### Testing Requirements
- [ ] Component test: Chart disposed on unmount
- [ ] Component test: No memory leak on re-mount
- [ ] Integration test: Navigation doesn't leak charts
- [ ] Memory test: 50 mount/unmount cycles

#### Success Criteria
- Chart references cleared on unmount
- Memory returns to baseline after unmount
- No warnings in console
- ResizeObserver disconnected properly

---

### Issue H2: OHLCV Repository Batch Loading

**File:** `backend/src/repositories/ohlcv_repository.py`
**Lines:** 241-258
**Severity:** High
**Estimated Effort:** 3 hours

#### Implementation Steps

1. **Add Pagination Support** (2 hours)
   ```python
   class OHLCVRepository:
       async def get_bars(
           self,
           symbol: str,
           timeframe: str,
           start: Optional[datetime] = None,
           end: Optional[datetime] = None,
           limit: int = 1000,
           offset: int = 0
       ) -> list[OHLCVBar]:
           """Get OHLCV bars with pagination"""

           stmt = select(OHLCVModel).where(
               OHLCVModel.symbol == symbol,
               OHLCVModel.timeframe == timeframe
           )

           if start:
               stmt = stmt.where(OHLCVModel.timestamp >= start)
           if end:
               stmt = stmt.where(OHLCVModel.timestamp <= end)

           # Add ordering and pagination
           stmt = stmt.order_by(OHLCVModel.timestamp.asc())
           stmt = stmt.limit(limit).offset(offset)

           result = await self.session.execute(stmt)
           models = result.scalars().all()

           bars = [OHLCVBar.model_validate(model) for model in models]

           logger.debug(
               f"Fetched {len(bars)} bars for {symbol} {timeframe} "
               f"(offset: {offset}, limit: {limit})"
           )

           return bars

       async def get_bars_count(
           self,
           symbol: str,
           timeframe: str,
           start: Optional[datetime] = None,
           end: Optional[datetime] = None
       ) -> int:
           """Get total count of bars matching criteria"""

           stmt = select(func.count()).select_from(OHLCVModel).where(
               OHLCVModel.symbol == symbol,
               OHLCVModel.timeframe == timeframe
           )

           if start:
               stmt = stmt.where(OHLCVModel.timestamp >= start)
           if end:
               stmt = stmt.where(OHLCVModel.timestamp <= end)

           result = await self.session.execute(stmt)
           return result.scalar_one()
   ```

2. **Add Streaming Iterator** (1 hour)
   ```python
   async def stream_bars(
       self,
       symbol: str,
       timeframe: str,
       start: Optional[datetime] = None,
       end: Optional[datetime] = None,
       chunk_size: int = 100
   ) -> AsyncIterator[OHLCVBar]:
       """Stream bars in chunks to avoid loading all at once"""

       offset = 0

       while True:
           chunk = await self.get_bars(
               symbol=symbol,
               timeframe=timeframe,
               start=start,
               end=end,
               limit=chunk_size,
               offset=offset
           )

           if not chunk:
               break

           for bar in chunk:
               yield bar

           offset += chunk_size

           # Stop if we got fewer than requested (last chunk)
           if len(chunk) < chunk_size:
               break
   ```

#### Testing Requirements
- [ ] Unit test: Pagination returns correct results
- [ ] Unit test: Count query accurate
- [ ] Integration test: Streaming iteration complete
- [ ] Performance test: Paginated vs full load
- [ ] Memory test: Memory stable during streaming

#### Success Criteria
- Default limit prevents unbounded loading
- Pagination produces same results as full load
- Memory usage proportional to page size
- Streaming handles large datasets efficiently

---

### Issues H3-H8: Additional High Priority Items

Due to space constraints, I'll provide condensed implementation guidance:

**H3: Bar Iterator Fetch Batch** (3 hours)
- Fix `_fetch_batch()` to use SQL LIMIT directly
- Add keyset pagination for true efficiency
- Test with large datasets

**H4: Notification Service History** (2 hours)
- Audit NotificationService implementation
- Add max history size (100 notifications)
- Persist old notifications to database

**H5: Accuracy Tester FP/FN Lists** (2 hours)
- Clear lists after analysis
- Add max size limit (100 cases)
- Optionally stream to file for large sets

**H6: Campaign Store Growth** (3 hours)
- Limit to active campaigns only
- Add pagination for historical campaigns
- Implement cleanup on logout

**H7: Signal Store Accumulation** (3 hours)
- Limit to last 100 signals
- Add time-based expiry (24 hours)
- Implement auto-cleanup task

**H8: BarStore Keyed Map** (3 hours)
- Implement LRU cache (max 10 symbols)
- Clear on session end
- Add memory monitoring

---

## Phase 4: Medium Severity Issues (Week 9-12)

### Priority Medium Issues (M1-M15)

These issues should be addressed systematically over weeks 9-12:

**M1: WebSocket Reconnect Timeout** (1 hour)
- Clear timeout in all code paths
- Add guard against concurrent reconnects

**M2: Event Bus Metrics** (1 hour)
- Reset metrics daily
- Use rolling window counters

**M3: Orchestrator Cache Objects** (2 hours)
- Store lightweight summaries
- Use weak references where appropriate

**M4: Market Data Provider Adapters** (3 hours)
- Audit all adapter implementations
- Ensure proper disconnect cleanup

**M5: Pandas DataFrame Conversions** (2 hours)
- Minimize conversion frequency
- Explicitly delete temporary DataFrames

**M6: Volume Analysis Calculations** (2 hours)
- Profile with tracemalloc
- Use in-place operations
- Delete intermediate arrays

**M7-M15: Remaining Medium Issues** (2-3 hours each)
- Follow patterns established in Critical/High fixes
- Apply similar cleanup and monitoring approaches

---

## Low Severity Issues (Backlog)

**L1-L7** should be addressed opportunistically:
- During related feature work
- As part of performance optimization sprints
- When team has available capacity

These are optimizations rather than fixes and don't pose immediate risk.

---

## Testing Strategy

### Unit Testing
```python
# Example: Test WebSocket connection cleanup
@pytest.mark.asyncio
async def test_stale_connection_cleanup():
    manager = ConnectionManager()
    ws = MockWebSocket()

    await manager.connect(ws, "user_123")

    # Simulate 6 minutes of inactivity
    with freeze_time(datetime.now() + timedelta(minutes=6)):
        await manager._cleanup_stale_connections()

    # Connection should be removed
    assert "user_123" not in manager.active_connections
```

### Integration Testing
```python
# Example: Test backtest streaming persistence
@pytest.mark.asyncio
async def test_backtest_streaming_memory():
    engine = BacktestEngine(batch_size=100)

    # Generate 10K bars
    bars = generate_test_bars(10000)

    # Track memory
    mem_before = get_process_memory()

    result = await engine.run_backtest(strategy, bars)

    mem_after = get_process_memory()
    mem_growth = mem_after - mem_before

    # Memory growth should be minimal (<50MB)
    assert mem_growth < 50 * 1024 * 1024
    assert result.total_trades > 0
```

### Memory Profiling
```python
# Using tracemalloc for Python
import tracemalloc

tracemalloc.start()

# Run operation
await run_operation()

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

for stat in top_stats[:10]:
    print(stat)
```

```typescript
// Using Chrome DevTools for Frontend
// 1. Open DevTools > Memory
// 2. Take heap snapshot before operation
// 3. Perform operation (e.g., navigate routes 50 times)
// 4. Take heap snapshot after
// 5. Compare snapshots - look for:
//    - Detached DOM nodes
//    - Retained listeners
//    - Growing arrays/maps
```

### Load Testing
```python
# Using Locust for API load testing
from locust import HttpUser, task, between

class BacktestUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def run_backtest(self):
        self.client.post("/api/backtest/run", json={
            "symbol": "SPY",
            "timeframe": "1d",
            "start_date": "2020-01-01",
            "end_date": "2023-01-01"
        })
```

### Soak Testing
```bash
# Run system under load for 24 hours
# Monitor memory growth with:
watch -n 60 'ps aux | grep python'
watch -n 60 'docker stats'

# Alert if memory > 80% of available
```

---

## Monitoring & Validation

### Backend Monitoring

```python
# Add Prometheus metrics
from prometheus_client import Gauge, Counter

memory_usage = Gauge('process_memory_bytes', 'Process memory usage')
websocket_connections = Gauge('websocket_active_connections', 'Active WS connections')
db_pool_size = Gauge('db_pool_checked_out', 'DB connections checked out')
cache_size = Gauge('cache_entries', 'Cache entry count', ['cache_name'])

# Update metrics periodically
@app.on_event("startup")
async def start_metrics_collector():
    asyncio.create_task(collect_metrics())

async def collect_metrics():
    while True:
        memory_usage.set(get_process_memory())
        websocket_connections.set(len(manager.active_connections))
        db_pool_size.set(engine.pool.checkedout())
        cache_size.labels(cache_name='chart').set(chart_cache.size())

        await asyncio.sleep(60)
```

### Frontend Monitoring

```typescript
// Monitor memory usage
const monitorMemory = () => {
  if ('memory' in performance) {
    const memory = (performance as any).memory
    console.log({
      usedJSHeapSize: `${Math.round(memory.usedJSHeapSize / 1024 / 1024)}MB`,
      totalJSHeapSize: `${Math.round(memory.totalJSHeapSize / 1024 / 1024)}MB`,
      jsHeapSizeLimit: `${Math.round(memory.jsHeapSizeLimit / 1024 / 1024)}MB`
    })
  }
}

// Run every minute in dev mode
if (import.meta.env.DEV) {
  setInterval(monitorMemory, 60000)
}
```

### Alerting Rules

```yaml
# Prometheus alerting rules
groups:
  - name: memory_alerts
    rules:
      - alert: HighMemoryUsage
        expr: process_memory_bytes > 800000000  # 800MB
        for: 5m
        annotations:
          summary: "Backend memory usage high"

      - alert: WebSocketConnectionLeak
        expr: rate(websocket_active_connections[5m]) > 10
        for: 10m
        annotations:
          summary: "WebSocket connections growing rapidly"

      - alert: DatabasePoolExhaustion
        expr: db_pool_checked_out / db_pool_size > 0.9
        for: 2m
        annotations:
          summary: "Database pool nearly exhausted"
```

---

## Rollback Plan

### Per-Issue Rollback

Each fix should be implemented as a separate PR with:

1. **Feature Flag** (where applicable)
   ```python
   ENABLE_STREAMING_BACKTEST = os.getenv("ENABLE_STREAMING_BACKTEST", "true") == "true"

   if ENABLE_STREAMING_BACKTEST:
       result = await streaming_backtest(...)
   else:
       result = await legacy_backtest(...)
   ```

2. **Git Revert Strategy**
   - Each PR targets single issue
   - Comprehensive testing before merge
   - If issues detected in production, revert single PR
   - Investigate root cause offline

3. **Monitoring-Based Rollback**
   - Set up alerts for memory spikes
   - If alert fires after deployment:
     - Immediate rollback
     - Capture memory dump for analysis
     - Fix and redeploy

### Full Rollback Procedure

```bash
# 1. Identify problematic deployment
git log --oneline

# 2. Revert specific commit
git revert <commit-hash>

# 3. Or revert to previous release
git checkout <previous-release-tag>

# 4. Deploy
git push origin main
./deploy.sh

# 5. Verify rollback successful
curl http://api/health
# Check memory metrics
```

---

## Success Metrics

### Phase 1 Success Criteria (Week 1-2)
- [ ] No WebSocket connection leaks in 24-hour soak test
- [ ] Message buffer never exceeds 1000 entries
- [ ] All components properly unsubscribe on unmount
- [ ] Database pool healthy under load (no exhaustion)
- [ ] Memory reduction: 20-30% from baseline

### Phase 2 Success Criteria (Week 3-4)
- [ ] Chart cache stays under 20 entries
- [ ] Redis batch deletes handle 100K+ keys
- [ ] Backtest memory usage < 50MB
- [ ] DataFrame loading uses < 100MB
- [ ] Memory reduction: 30-40% from baseline

### Phase 3 Success Criteria (Week 5-8)
- [ ] All chart components dispose properly
- [ ] Repository queries use pagination
- [ ] Streaming APIs implemented
- [ ] Store size limits enforced
- [ ] Memory reduction: 40-45% from baseline

### Phase 4 Success Criteria (Week 9-12)
- [ ] All medium issues resolved
- [ ] Monitoring dashboards deployed
- [ ] Alert rules configured
- [ ] Documentation updated
- [ ] Target memory reduction achieved: 40-50%

### Overall Success Criteria
- **Backend idle:** 150-200MB (vs 200-300MB)
- **Backend under load:** 300-500MB (vs 500-800MB)
- **Frontend idle:** 30-50MB (vs 50-100MB)
- **Frontend active:** 80-150MB (vs 150-300MB)
- **Zero critical memory issues** in production
- **24-hour soak test passes** with <5% memory growth

---

## Timeline Summary

| Phase | Duration | Focus | Estimated Effort |
|-------|----------|-------|------------------|
| Phase 1 | Week 1-2 | WebSocket & Connections | 28 hours |
| Phase 2 | Week 3-4 | Cache & Data Loading | 18 hours |
| Phase 3 | Week 5-8 | High Priority Fixes | 32 hours |
| Phase 4 | Week 9-12 | Medium Priority Fixes | 24 hours |
| **Total** | **12 weeks** | **All Issues** | **~102 hours** |

---

## Appendix A: Issue Reference Quick Links

### Critical Issues
- [C1: WebSocket Connection Leak](#issue-c1-websocket-connection-leak-backend)
- [C2: Message Buffer Growth](#issue-c2-message-buffer-unbounded-growth-frontend)
- [C3: Event Subscriber Leak](#issue-c3-event-subscriber-memory-leak-frontend)
- [C4: DB Connection Pool](#issue-c4-database-connection-pool-exhaustion)
- [C5: Redis Cache Growth](#issue-c5-redis-cache-unbounded-growth)
- [C6: Dead Letter Queue](#phase-2-critical-cache--data-loading-issues-week-3-4)
- [C7: Chart Data Cache](#issue-c7-chart-data-cache-map-unbounded)
- [C8: EventBus Handlers](#phase-2-critical-cache--data-loading-issues-week-3-4)
- [C9: Backtest Trades](#issue-c9-backtest-trade-accumulation)
- [C10: DataFrame Loading](#issue-c10-dataframe-loading-without-chunking)
- [C11: Orchestrator Cache](#phase-2-critical-cache--data-loading-issues-week-3-4)
- [C12: Async Task Leak](#phase-2-critical-cache--data-loading-issues-week-3-4)

### High Priority Issues
- [H1: Chart Disposal](#issue-h1-pattern-chart-not-disposed)
- [H2: OHLCV Repository](#issue-h2-ohlcv-repository-batch-loading)
- [H3-H8: Additional High](#issues-h3-h8-additional-high-priority-items)

---

## Appendix B: Memory Estimation Formulas

### Backend
- **WebSocket connection:** ~1-5MB each (websocket + buffers)
- **Database session:** ~500KB-1MB each
- **Trading range cache entry:** ~50-100KB (with 200 bars)
- **Trade object:** ~2KB each
- **OHLCV bar:** ~500 bytes each
- **Pandas DataFrame row:** ~1-2KB (depends on columns)

### Frontend
- **Chart instance:** ~5-10MB (canvas + series data)
- **WebSocket message:** ~1-2KB each
- **Event handler:** ~1-10KB (depends on closure)
- **Cache entry (chart data):** ~500KB-2MB (500 bars + patterns)
- **Vue component instance:** ~10-50KB (depends on state)

---

## Appendix C: Tools & Resources

### Profiling Tools
- **Python:** tracemalloc, memory_profiler, py-spy, memray
- **JavaScript:** Chrome DevTools Memory Profiler, heap snapshots
- **System:** htop, ps, docker stats, Prometheus

### Testing Tools
- **Load:** Locust, Apache JMeter, k6
- **E2E:** Playwright, Cypress
- **Memory:** Valgrind (C/C++ extensions), heapdump

### Monitoring
- **Metrics:** Prometheus + Grafana
- **APM:** Sentry, DataDog, New Relic
- **Logs:** ELK Stack, Loki

---

**END OF IMPLEMENTATION PLAN**
