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
function convertDecimalsToBig(obj: any): any {
  if (obj === null || obj === undefined) {
    return obj
  }

  if (Array.isArray(obj)) {
    return obj.map((item) => convertDecimalsToBig(item))
  }

  if (typeof obj === 'object') {
    const converted: any = {}
    for (const key in obj) {
      const value = obj[key]
      // Convert strings that look like decimal numbers (prices, percentages)
      // Only convert if field name suggests it's a financial value
      if (
        typeof value === 'string' &&
        /^-?\d+\.\d+$/.test(value) &&
        (key.includes('price') ||
          key.includes('risk') ||
          key.includes('percent') ||
          key.includes('ratio') ||
          key.includes('size'))
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
  get: <T = any>(url: string, params?: any): Promise<T> => {
    return axiosInstance.get<T>(url, { params }).then((res) => res.data)
  },

  post: <T = any>(url: string, data?: any): Promise<T> => {
    return axiosInstance.post<T>(url, data).then((res) => res.data)
  },

  patch: <T = any>(url: string, data?: any): Promise<T> => {
    return axiosInstance.patch<T>(url, data).then((res) => res.data)
  },

  delete: <T = any>(url: string): Promise<T> => {
    return axiosInstance.delete<T>(url).then((res) => res.data)
  },
}

export default apiClient
