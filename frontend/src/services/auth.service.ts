// ============================================
// Auth Service
// ============================================
import { api, setTokens, clearTokens } from './api'
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

  // Login
  login: async (data: LoginRequest): Promise<TokenResponse> => {
    const response = await api.post<TokenResponse>('/api/auth/login', data, { skipAuth: true })
    setTokens(response.access_token, response.refresh_token)
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

  // Refresh token
  refreshToken: async (refreshToken: string): Promise<TokenResponse> => {
    const response = await api.post<TokenResponse>(
      '/api/auth/refresh',
      { refresh_token: refreshToken },
      { skipAuth: true, isRefreshRequest: true }
    )
    setTokens(response.access_token, response.refresh_token)
    return response
  },
}
