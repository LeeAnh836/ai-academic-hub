// ============================================
// Chat Hooks
// ============================================
import { useState, useEffect } from 'react'
import {
  chatService,
  type CreateChatSessionParams,
} from '@/services/chat.service'
import type { ChatSession, ChatMessage } from '@/types/api'

// Hook for chat sessions
export const useChatSessions = (autoFetch = true) => {
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchSessions = async (skip = 0, limit = 100) => {
    setLoading(true)
    setError(null)
    try {
      const data = await chatService.listSessions(skip, limit)
      setSessions(data)
      return data
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to fetch sessions'
      setError(errorMessage)
      throw err
    } finally {
      setLoading(false)
    }
  }

  const createSession = async (params: CreateChatSessionParams) => {
    setError(null)
    try {
      const newSession = await chatService.createSession(params)
      setSessions(prev => [newSession, ...prev])
      return newSession
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to create session'
      setError(errorMessage)
      throw err
    }
  }

  const deleteSession = async (sessionId: string) => {
    setError(null)
    try {
      await chatService.deleteSession(sessionId)
      setSessions(prev => prev.filter(s => s.id !== sessionId))
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to delete session'
      setError(errorMessage)
      throw err
    }
  }

  useEffect(() => {
    if (autoFetch) {
      fetchSessions()
    }
  }, [autoFetch])

  return {
    sessions,
    loading,
    error,
    fetchSessions,
    createSession,
    deleteSession,
    refetch: fetchSessions,
  }
}

// Hook for chat messages in a session
export const useChatMessages = (sessionId: string | null, autoFetch = true) => {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchMessages = async (skip = 0, limit = 100) => {
    if (!sessionId) return
    
    setLoading(true)
    setError(null)
    try {
      const data = await chatService.getSessionMessages(sessionId, skip, limit)
      setMessages(data)
      return data
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to fetch messages'
      setError(errorMessage)
      throw err
    } finally {
      setLoading(false)
    }
  }

  const sendMessage = async (content: string) => {
    if (!sessionId) throw new Error('No session selected')
    
    setError(null)
    try {
      const newMessage = await chatService.sendMessage({
        session_id: sessionId,
        content,
      })
      setMessages(prev => [...prev, newMessage])
      return newMessage
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to send message'
      setError(errorMessage)
      throw err
    }
  }

  useEffect(() => {
    if (autoFetch && sessionId) {
      fetchMessages()
    }
  }, [autoFetch, sessionId])

  return {
    messages,
    loading,
    error,
    fetchMessages,
    sendMessage,
    refetch: fetchMessages,
  }
}

// Hook for AI chat ask in a session
export const useChatAsk = () => {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const askInSession = async (
    sessionId: string,
    question: string,
    options?: {
      document_ids?: string[] | null
      top_k?: number
      score_threshold?: number
      temperature?: number
      max_tokens?: number
    }
  ) => {
    setLoading(true)
    setError(null)
    try {
      const response = await chatService.askInSession(sessionId, question, options)
      return response
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to get AI response'
      setError(errorMessage)
      throw err
    } finally {
      setLoading(false)
    }
  }

  return {
    askInSession,
    loading,
    error,
  }
}

// Hook for chat session detail
export const useChatSession = (sessionId: string | null) => {
  const [session, setSession] = useState<ChatSession | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchSession = async () => {
    if (!sessionId) return
    
    setLoading(true)
    setError(null)
    try {
      const data = await chatService.getSession(sessionId)
      setSession(data)
      return data
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to fetch session'
      setError(errorMessage)
      throw err
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (sessionId) {
      fetchSession()
    }
  }, [sessionId])

  return {
    session,
    loading,
    error,
    refetch: fetchSession,
  }
}
