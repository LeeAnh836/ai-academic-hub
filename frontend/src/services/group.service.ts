// ============================================
// Group Service
// ============================================
import { api } from './api'
import type { Group, GroupMember, GroupMessage } from '@/types/api'

export interface CreateGroupParams {
  group_name: string
  group_type: string
  is_public: boolean
  description?: string
}

export interface UpdateGroupParams {
  group_name?: string
  description?: string
  is_public?: boolean
}

export interface SendGroupMessageParams {
  group_id: string
  content: string
  message_type?: string
  attachments?: any[]
}

export const groupService = {
  // List groups
  listGroups: async (skip = 0, limit = 10): Promise<Group[]> => {
    return api.get<Group[]>(`/api/groups?skip=${skip}&limit=${limit}`)
  },

  // Create group
  createGroup: async (params: CreateGroupParams): Promise<Group> => {
    return api.post<Group>('/api/groups', params)
  },

  // Get group detail
  getGroup: async (groupId: string): Promise<Group> => {
    return api.get<Group>(`/api/groups/${groupId}`)
  },

  // Update group
  updateGroup: async (groupId: string, params: UpdateGroupParams): Promise<Group> => {
    return api.put<Group>(`/api/groups/${groupId}`, params)
  },

  // Delete group
  deleteGroup: async (groupId: string): Promise<{ message: string }> => {
    return api.delete(`/api/groups/${groupId}`)
  },

  // Add member
  addMember: async (groupId: string, userId: string): Promise<{ message: string }> => {
    return api.post(`/api/groups/${groupId}/members`, { user_id: userId })
  },

  // Remove member
  removeMember: async (groupId: string, memberId: string): Promise<{ message: string }> => {
    return api.delete(`/api/groups/${groupId}/members/${memberId}`)
  },

  // List members
  listMembers: async (groupId: string): Promise<GroupMember[]> => {
    return api.get<GroupMember[]>(`/api/groups/${groupId}/members`)
  },

  // Send message
  sendMessage: async (params: SendGroupMessageParams): Promise<GroupMessage> => {
    return api.post<GroupMessage>('/api/groups/messages', {
      group_id: params.group_id,
      content: params.content,
      message_type: params.message_type || 'text',
      attachments: params.attachments || [],
    })
  },

  // List messages
  listMessages: async (
    groupId: string,
    skip = 0,
    limit = 50
  ): Promise<GroupMessage[]> => {
    return api.get<GroupMessage[]>(
      `/api/groups/${groupId}/messages?skip=${skip}&limit=${limit}`
    )
  },

  // Share file to group
  shareFile: async (
    groupId: string,
    documentId: string
  ): Promise<{ message: string }> => {
    return api.post(`/api/groups/${groupId}/files`, { document_id: documentId })
  },

  // List group files
  listFiles: async (groupId: string): Promise<any[]> => {
    return api.get(`/api/groups/${groupId}/files`)
  },

  // Leave group
  leaveGroup: async (groupId: string): Promise<{ message: string }> => {
    return api.post(`/api/groups/${groupId}/leave`, {})
  },
}
