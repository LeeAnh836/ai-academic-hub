// ============================================
// Chat Service
// ============================================
import { api } from './api'
import type { ChatSession, ChatMessage, ChatAskResponse } from '@/types/api'

export interface CreateChatSessionParams {
  title: string
  session_type?: string
  context_documents?: string[]
  model_name?: string
}

export interface SendMessageParams {
  session_id: string
  content: string
  retrieved_chunks?: any[]
}

export const chatService = {
  // List chat sessions
  listSessions: async (skip = 0, limit = 10): Promise<ChatSession[]> => {
    return api.get<ChatSession[]>(`/api/chat/sessions?skip=${skip}&limit=${limit}`)
  },

  // Create chat session
  createSession: async (params: CreateChatSessionParams): Promise<ChatSession> => {
    return api.post<ChatSession>('/api/chat/sessions', {
      title: params.title,
      session_type: params.session_type || 'general',
      context_documents: params.context_documents || [],
      model_name: params.model_name || 'llama3.2:1b',
    })
  },

  // Get session detail with messages
  getSession: async (sessionId: string): Promise<ChatSession> => {
    return api.get<ChatSession>(`/api/chat/sessions/${sessionId}`)
  },

  // Get session messages
  getSessionMessages: async (
    sessionId: string,
    skip = 0,
    limit = 50
  ): Promise<ChatMessage[]> => {
    return api.get<ChatMessage[]>(
      `/api/chat/sessions/${sessionId}/messages?skip=${skip}&limit=${limit}`
    )
  },

  // Send message
  sendMessage: async (params: SendMessageParams): Promise<ChatMessage> => {
    return api.post<ChatMessage>('/api/chat/messages', {
      session_id: params.session_id,
      content: params.content,
      retrieved_chunks: params.retrieved_chunks || [],
    })
  },

  // Ask question in a chat session (with AI response)
  askInSession: async (
    sessionId: string,
    question: string,
    options?: {
      document_ids?: string[] | null
      top_k?: number
      score_threshold?: number
      temperature?: number
      max_tokens?: number
    }
  ): Promise<ChatAskResponse> => {
    return api.post<ChatAskResponse>(`/api/chat/sessions/${sessionId}/ask`, {
      question,
      document_ids: options?.document_ids,
      top_k: options?.top_k || 5,
      score_threshold: options?.score_threshold || 0.5,
      temperature: options?.temperature || 0.7,
      max_tokens: options?.max_tokens || 4000,
    })
  },

  // Delete session
  deleteSession: async (sessionId: string): Promise<{ message: string }> => {
    return api.delete(`/api/chat/sessions/${sessionId}`)
  },

  // Send feedback
  sendFeedback: async (
    messageId: string,
    data: { feedback_type: string; comment?: string }
  ): Promise<{ message: string }> => {
    return api.post(`/api/chat/messages/${messageId}/feedback`, data)
  },

  // Get AI usage stats
  getUsageStats: async (): Promise<{
    total_sessions: number
    total_messages: number
    total_tokens: number
    usage_by_model: Record<string, number>
  }> => {
    return api.get('/api/chat/usage')
  },
}
