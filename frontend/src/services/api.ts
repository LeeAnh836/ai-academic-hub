// ============================================
// Base API Client - Using HttpOnly Cookies
// ============================================

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

console.log('🔗 API Base URL:', API_BASE_URL) // Debug log

// Token management - Tokens are now in HttpOnly cookies, managed by backend
// Auto-refresh timer
let autoRefreshTimer: number | null = null

// Clear any old localStorage tokens (migration)
if (localStorage.getItem('access_token') || localStorage.getItem('refresh_token')) {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  console.log('🔄 Migrated from localStorage to HttpOnly cookies')
}

// Token refresh logic - MUST be defined before startAutoRefresh
let isRefreshing = false
let failedQueue: Array<{
  resolve: (value?: any) => void
  reject: (error?: any) => void
}> = []

const processQueue = (error: any = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve()
    }
  })
  failedQueue = []
}

async function refreshAccessToken(): Promise<void> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
      method: 'POST',
      credentials: 'include', // Important: Send cookies
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      // Refresh token expired or invalid
      stopAutoRefresh()
      
      // Only redirect if not already on login page
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
      
      throw new ApiError(response.status, 'Token refresh failed')
    }

    // Tokens are set in cookies by backend
    console.log('✅ Token refreshed successfully')
  } catch (error) {
    stopAutoRefresh()
    
    // Only redirect if not already on login page
    if (window.location.pathname !== '/login') {
      window.location.href = '/login'
    }
    
    throw error
  }
}

// Start auto-refresh timer - refresh 2 minutes before expiry
const startAutoRefresh = () => {
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer)
  }
  
  // Refresh every 13 minutes (access token expires in 15 minutes)
  autoRefreshTimer = window.setInterval(async () => {
    try {
      console.log('🔄 Auto-refreshing access token...')
      await refreshAccessToken()
    } catch (error) {
      console.error('❌ Auto-refresh failed:', error)
      // If refresh fails, stop the timer
      stopAutoRefresh()
    }
  }, 13 * 60 * 1000) // 13 minutes
}

const stopAutoRefresh = () => {
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer)
    autoRefreshTimer = null
  }
}

export const clearTokens = () => {
  stopAutoRefresh()
  // Cookies will be cleared by backend on logout
  // Just clear any local state
  console.log('🔒 Tokens cleared')
}

// Start auto-refresh after successful login
export const initAutoRefresh = () => {
  startAutoRefresh()
  console.log('✅ Auto-refresh initialized')
}

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

  // Add Content-Type for non-FormData requests
  if (!(fetchConfig.body instanceof FormData) && fetchConfig.body) {
    headers['Content-Type'] = 'application/json'
  }

  try {
    const response = await fetch(url, {
      ...fetchConfig,
      headers,
      credentials: 'include', // Important: Include cookies in all requests
    })

    // Handle 401 - Token expired
    if (response.status === 401 && !skipAuth && !isRefreshRequest) {
      // Don't try to refresh if we're already on login page
      if (window.location.pathname === '/login') {
        throw new ApiError(response.status, 'Unauthorized')
      }
      
      if (!isRefreshing) {
        isRefreshing = true
        try {
          await refreshAccessToken()
          isRefreshing = false
          processQueue(null)
          
          // Retry original request
          return apiRequest<T>(endpoint, config)
        } catch (error) {
          isRefreshing = false
          processQueue(error)
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
