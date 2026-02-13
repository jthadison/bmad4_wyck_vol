/**
 * Monitoring Dashboard API Service (Story 23.13)
 *
 * Provides typed API methods for production monitoring endpoints.
 * Integrates with backend /api/v1/monitoring routes.
 */

import { apiClient } from './api'
import type {
  SystemHealth,
  AuditEvent,
  DashboardData,
  KillSwitchStatus,
  KillSwitchResult,
} from '@/types/monitoring'

/**
 * Fetch system health status.
 */
export async function getMonitoringHealth(): Promise<SystemHealth> {
  return apiClient.get<SystemHealth>('/monitoring/health')
}

/**
 * Fetch audit trail events with optional filtering.
 */
export async function getAuditTrail(
  params?: Record<string, unknown>
): Promise<AuditEvent[]> {
  return apiClient.get<AuditEvent[]>('/monitoring/audit', params)
}

/**
 * Fetch complete monitoring dashboard data in a single call.
 */
export async function getDashboardData(): Promise<DashboardData> {
  return apiClient.get<DashboardData>('/monitoring/dashboard')
}

/**
 * Activate the kill switch (emergency stop).
 */
export async function activateKillSwitch(): Promise<KillSwitchResult> {
  return apiClient.post<KillSwitchResult>('/monitoring/kill-switch/activate')
}

/**
 * Deactivate the kill switch.
 */
export async function deactivateKillSwitch(): Promise<KillSwitchResult> {
  return apiClient.post<KillSwitchResult>('/monitoring/kill-switch/deactivate')
}

/**
 * Get current kill switch status.
 */
export async function getKillSwitchStatus(): Promise<KillSwitchStatus> {
  return apiClient.get<KillSwitchStatus>('/monitoring/kill-switch')
}

export const monitoringApi = {
  getMonitoringHealth,
  getAuditTrail,
  getDashboardData,
  activateKillSwitch,
  deactivateKillSwitch,
  getKillSwitchStatus,
}

export default monitoringApi
