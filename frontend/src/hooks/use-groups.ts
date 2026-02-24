// ============================================
// Group Hooks
// ============================================
import { useState, useEffect } from 'react'
import {
  groupService,
  type CreateGroupParams,
  type UpdateGroupParams,
} from '@/services/group.service'
import type { Group, GroupMember, GroupMessage } from '@/types/api'

// Hook for groups
export const useGroups = (autoFetch = true) => {
  const [groups, setGroups] = useState<Group[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchGroups = async (skip = 0, limit = 100) => {
    setLoading(true)
    setError(null)
    try {
      const data = await groupService.listGroups(skip, limit)
      setGroups(data)
      return data
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to fetch groups'
      setError(errorMessage)
      throw err
    } finally {
      setLoading(false)
    }
  }

  const createGroup = async (params: CreateGroupParams) => {
    setError(null)
    try {
      const newGroup = await groupService.createGroup(params)
      setGroups(prev => [newGroup, ...prev])
      return newGroup
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to create group'
      setError(errorMessage)
      throw err
    }
  }

  const deleteGroup = async (groupId: string) => {
    setError(null)
    try {
      await groupService.deleteGroup(groupId)
      setGroups(prev => prev.filter(g => g.id !== groupId))
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to delete group'
      setError(errorMessage)
      throw err
    }
  }

  const leaveGroup = async (groupId: string) => {
    setError(null)
    try {
      await groupService.leaveGroup(groupId)
      setGroups(prev => prev.filter(g => g.id !== groupId))
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to leave group'
      setError(errorMessage)
      throw err
    }
  }

  useEffect(() => {
    if (autoFetch) {
      fetchGroups()
    }
  }, [autoFetch])

  return {
    groups,
    loading,
    error,
    fetchGroups,
    createGroup,
    deleteGroup,
    leaveGroup,
    refetch: fetchGroups,
  }
}

// Hook for single group
export const useGroup = (groupId: string | null) => {
  const [group, setGroup] = useState<Group | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchGroup = async () => {
    if (!groupId) return
    
    setLoading(true)
    setError(null)
    try {
      const data = await groupService.getGroup(groupId)
      setGroup(data)
      return data
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to fetch group'
      setError(errorMessage)
      throw err
    } finally {
      setLoading(false)
    }
  }

  const updateGroup = async (params: UpdateGroupParams) => {
    if (!groupId) throw new Error('No group selected')
    
    setError(null)
    try {
      const updated = await groupService.updateGroup(groupId, params)
      setGroup(updated)
      return updated
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to update group'
      setError(errorMessage)
      throw err
    }
  }

  useEffect(() => {
    if (groupId) {
      fetchGroup()
    }
  }, [groupId])

  return {
    group,
    loading,
    error,
    fetchGroup,
    updateGroup,
    refetch: fetchGroup,
  }
}

// Hook for group members
export const useGroupMembers = (groupId: string | null, autoFetch = true) => {
  const [members, setMembers] = useState<GroupMember[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchMembers = async () => {
    if (!groupId) return
    
    setLoading(true)
    setError(null)
    try {
      const data = await groupService.listMembers(groupId)
      setMembers(data)
      return data
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to fetch members'
      setError(errorMessage)
      throw err
    } finally {
      setLoading(false)
    }
  }

  const addMember = async (userId: string) => {
    if (!groupId) throw new Error('No group selected')
    
    setError(null)
    try {
      await groupService.addMember(groupId, userId)
      await fetchMembers() // Refresh members list
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to add member'
      setError(errorMessage)
      throw err
    }
  }

  const removeMember = async (memberId: string) => {
    if (!groupId) throw new Error('No group selected')
    
    setError(null)
    try {
      await groupService.removeMember(groupId, memberId)
      setMembers(prev => prev.filter(m => m.id !== memberId))
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to remove member'
      setError(errorMessage)
      throw err
    }
  }

  useEffect(() => {
    if (autoFetch && groupId) {
      fetchMembers()
    }
  }, [autoFetch, groupId])

  return {
    members,
    loading,
    error,
    fetchMembers,
    addMember,
    removeMember,
    refetch: fetchMembers,
  }
}

// Hook for group messages
export const useGroupMessages = (groupId: string | null, autoFetch = true) => {
  const [messages, setMessages] = useState<GroupMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchMessages = async (skip = 0, limit = 100) => {
    if (!groupId) return
    
    setLoading(true)
    setError(null)
    try {
      const data = await groupService.listMessages(groupId, skip, limit)
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
    if (!groupId) throw new Error('No group selected')
    
    setError(null)
    try {
      const newMessage = await groupService.sendMessage({
        group_id: groupId,
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
    if (autoFetch && groupId) {
      fetchMessages()
    }
  }, [autoFetch, groupId])

  return {
    messages,
    loading,
    error,
    fetchMessages,
    sendMessage,
    refetch: fetchMessages,
  }
}
