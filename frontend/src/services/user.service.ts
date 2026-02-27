// ============================================
// User Service
// ============================================
import { api } from './api'
import type { User, UserSettings } from '@/types/api'

export const userService = {
  // Get current user
  getCurrentUser: async (): Promise<User> => {
    return api.get<User>('/api/users/me')
  },

  // Update current user
  updateCurrentUser: async (data: { full_name?: string }): Promise<User> => {
    return api.put<User>('/api/users/me', data)
  },

  // Get user by ID
  getUserById: async (userId: string): Promise<User> => {
    return api.get<User>(`/api/users/${userId}`)
  },

  // Get user settings
  getUserSettings: async (): Promise<UserSettings> => {
    return api.get<UserSettings>('/api/users/me/settings')
  },

  // Update user settings
  updateUserSettings: async (data: Partial<UserSettings>): Promise<UserSettings> => {
    return api.put<UserSettings>('/api/users/me/settings', data)
  },

  // Change password
  changePassword: async (data: { current_password: string; new_password: string }): Promise<{ message: string }> => {
    return api.post<{ message: string }>('/api/users/me/change-password', data)
  },

  // Upload avatar
  uploadAvatar: async (file: File): Promise<User> => {
    const formData = new FormData()
    formData.append('file', file)
    
    const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
    const token = localStorage.getItem('access_token')
    
    const response = await fetch(`${API_BASE_URL}/api/users/me/avatar`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
      body: formData,
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Upload failed' }))
      throw new Error(error.detail || 'Upload failed')
    }

    return response.json()
  },
}
