// ============================================
// Base API Client
// ============================================

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

console.log('🔗 API Base URL:', API_BASE_URL) // Debug log

// Token management
let accessToken: string | null = localStorage.getItem('access_token')
let refreshToken: string | null = localStorage.getItem('refresh_token')

export const setTokens = (access: string, refresh: string) => {
  accessToken = access
  refreshToken = refresh
  localStorage.setItem('access_token', access)
  localStorage.setItem('refresh_token', refresh)
}

export const clearTokens = () => {
  accessToken = null
  refreshToken = null
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

export const getAccessToken = () => accessToken

// API Error class
export class ApiError extends Error {
  status: number
  message: string
  data?: any

  constructor(status: number, message: string, data?: any) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.message = message
    this.data = data
  }
}

// API Client configuration
interface RequestConfig extends RequestInit {
  skipAuth?: boolean
  isRefreshRequest?: boolean
}

// Token refresh logic
let isRefreshing = false
let failedQueue: Array<{
  resolve: (value?: any) => void
  reject: (error?: any) => void
}> = []

const processQueue = (error: any = null, token: string | null = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token)
    }
  })
  failedQueue = []
}

const refreshAccessToken = async (): Promise<string> => {
  if (!refreshToken) {
    throw new ApiError(401, 'No refresh token available')
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })

    if (!response.ok) {
      throw new ApiError(response.status, 'Token refresh failed')
    }

    const data = await response.json()
    setTokens(data.access_token, data.refresh_token)
    return data.access_token
  } catch (error) {
    clearTokens()
    throw error
  }
}

// Main API request function
export const apiRequest = async <T = any>(
  endpoint: string,
  config: RequestConfig = {}
): Promise<T> => {
  const { skipAuth, isRefreshRequest, ...fetchConfig } = config
  
  const url = `${API_BASE_URL}${endpoint}`
  
  const headers: Record<string, string> = {
    ...(fetchConfig.headers as Record<string, string>),
  }

  // Add auth header if not skipped
  if (!skipAuth && accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`
  }

  // Add Content-Type for non-FormData requests
  if (!(fetchConfig.body instanceof FormData) && fetchConfig.body) {
    headers['Content-Type'] = 'application/json'
  }

  try {
    const response = await fetch(url, {
      ...fetchConfig,
      headers,
    })

    // Handle 401 - Token expired
    if (response.status === 401 && !skipAuth && !isRefreshRequest) {
      if (!isRefreshing) {
        isRefreshing = true
        try {
          const newToken = await refreshAccessToken()
          isRefreshing = false
          processQueue(null, newToken)
          
          // Retry original request with new token
          return apiRequest<T>(endpoint, config)
        } catch (error) {
          isRefreshing = false
          processQueue(error, null)
          throw error
        }
      } else {
        // Queue this request while token is being refreshed
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then(() => {
          return apiRequest<T>(endpoint, config)
        })
      }
    }

    // Handle other errors
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new ApiError(
        response.status,
        errorData.detail || response.statusText,
        errorData
      )
    }

    // Parse response
    const contentType = response.headers.get('content-type')
    if (contentType && contentType.includes('application/json')) {
      return await response.json()
    }
    
    return response as any
  } catch (error) {
    if (error instanceof ApiError) {
      throw error
    }
    throw new ApiError(500, 'Network error', error)
  }
}

// Convenience methods
export const api = {
  get: <T = any>(endpoint: string, config?: RequestConfig) =>
    apiRequest<T>(endpoint, { ...config, method: 'GET' }),
  
  post: <T = any>(endpoint: string, data?: any, config?: RequestConfig) =>
    apiRequest<T>(endpoint, {
      ...config,
      method: 'POST',
      body: data instanceof FormData ? data : JSON.stringify(data),
    }),
  
  put: <T = any>(endpoint: string, data?: any, config?: RequestConfig) =>
    apiRequest<T>(endpoint, {
      ...config,
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  
  patch: <T = any>(endpoint: string, data?: any, config?: RequestConfig) =>
    apiRequest<T>(endpoint, {
      ...config,
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  
  delete: <T = any>(endpoint: string, config?: RequestConfig) =>
    apiRequest<T>(endpoint, { ...config, method: 'DELETE' }),
}
