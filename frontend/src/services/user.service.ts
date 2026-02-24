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
}
