// ============================================
// Messaging Service - REST API + WebSocket
// ============================================
import { api, apiRequest } from './api'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const WS_BASE_URL = API_BASE_URL.replace(/^http/, 'ws')

// ============================================
// Types
// ============================================
export interface ConversationItem {
  id: string
  type: 'direct' | 'group'
  name: string
  avatar_url: string | null
  last_message: string | null
  last_message_at: string | null
  unread_count: number
  is_online?: boolean | null
  last_activity?: string | null
  member_count?: number | null
  other_user_id?: string | null
  member_avatars?: { avatar_url: string | null; full_name: string }[]
}

export interface MessageSender {
  id: string
  username: string
  full_name: string | null
  avatar_url: string | null
}

export interface ReplyToInfo {
  id: string
  content: string | null
  sender_name: string
  message_type: string
  is_deleted: boolean
  file_url?: string | null
}

export interface ReactionItem {
  id: string
  user_id: string
  username: string
  reaction: string
}

export interface DirectMessageItem {
  id: string
  conversation_id: string
  sender_id: string
  receiver_id: string
  content: string | null
  message_type: string
  file_url: string | null
  file_name: string | null
  file_size: number | null
  is_read: boolean
  status: 'sent' | 'delivered' | 'seen'
  delivered_at: string | null
  read_at: string | null
  created_at: string
  sender: MessageSender | null
  reply_to_id?: string | null
  reply_to?: ReplyToInfo | null
  is_deleted?: boolean
  reactions?: ReactionItem[]
}

export interface GroupMessageItem {
  id: string
  group_id: string
  user_id: string
  content: string | null
  message_type: string
  file_url: string | null
  file_name: string | null
  file_size: number | null
  is_pinned: boolean
  created_at: string
  sender: MessageSender | null
  reply_to_id?: string | null
  reply_to?: ReplyToInfo | null
  is_deleted?: boolean
  reactions?: ReactionItem[]
}

export interface SearchUserResult {
  id: string
  username: string
  full_name: string | null
  student_id: string | null
  avatar_url: string | null
  friendship_status: string | null
}

export interface FriendItem {
  id: string
  username: string
  full_name: string | null
  student_id: string | null
  avatar_url: string | null
  is_online: boolean
}

export interface FriendRequestItem {
  id: string
  requester: {
    id: string
    username: string
    full_name: string | null
    avatar_url: string | null
    student_id: string | null
  }
  status: string
  created_at: string
}

export interface GroupMemberItem {
  id: string
  username: string
  full_name: string | null
  avatar_url: string | null
  role: string
  is_online: boolean
}

export interface FileUploadResult {
  file_url: string
  file_name: string
  file_size: number
  message_type: 'image' | 'file'
}

export interface MediaItem {
  id: string
  file_url: string
  file_name: string
  file_size: number
  message_type: string
  created_at: string
  sender: { id: string; full_name: string; username: string } | null
}

