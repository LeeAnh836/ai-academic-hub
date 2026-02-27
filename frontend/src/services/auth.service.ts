// ============================================
// Auth Service
// ============================================
import { api, clearTokens, initAutoRefresh } from './api'
import type {
  RegisterRequest,
  LoginRequest,
  TokenResponse,
  MessageResponse,
} from '@/types/api'

export const authService = {
  // Register new user
  register: async (data: RegisterRequest): Promise<MessageResponse> => {
    return api.post<MessageResponse>('/api/auth/register', data, { skipAuth: true })
  },

  // Login - Tokens are set in HttpOnly cookies by backend
  login: async (data: LoginRequest): Promise<TokenResponse> => {
    const response = await api.post<TokenResponse>('/api/auth/login', data, { skipAuth: true })
    // Start auto-refresh timer after successful login
    initAutoRefresh()
    return response
  },

  // Logout
  logout: async (): Promise<MessageResponse> => {
    try {
      const response = await api.post<MessageResponse>('/api/auth/logout', {})
      return response
    } finally {
      clearTokens()
    }
  },

  // Refresh token - Not needed anymore as it's handled automatically
  refreshToken: async (): Promise<TokenResponse> => {
    const response = await api.post<TokenResponse>(
      '/api/auth/refresh',
      {},
      { skipAuth: true, isRefreshRequest: true }
    )
    return response
  },
}
