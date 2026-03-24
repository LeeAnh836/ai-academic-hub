// ============================================
// Admin Service - API calls for admin panel
// ============================================
import { api } from './api'
import type {
  AdminStats,
  AdminUserListResponse,
  AdminGroupListResponse,
  AdminDocumentListResponse,
  AdminActivityLogListResponse,
} from '@/types/api'

export const adminService = {
  // Get dashboard statistics
  getStats: async (): Promise<AdminStats> => {
    return api.get<AdminStats>('/api/admin/stats')
  },

  // List all users (paginated, searchable)
  getUsers: async (params?: {
    search?: string
    page?: number
    page_size?: number
  }): Promise<AdminUserListResponse> => {
    const query = new URLSearchParams()
    if (params?.search) query.set('search', params.search)
    if (params?.page) query.set('page', params.page.toString())
    if (params?.page_size) query.set('page_size', params.page_size.toString())
    const qs = query.toString()
    return api.get<AdminUserListResponse>(`/api/admin/users${qs ? `?${qs}` : ''}`)
  },

  // Change user role
  changeUserRole: async (userId: string, role: 'admin' | 'user'): Promise<{ message: string }> => {
    return api.put<{ message: string }>(`/api/admin/users/${userId}/role`, { role })
  },

  // Ban/unban user
  banUser: async (userId: string): Promise<{ message: string; is_active: boolean }> => {
    return api.put<{ message: string; is_active: boolean }>(`/api/admin/users/${userId}/ban`)
  },

  // Delete user
  deleteUser: async (userId: string): Promise<{ message: string }> => {
    return api.delete<{ message: string }>(`/api/admin/users/${userId}`)
  },

  // List all groups (paginated, searchable)
  getGroups: async (params?: {
    search?: string
    page?: number
    page_size?: number
  }): Promise<AdminGroupListResponse> => {
    const query = new URLSearchParams()
    if (params?.search) query.set('search', params.search)
    if (params?.page) query.set('page', params.page.toString())
    if (params?.page_size) query.set('page_size', params.page_size.toString())
    const qs = query.toString()
    return api.get<AdminGroupListResponse>(`/api/admin/groups${qs ? `?${qs}` : ''}`)
  },

  // Delete group
  deleteGroup: async (groupId: string): Promise<{ message: string }> => {
    return api.delete<{ message: string }>(`/api/admin/groups/${groupId}`)
  },

  // List all documents (paginated, searchable)
  getDocuments: async (params?: {
    search?: string
    page?: number
    page_size?: number
  }): Promise<AdminDocumentListResponse> => {
    const query = new URLSearchParams()
    if (params?.search) query.set('search', params.search)
    if (params?.page) query.set('page', params.page.toString())
    if (params?.page_size) query.set('page_size', params.page_size.toString())
    const qs = query.toString()
    return api.get<AdminDocumentListResponse>(`/api/admin/documents${qs ? `?${qs}` : ''}`)
  },

  // Delete document
  deleteDocument: async (documentId: string): Promise<{ message: string }> => {
    return api.delete<{ message: string }>(`/api/admin/documents/${documentId}`)
  },

  // Get activity logs (paginated, today only by default)
  getActivityLogs: async (params?: {
    page?: number
    page_size?: number
    today_only?: boolean
  }): Promise<AdminActivityLogListResponse> => {
    const query = new URLSearchParams()
    if (params?.page) query.set('page', params.page.toString())
    if (params?.page_size) query.set('page_size', params.page_size.toString())
    if (params?.today_only !== undefined) query.set('today_only', params.today_only.toString())
    const qs = query.toString()
    return api.get<AdminActivityLogListResponse>(`/api/admin/activity-logs${qs ? `?${qs}` : ''}`)
  },
}