// ============================================
// REST API
// ============================================
export const messagingApi = {
  getConversations: (): Promise<ConversationItem[]> =>
    api.get('/api/messages/conversations'),

  createConversation: (participant2Id: string) =>
    api.post('/api/messages/conversations', { participant_2_id: participant2Id }),

  getDirectMessages: (conversationId: string, skip = 0, limit = 50): Promise<DirectMessageItem[]> =>
    api.get(`/api/messages/conversations/${conversationId}/messages?skip=${skip}&limit=${limit}`),

  getGroupMessages: (groupId: string, skip = 0, limit = 50): Promise<GroupMessageItem[]> =>
    api.get(`/api/messages/groups/${groupId}/messages?skip=${skip}&limit=${limit}`),

  getGroupMembers: (groupId: string): Promise<GroupMemberItem[]> =>
    api.get(`/api/messages/groups/${groupId}/members`),

  getConversationMedia: (conversationId: string, mediaType: 'image' | 'file', skip = 0, limit = 50): Promise<MediaItem[]> =>
    api.get(`/api/messages/conversations/${conversationId}/media?media_type=${mediaType}&skip=${skip}&limit=${limit}`),

  getGroupMedia: (groupId: string, mediaType: 'image' | 'file', skip = 0, limit = 50): Promise<MediaItem[]> =>
    api.get(`/api/messages/groups/${groupId}/media?media_type=${mediaType}&skip=${skip}&limit=${limit}`),

  uploadFile: async (file: File): Promise<FileUploadResult> => {
    const formData = new FormData()
    formData.append('file', file)
    return apiRequest('/api/messages/upload', {
      method: 'POST',
      body: formData,
    })
  },

  searchUsers: (query: string): Promise<SearchUserResult[]> =>
    api.get(`/api/messages/users/search?q=${encodeURIComponent(query)}`),

  sendFriendRequest: (addresseeId: string) =>
    api.post('/api/messages/friends/request', { addressee_id: addresseeId }),

  respondToFriendRequest: (friendshipId: string, action: 'accepted' | 'declined') =>
    api.post(`/api/messages/friends/${friendshipId}/respond`, { action }),

  getFriends: (): Promise<FriendItem[]> =>
    api.get('/api/messages/friends'),

  getFriendRequests: (): Promise<FriendRequestItem[]> =>
    api.get('/api/messages/friends/requests'),

  getOnlineStatus: (userId: string) =>
    api.get(`/api/messages/online-status/${userId}`),

  getUnreadCount: (): Promise<{ total_unread: number }> =>
    api.get('/api/messages/unread-count'),

  createGroup: async (name: string, memberIds: string[]): Promise<{ id: string }> => {
    // Create group
    const group = await api.post<{ id: string }>('/api/groups', {
      group_name: name,
      group_type: 'chat',
      is_public: false,
    })
    // Add members
    for (const uid of memberIds) {
      await api.post(`/api/groups/${group.id}/members`, { user_id: uid })
    }
    return group
  },
}

// ============================================
// WebSocket Manager
// ============================================
export type WSMessageHandler = (data: any) => void

class WebSocketManager {
  private ws: WebSocket | null = null
  private handlers: Map<string, WSMessageHandler[]> = new Map()
  private reconnectTimer: number | null = null
  private pingTimer: number | null = null
  private token: string | null = null

  connect(token: string) {
    this.token = token
    this.doConnect()
  }

  private doConnect() {
    if (!this.token) return
    if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING) return

    this.ws = new WebSocket(`${WS_BASE_URL}/api/messages/ws?token=${this.token}`)

    this.ws.onopen = () => {
      console.log('✅ WebSocket connected')
      // Ping every 30s to keep connection alive
      this.pingTimer = window.setInterval(() => {
        this.send({ type: 'ping' })
      }, 30000)
    }

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        const type = data.type
        const typeHandlers = this.handlers.get(type) || []
        typeHandlers.forEach((h) => h(data))

        // Also fire wildcard handlers
        const wildcardHandlers = this.handlers.get('*') || []
        wildcardHandlers.forEach((h) => h(data))
      } catch (err) {
        console.error('WebSocket message handler error:', err)
      }
    }

    this.ws.onclose = () => {
      console.log('❌ WebSocket disconnected')
      this.cleanup()
      // Reconnect after 3s
      this.reconnectTimer = window.setTimeout(() => this.doConnect(), 3000)
    }

    this.ws.onerror = () => {
      this.ws?.close()
    }
  }

  private cleanup() {
    if (this.pingTimer) {
      clearInterval(this.pingTimer)
      this.pingTimer = null
    }
  }

  disconnect() {
    this.token = null
    this.cleanup()
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      this.ws.onclose = null
      this.ws.close()
      this.ws = null
    }
  }

  on(type: string, handler: WSMessageHandler) {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, [])
    }
    this.handlers.get(type)!.push(handler)
  }

  off(type: string, handler: WSMessageHandler) {
    const handlers = this.handlers.get(type)
    if (handlers) {
      this.handlers.set(
        type,
        handlers.filter((h) => h !== handler)
      )
    }
  }

  send(data: any): boolean {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
      return true
    }
    return false
  }

  get isConnected() {
    return this.ws?.readyState === WebSocket.OPEN
  }
}

export const wsManager = new WebSocketManager()
