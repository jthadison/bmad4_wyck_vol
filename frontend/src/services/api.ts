import axios, {
  type AxiosInstance,
  type AxiosError,
  type AxiosResponse,
} from 'axios'
import Big from 'big.js'
import { v4 as uuidv4 } from 'uuid'

// Get base URL from environment variables
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

// Create Axios instance with base configuration
const axiosInstance: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 second timeout
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor - add request ID for tracing
axiosInstance.interceptors.request.use(
  (config) => {
    config.headers['X-Request-ID'] = uuidv4()
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor - convert Decimal strings to Big.js objects
axiosInstance.interceptors.response.use(
  (response: AxiosResponse) => {
    // Convert Decimal strings to Big.js objects for financial precision
    if (response.data && typeof response.data === 'object') {
      response.data = convertDecimalsToBig(response.data)
    }
    return response
  },
  (error: AxiosError) => {
    return Promise.reject(error)
  }
)

// Recursively convert Decimal string fields to Big.js objects
function convertDecimalsToBig(obj: unknown): unknown {
  if (obj === null || obj === undefined) {
    return obj
  }

  if (Array.isArray(obj)) {
    return obj.map((item) => convertDecimalsToBig(item))
  }

  if (typeof obj === 'object') {
    const converted: Record<string, unknown> = {}
    const record = obj as Record<string, unknown>
    for (const key in record) {
      const value = record[key]
      // Convert strings that look like decimal numbers (prices, percentages)
      // Only convert if field name suggests it's a financial value
      if (
        typeof value === 'string' &&
        /^-?\d+\.?\d*$/.test(value) &&
        (key.includes('price') ||
          key.includes('risk') ||
          key.includes('percent') ||
          key.includes('ratio') ||
          key.includes('size') ||
          key.includes('change') ||
          key.includes('heat'))
      ) {
        converted[key] = new Big(value)
      } else {
        converted[key] = convertDecimalsToBig(value)
      }
    }
    return converted
  }

  return obj
}

// Typed API client methods
export const apiClient = {
  get: <T = unknown>(
    url: string,
    params?: Record<string, unknown>
  ): Promise<T> => {
    return axiosInstance.get<T>(url, { params }).then((res) => res.data)
  },

  post: <T = unknown>(url: string, data?: unknown): Promise<T> => {
    return axiosInstance.post<T>(url, data).then((res) => res.data)
  },

  patch: <T = unknown>(url: string, data?: unknown): Promise<T> => {
    return axiosInstance.patch<T>(url, data).then((res) => res.data)
  },

  delete: <T = unknown>(url: string): Promise<T> => {
    return axiosInstance.delete<T>(url).then((res) => res.data)
  },
}

// ============================================================================
// Audit Log Types (Story 10.8)
// ============================================================================

export interface ValidationChainStep {
  step_name: string
  passed: boolean
  reason: string
  timestamp: string
  wyckoff_rule_reference: string
}

export interface AuditLogEntry {
  id: string
  timestamp: string
  symbol: string
  pattern_type: 'SPRING' | 'UTAD' | 'SOS' | 'LPS' | 'SC' | 'AR' | 'ST'
  phase: 'A' | 'B' | 'C' | 'D' | 'E'
  confidence_score: number
  status:
    | 'PENDING'
    | 'APPROVED'
    | 'REJECTED'
    | 'FILLED'
    | 'STOPPED'
    | 'TARGET_HIT'
    | 'EXPIRED'
  rejection_reason: string | null
  signal_id: string | null
  pattern_id: string
  validation_chain: ValidationChainStep[]
  entry_price: string | null
  target_price: string | null
  stop_loss: string | null
  r_multiple: string | null
  volume_ratio: string
  spread_ratio: string
}

export interface AuditLogQueryParams {
  start_date?: string
  end_date?: string
  symbols?: string[]
  pattern_types?: string[]
  statuses?: string[]
  min_confidence?: number
  max_confidence?: number
  search_text?: string
  order_by?: 'timestamp' | 'symbol' | 'pattern_type' | 'confidence' | 'status'
  order_direction?: 'asc' | 'desc'
  limit?: number
  offset?: number
}

export interface AuditLogResponse {
  data: AuditLogEntry[]
  total_count: number
  limit: number
  offset: number
}

// ============================================================================
// API Methods
// ============================================================================

/**
 * Get audit log with filtering, sorting, and pagination (Story 10.8)
 *
 * @param params - Query parameters for filtering/sorting/pagination
 * @returns Promise resolving to paginated audit log response
 *
 * @example
 * ```ts
 * const response = await getAuditLog({
 *   symbols: ['AAPL', 'TSLA'],
 *   pattern_types: ['SPRING'],
 *   statuses: ['FILLED'],
 *   limit: 50,
 *   offset: 0
 * })
 * ```
 */
export async function getAuditLog(
  params?: AuditLogQueryParams
): Promise<AuditLogResponse> {
  return apiClient.get<AuditLogResponse>(
    '/audit-log',
    params as Record<string, unknown>
  )
}

export default apiClient
