/**
 * Broker Dashboard API Service (Issue P4-I17)
 *
 * Provides API calls for broker connection status, account info,
 * connection testing, and kill switch management.
 */

import { apiClient } from './api'

// --- Types ---

export interface BrokerAccountInfo {
  broker: string
  connected: boolean
  last_connected_at: string | null
  platform_name: string
  account_id: string | null
  account_balance: string | null
  buying_power: string | null
  cash: string | null
  margin_used: string | null
  margin_available: string | null
  margin_level_pct: string | null
  latency_ms: number | null
  error_message: string | null
}

export interface AllBrokersStatus {
  brokers: BrokerAccountInfo[]
  kill_switch_active: boolean
  kill_switch_activated_at: string | null
  kill_switch_reason: string | null
}

export interface ConnectionTestResult {
  broker: string
  success: boolean
  latency_ms: number | null
  error_message: string | null
}

// --- API Functions ---

export async function getAllBrokersStatus(): Promise<AllBrokersStatus> {
  return apiClient.get<AllBrokersStatus>('/brokers/status')
}

export async function getBrokerStatus(
  broker: string
): Promise<BrokerAccountInfo> {
  return apiClient.get<BrokerAccountInfo>(`/brokers/${broker}/status`)
}

export async function testBrokerConnection(
  broker: string
): Promise<ConnectionTestResult> {
  return apiClient.post<ConnectionTestResult>(`/brokers/${broker}/test`)
}

export async function connectBroker(
  broker: string
): Promise<BrokerAccountInfo> {
  return apiClient.post<BrokerAccountInfo>(`/brokers/${broker}/connect`)
}

export async function disconnectBroker(
  broker: string
): Promise<BrokerAccountInfo> {
  return apiClient.post<BrokerAccountInfo>(`/brokers/${broker}/disconnect`)
}
