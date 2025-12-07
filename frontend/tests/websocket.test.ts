import { describe, it, expect, vi, beforeEach } from 'vitest'
import { WebSocketClient } from '../src/services/websocket'

// Mock WebSocket
class MockWebSocket {
  static OPEN = 1
  static CLOSED = 3

  readyState = MockWebSocket.OPEN
  onopen: (() => void) | null = null
  onclose: (() => void) | null = null
  onmessage: ((event: any) => void) | null = null
  onerror: ((error: any) => void) | null = null

  close() {
    this.readyState = MockWebSocket.CLOSED
    if (this.onclose) {
      this.onclose()
    }
  }

  send(data: string) {
    // Mock send
  }

  simulateMessage(data: any) {
    if (this.onmessage) {
      this.onmessage({ data: JSON.stringify(data) })
    }
  }

  simulateOpen() {
    if (this.onopen) {
      this.onopen()
    }
  }
}

global.WebSocket = MockWebSocket as any

describe('WebSocket Client', () => {
  let client: WebSocketClient
  let mockWs: MockWebSocket

  beforeEach(() => {
    vi.clearAllTimers()
    vi.useFakeTimers()
    client = new WebSocketClient('ws://localhost:8000/ws')
  })

  it('registers event handlers', () => {
    const handler = vi.fn()
    client.on('connected', handler)

    client.connect()
    mockWs = (client as any).ws

    mockWs.simulateMessage({
      type: 'connected',
      connection_id: 'test-123',
      sequence_number: 1,
    })

    expect(handler).toHaveBeenCalled()
  })

  it('tracks sequence numbers', () => {
    client.connect()
    mockWs = (client as any).ws

    mockWs.simulateMessage({
      type: 'signal_generated',
      signal: {},
      sequence_number: 42,
    })

    expect(client.getLastSequenceNumber()).toBe(42)
  })

  it('handles reconnection with exponential backoff', () => {
    client.connect()
    mockWs = (client as any).ws

    // Simulate disconnect
    mockWs.close()

    // Check that reconnection is scheduled
    expect(vi.getTimerCount()).toBeGreaterThan(0)
  })

  it('returns connection status', () => {
    expect(client.isConnected()).toBe(false)
  })

  it('buffers messages during reconnection', () => {
    const handler = vi.fn()
    client.on('signal_generated', handler)

    client.connect()
    mockWs = (client as any).ws

    // Simulate initial connection
    mockWs.simulateMessage({
      type: 'connected',
      connection_id: 'test-123',
      sequence_number: 1,
    })

    // Trigger disconnect to enter reconnecting state
    ;(client as any).isReconnecting = true

    // Send message while reconnecting - should be buffered
    mockWs.simulateMessage({
      type: 'signal_generated',
      signal: { id: 'sig-1' },
      sequence_number: 2,
    })

    // Handler should not be called yet (message buffered)
    expect(handler).not.toHaveBeenCalled()

    // Check that message is in buffer
    const buffer = (client as any).messageBuffer
    expect(buffer.length).toBe(1)
    expect(buffer[0].type).toBe('signal_generated')
  })

  it('clears buffer on disconnect', () => {
    client.connect()
    mockWs = (client as any).ws

    // Add messages to buffer
    ;(client as any).messageBuffer = [
      { type: 'signal_generated', signal: {}, sequence_number: 1 },
      { type: 'signal_generated', signal: {}, sequence_number: 2 },
    ]

    // Disconnect should clear buffer
    client.disconnect()

    expect((client as any).messageBuffer.length).toBe(0)
  })
})
