// ============================================
// Auth Hooks
// ============================================
import { useState } from 'react'
import { authService } from '@/services/auth.service'
import { userService } from '@/services/user.service'
import type { User, RegisterRequest, LoginRequest } from '@/types/api'

export const useAuth = () => {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const register = async (data: RegisterRequest) => {
    setLoading(true)
    setError(null)
    try {
      const response = await authService.register(data)
      return response
    } catch (err: any) {
      const errorMessage = err.message || 'Registration failed'
      setError(errorMessage)
      throw err
    } finally {
      setLoading(false)
    }
  }

  const login = async (data: LoginRequest) => {
    setLoading(true)
    setError(null)
    try {
      const response = await authService.login(data)
      // Get user info after login
      const user = await userService.getCurrentUser()
      return { tokens: response, user }
    } catch (err: any) {
      const errorMessage = err.message || 'Login failed'
      setError(errorMessage)
      throw err
    } finally {
      setLoading(false)
    }
  }

  const logout = async () => {
    setLoading(true)
    setError(null)
    try {
      await authService.logout()
    } catch (err: any) {
      const errorMessage = err.message || 'Logout failed'
      setError(errorMessage)
      throw err
    } finally {
      setLoading(false)
    }
  }

  return {
    register,
    login,
    logout,
    loading,
    error,
  }
}

// Hook for getting current user
export const useCurrentUser = () => {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchUser = async () => {
    setLoading(true)
    setError(null)
    try {
      const userData = await userService.getCurrentUser()
      setUser(userData)
      return userData
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to fetch user'
      setError(errorMessage)
      setUser(null)
      throw err
    } finally {
      setLoading(false)
    }
  }

  const updateUser = async (data: { full_name?: string }) => {
    setError(null)
    try {
      const updatedUser = await userService.updateCurrentUser(data)
      setUser(updatedUser)
      return updatedUser
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to update user'
      setError(errorMessage)
      throw err
    }
  }

  return {
    user,
    loading,
    error,
    fetchUser,
    updateUser,
    refetch: fetchUser,
  }
}
