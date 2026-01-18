import type { AxiosError } from 'axios'

interface ApiErrorResponse {
  error?: {
    code: string
    message: string
    details?: string | Record<string, unknown>
  }
  request_id?: string
}

/**
 * Parse API error responses into user-friendly messages
 * @param error - Axios error object
 * @returns User-friendly error message
 */
export function handleApiError(error: AxiosError<ApiErrorResponse>): string {
  // Network errors
  if (!error.response) {
    return 'Network error: Unable to connect to the server. Please check your connection.'
  }

  const { status, data } = error.response

  // Parse standardized API error format
  if (data?.error) {
    const { message, details } = data.error
    let errorMsg = message

    // Add details if available
    if (details && typeof details === 'string') {
      errorMsg += ` (${details})`
    }

    // Add request ID for debugging
    if (data.request_id) {
      errorMsg += ` [Request ID: ${data.request_id}]`
    }

    return errorMsg
  }

  // Fallback for non-standard errors
  switch (status) {
    case 400:
      return 'Bad Request: Invalid data provided.'
    case 401:
      return 'Unauthorized: Please log in again.'
    case 403:
      return 'Forbidden: You do not have permission to perform this action.'
    case 404:
      return 'Not Found: The requested resource was not found.'
    case 500:
      return 'Server Error: An internal server error occurred.'
    case 503:
      return 'Service Unavailable: The server is temporarily unavailable.'
    default:
      return `Error ${status}: ${error.message}`
  }
}
