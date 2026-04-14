import { useState, useEffect, useRef, useCallback } from "react"
import { useLocation } from "react-router-dom"
import {
  Send,
  Search,
  Paperclip,
  ImageIcon,
  Users,
  Plus,
  ArrowLeft,
  Info,
  FileText,
  X,
  UserPlus,
  Download,
  Check,
  CheckCheck,
  Loader2,
  Reply,
  Trash2,
  LogOut,
  SmilePlus,
  Menu,
  PanelLeft,
  PanelLeftClose,
  ChevronLeft,
  ChevronRight,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { useApp } from "@/lib/app-context"
import { useTranslation } from "@/lib/i18n"
import {
  messagingApi,
  wsManager,
  type ConversationItem,
  type DirectMessageItem,
  type GroupMessageItem,
  type SearchUserResult,
  type GroupMemberItem,
  type ReactionItem,
  type MediaItem,
} from "@/services/messaging.service"
import { groupService } from "@/services/group.service"

type MessageItem = DirectMessageItem | GroupMessageItem

function getInitials(name: string | null | undefined): string {
  if (!name) return "?"
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2)
}

function parseUTCDate(dateStr: string): Date {
  // Backend stores UTC but returns ISO without 'Z' suffix
  // Append 'Z' so JS Date parses as UTC, not local time
  if (!dateStr.endsWith("Z") && !dateStr.includes("+")) {
    return new Date(dateStr + "Z")
  }
  return new Date(dateStr)
}

function formatTime(dateStr: string, t: (key: string, params?: Record<string, string | number>) => string): string {
  const date = parseUTCDate(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMin = Math.floor(diffMs / 60000)

  if (diffMin < 1) return t("time.justNow")
  if (diffMin < 60) return t("time.minutesShort", { n: diffMin })
  const diffHours = Math.floor(diffMin / 60)
  if (diffHours < 24) return t("time.hoursShort", { n: diffHours })
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 7) return t("time.daysShort", { n: diffDays })
  return date.toLocaleDateString(t("time.locale"), { day: "2-digit", month: "2-digit" })
}

function formatMessageTime(dateStr: string, t: (key: string, params?: Record<string, string | number>) => string): string {
  const date = parseUTCDate(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / 86400000)
  const timeStr = date.toLocaleTimeString(t("time.locale"), { hour: "2-digit", minute: "2-digit" })

  if (diffDays === 0 && date.getDate() === now.getDate()) {
    return timeStr
  }
  const yesterday = new Date(now)
  yesterday.setDate(yesterday.getDate() - 1)
  if (date.getDate() === yesterday.getDate() && date.getMonth() === yesterday.getMonth() && date.getFullYear() === yesterday.getFullYear()) {
    return t("time.yesterdayAt", { time: timeStr })
  }
  if (diffDays < 7) {
    const weekdayKeys = ["time.sunday", "time.monday", "time.tuesday", "time.wednesday", "time.thursday", "time.friday", "time.saturday"]
    return t("time.weekdayAt", { day: t(weekdayKeys[date.getDay()]), time: timeStr })
  }
  if (date.getFullYear() === now.getFullYear()) {
    return t("time.dateMonth", { d: date.getDate(), m: date.getMonth() + 1, time: timeStr })
  }
  return t("time.dateMonthYear", { d: date.getDate(), m: date.getMonth() + 1, y: date.getFullYear(), time: timeStr })
}

function formatDateSeparator(dateStr: string, t: (key: string, params?: Record<string, string | number>) => string): string {
  const date = parseUTCDate(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffDays === 0 && date.getDate() === now.getDate()) return t("time.today")
  const yesterday = new Date(now)
  yesterday.setDate(yesterday.getDate() - 1)
  if (date.getDate() === yesterday.getDate() && date.getMonth() === yesterday.getMonth() && date.getFullYear() === yesterday.getFullYear()) return t("time.yesterday")
  if (diffDays < 7) {
    const weekdayKeys = ["time.sunday", "time.monday", "time.tuesday", "time.wednesday", "time.thursday", "time.friday", "time.saturday"]
    return t(weekdayKeys[date.getDay()])
  }
  if (date.getFullYear() === now.getFullYear()) {
    return t("time.dayMonth", { d: date.getDate(), m: date.getMonth() + 1 })
  }
  return t("time.dayMonthYear", { d: date.getDate(), m: date.getMonth() + 1, y: date.getFullYear() })
}

function shouldShowDateSeparator(currentMsg: string, prevMsg: string | null): boolean {
  if (!prevMsg) return true
  const cur = parseUTCDate(currentMsg)
  const prev = parseUTCDate(prevMsg)
  return cur.getDate() !== prev.getDate() || cur.getMonth() !== prev.getMonth() || cur.getFullYear() !== prev.getFullYear()
}

function formatFileSize(bytes: number | null): string {
  if (!bytes) return ""
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

export function MessagesPage() {
  const { user, setUnreadCount, refreshUnreadCount } = useApp()
  const { t } = useTranslation()
  const location = useLocation()
  const [conversations, setConversations] = useState<ConversationItem[]>([])
  const [selectedConvo, setSelectedConvo] = useState<ConversationItem | null>(null)
  const [messages, setMessages] = useState<MessageItem[]>([])
  const [message, setMessage] = useState("")
  const [searchQuery, setSearchQuery] = useState("")
  const [showInfoPanel, setShowInfoPanel] = useState(false)
  const [loading, setLoading] = useState(true)
  const [messagesLoading, setMessagesLoading] = useState(false)
  const [groupMembers, setGroupMembers] = useState<GroupMemberItem[]>([])
  const [typingUser, setTypingUser] = useState<string | null>(null)

  // New conversation dialog
  const [newConvoSearch, setNewConvoSearch] = useState("")
  const [searchResults, setSearchResults] = useState<SearchUserResult[]>([])
  const [searching, setSearching] = useState(false)
  const [newConvoOpen, setNewConvoOpen] = useState(false)

  // Group create dialog
  const [groupCreateOpen, setGroupCreateOpen] = useState(false)
  const [groupName, setGroupName] = useState("")
  const [groupSearchQuery, setGroupSearchQuery] = useState("")
  const [groupSearchResults, setGroupSearchResults] = useState<SearchUserResult[]>([])
  const [selectedGroupMembers, setSelectedGroupMembers] = useState<SearchUserResult[]>([])

  // Reply & Reactions
  const [replyToMsg, setReplyToMsg] = useState<MessageItem | null>(null)
  const [reactionPickerMsgId, setReactionPickerMsgId] = useState<string | null>(null)

  // Invite member to group
  const [inviteSearchQuery, setInviteSearchQuery] = useState("")
  const [inviteSearchResults, setInviteSearchResults] = useState<SearchUserResult[]>([])
  const [inviting, setInviting] = useState(false)

  // Leave / Disband group confirm dialog
  const [groupActionDialog, setGroupActionDialog] = useState<"leave" | "disband" | null>(null)

  // Media & Files gallery in info panel
  const [infoTab, setInfoTab] = useState<"info" | "media" | "files">("info")
  const [mediaItems, setMediaItems] = useState<MediaItem[]>([])
  const [mediaLoading, setMediaLoading] = useState(false)
  useEffect(() => {
    if (!reactionPickerMsgId) return
    const handleClick = () => setReactionPickerMsgId(null)
    const timer = setTimeout(() => document.addEventListener("click", handleClick), 0)
    return () => { clearTimeout(timer); document.removeEventListener("click", handleClick) }
  }, [reactionPickerMsgId])

  // File upload
  const fileInputRef = useRef<HTMLInputElement>(null)
  const imageInputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)

  // Sidebar collapse
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  // Image lightbox
  const [lightboxImages, setLightboxImages] = useState<string[]>([])
  const [lightboxIndex, setLightboxIndex] = useState(0)

  // Lightbox keyboard controls
  useEffect(() => {
    if (lightboxImages.length === 0) return
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setLightboxImages([])
      else if (e.key === "ArrowLeft") setLightboxIndex((prev) => (prev - 1 + lightboxImages.length) % lightboxImages.length)
      else if (e.key === "ArrowRight") setLightboxIndex((prev) => (prev + 1) % lightboxImages.length)
    }
    document.addEventListener("keydown", handleKey)
    return () => document.removeEventListener("keydown", handleKey)
  }, [lightboxImages])

  // Fetch media/files when info panel tab changes
  useEffect(() => {
    if (!showInfoPanel || !selectedConvo || infoTab === "info") return
    const mediaType = infoTab === "media" ? "image" as const : "file" as const
    setMediaLoading(true)
    setMediaItems([])
    const fetchMedia = selectedConvo.type === "group"
      ? messagingApi.getGroupMedia(selectedConvo.id, mediaType, 0, 100)
      : messagingApi.getConversationMedia(selectedConvo.id, mediaType, 0, 100)
    fetchMedia.then(setMediaItems).catch(console.error).finally(() => setMediaLoading(false))
  }, [showInfoPanel, selectedConvo?.id, infoTab])

  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const typingTimeoutRef = useRef<number | null>(null)
  const readDebounceRef = useRef<number | null>(null)
  const selectedConvoRef = useRef<ConversationItem | null>(null)

  // Keep ref in sync for use in event handlers
  useEffect(() => {
    selectedConvoRef.current = selectedConvo
  }, [selectedConvo])

  const currentUserId = user?.id

  // Auto resize textarea
  useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = "auto"
      textarea.style.height = Math.min(textarea.scrollHeight, 200) + "px"
    }
  }, [message])

  // Scroll to bottom
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [])

  // Track message count to only scroll on new messages, not reactions
  const prevMsgCountRef = useRef(0)
  useEffect(() => {
    if (messages.length !== prevMsgCountRef.current) {
      scrollToBottom()
      prevMsgCountRef.current = messages.length
    }
  }, [messages, scrollToBottom])

  // Load conversations
  const loadConversations = useCallback(async () => {
    try {
      const data = await messagingApi.getConversations()
      setConversations(data)
    } catch (err) {
      console.error("Failed to load conversations:", err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadConversations()
  }, [loadConversations])

  // Auto-select group conversation when navigated from groups page
  useEffect(() => {
    const openGroupId = (location.state as { openGroupId?: string })?.openGroupId
    if (openGroupId && conversations.length > 0 && !selectedConvo) {
      const groupConvo = conversations.find(
        (c) => c.type === "group" && c.id === openGroupId
      )
      if (groupConvo) {
        setSelectedConvo(groupConvo)
        // Clear location state to prevent re-selecting on re-render
        window.history.replaceState({}, "")
      }
    }
  }, [location.state, conversations, selectedConvo])

  // Connect WebSocket
  useEffect(() => {
    if (!user) return

    const getWsToken = async () => {
      try {
        const resp = await fetch(
          `${import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"}/api/auth/ws-token`,
          { credentials: "include" }
        )
        if (resp.ok) {
          const data = await resp.json()
          wsManager.connect(data.token)
        }
      } catch (err) {
        console.error("Failed to get WS token:", err)
      }
    }

    getWsToken()

    return () => {
      wsManager.disconnect()
    }
  }, [user])

  // WebSocket message handlers
  useEffect(() => {
    const handleNewDirectMessage = (data: any) => {
      const msg = data.message as DirectMessageItem

      // Send delivery acknowledgement if receiver
      if (msg.receiver_id === currentUserId) {
        wsManager.send({ type: "msg_delivered", message_ids: [msg.id] })
      }

      // Update messages if this conversation is selected
      const curConvo = selectedConvoRef.current
      if (curConvo && curConvo.type === "direct" && msg.conversation_id === curConvo.id) {
        setMessages((prev) => {
          // Skip if real message already exists
          if (prev.some((m) => m.id === msg.id)) return prev
          // If sender is current user, replace the optimistic temp message
          if (msg.sender_id === currentUserId) {
            const tempIdx = prev.findIndex(
              (m) => m.id.startsWith("temp-") && (m as DirectMessageItem).sender_id === currentUserId && m.content === msg.content
            )
            if (tempIdx !== -1) {
              const updated = [...prev]
              updated[tempIdx] = msg
              return updated
            }
          }
          return [...prev, msg]
        })

        // Auto-mark as read if tab is focused and receiver is current user
        if (msg.receiver_id === currentUserId && document.hasFocus()) {
          if (readDebounceRef.current) clearTimeout(readDebounceRef.current)
          readDebounceRef.current = window.setTimeout(() => {
            wsManager.send({ type: "msg_read", conversation_id: msg.conversation_id })
          }, 1000)
        }
      }

      // Update conversation list + unread count
      loadConversations()
      refreshUnreadCount()
    }

    const handleNewGroupMessage = (data: any) => {
      const msg = data.message as GroupMessageItem
      const curConvo = selectedConvoRef.current

      if (curConvo && curConvo.type === "group" && msg.group_id === curConvo.id) {
        setMessages((prev) => {
          if (prev.some((m) => m.id === msg.id)) return prev
          // Replace optimistic temp message from same sender with same content
          if (msg.user_id === currentUserId) {
            const tempIdx = prev.findIndex(
              (m) => m.id.startsWith("temp-") && (m as GroupMessageItem).user_id === currentUserId && m.content === msg.content
            )
            if (tempIdx !== -1) {
              const updated = [...prev]
              updated[tempIdx] = msg
              return updated
            }
          }
          return [...prev, msg]
        })

        // Auto-mark group as read if focused
        if (msg.user_id !== currentUserId && document.hasFocus()) {
          wsManager.send({ type: "group_msg_read", group_id: msg.group_id })
        }
      }

      loadConversations()
      refreshUnreadCount()
    }

    const handleStatusUpdate = (data: any) => {
      // Update message status in current view
      const messageIds: string[] = data.message_ids || []
      const newStatus: string = data.status
      setMessages((prev) =>
        prev.map((m) => {
          if (messageIds.includes(m.id) && "sender_id" in m) {
            return {
              ...m,
              status: newStatus as DirectMessageItem["status"],
              is_read: newStatus === "seen" ? true : m.is_read,
              delivered_at: data.delivered_at || (m as DirectMessageItem).delivered_at,
              read_at: data.read_at || (m as DirectMessageItem).read_at,
            }
          }
          return m
        })
      )
    }

    const handleUnreadCountUpdate = (data: any) => {
      setUnreadCount(data.total_unread ?? 0)
    }

    const handleTyping = (data: any) => {
      const curConvo = selectedConvoRef.current
      if (curConvo && data.conversation_id === curConvo.id) {
        setTypingUser(data.username)
        if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current)
        typingTimeoutRef.current = window.setTimeout(() => setTypingUser(null), 3000)
      }
    }

    const handlePresenceUpdate = (data: any) => {
      const userId = data.user_id as string
      const isOnline = data.is_online as boolean
      const lastActivity = data.last_activity as string | null

      // Update conversation list
      setConversations((prev) =>
        prev.map((c) => {
          if (c.type === "direct" && c.other_user_id === userId) {
            return { ...c, is_online: isOnline, last_activity: isOnline ? null : (lastActivity || "Offline") }
          }
          return c
        })
      )

      // Update selected conversation if it matches
      const curConvo = selectedConvoRef.current
      if (curConvo && curConvo.type === "direct" && curConvo.other_user_id === userId) {
        setSelectedConvo((prev) =>
          prev ? { ...prev, is_online: isOnline, last_activity: isOnline ? null : (lastActivity || "Offline") } : prev
        )
      }
    }

    const handleReactionUpdate = (data: any) => {
      const messageId = data.message_id as string
      const reactions = data.reactions as ReactionItem[]
      setMessages((prev) =>
        prev.map((m) => (m.id === messageId ? { ...m, reactions } : m))
      )
    }

    const handleMessageDeleted = (data: any) => {
      const messageId = data.message_id as string
      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId
            ? { ...m, is_deleted: true, content: null, file_url: null, file_name: null }
            : m
        )
      )
    }

    wsManager.on("new_direct_message", handleNewDirectMessage)
    wsManager.on("new_group_message", handleNewGroupMessage)
    wsManager.on("msg_status_update", handleStatusUpdate)
    wsManager.on("unread_count_update", handleUnreadCountUpdate)
    wsManager.on("typing", handleTyping)
    wsManager.on("presence_update", handlePresenceUpdate)
    wsManager.on("reaction_update", handleReactionUpdate)
    wsManager.on("message_deleted", handleMessageDeleted)

    return () => {
      wsManager.off("new_direct_message", handleNewDirectMessage)
      wsManager.off("new_group_message", handleNewGroupMessage)
      wsManager.off("msg_status_update", handleStatusUpdate)
      wsManager.off("unread_count_update", handleUnreadCountUpdate)
      wsManager.off("typing", handleTyping)
      wsManager.off("presence_update", handlePresenceUpdate)
      wsManager.off("reaction_update", handleReactionUpdate)
      wsManager.off("message_deleted", handleMessageDeleted)
    }
  }, [currentUserId, loadConversations, refreshUnreadCount, setUnreadCount])

  // Load messages when conversation changes
  useEffect(() => {
    if (!selectedConvo) return
    setInfoTab("info")
    setMediaItems([])

    const loadMessages = async () => {
      setMessagesLoading(true)
      try {
        if (selectedConvo.type === "direct") {
          const msgs = await messagingApi.getDirectMessages(selectedConvo.id)
          setMessages(msgs)
          // Mark as read when opening conversation
          wsManager.send({ type: "msg_read", conversation_id: selectedConvo.id })
          refreshUnreadCount()
        } else {
          const msgs = await messagingApi.getGroupMessages(selectedConvo.id)
          setMessages(msgs)
          const members = await messagingApi.getGroupMembers(selectedConvo.id)
          setGroupMembers(members)
          // Mark group as read when opening
          wsManager.send({ type: "group_msg_read", group_id: selectedConvo.id })
          refreshUnreadCount()
        }
      } catch (err) {
        console.error("Failed to load messages:", err)
      } finally {
        setMessagesLoading(false)
      }
    }

    // Update conversation list to clear unread badge
    setConversations((prev) =>
      prev.map((c) => (c.id === selectedConvo.id ? { ...c, unread_count: 0 } : c))
    )
    setReplyToMsg(null)
    setReactionPickerMsgId(null)

    loadMessages()
  }, [selectedConvo, refreshUnreadCount])

  // Send "seen" event when tab regains focus while a conversation is open
  useEffect(() => {
    const handleFocus = () => {
      const convo = selectedConvoRef.current
      if (!convo) return
      if (readDebounceRef.current) clearTimeout(readDebounceRef.current)
      readDebounceRef.current = window.setTimeout(() => {
        if (convo.type === "direct") {
          wsManager.send({ type: "msg_read", conversation_id: convo.id })
        } else {
          wsManager.send({ type: "group_msg_read", group_id: convo.id })
        }
        refreshUnreadCount()
      }, 500)
    }

    window.addEventListener("focus", handleFocus)
    return () => window.removeEventListener("focus", handleFocus)
  }, [refreshUnreadCount])

  // Search users for new conversation
  useEffect(() => {
    if (!newConvoSearch.trim()) {
      setSearchResults([])
      return
    }

    const timer = setTimeout(async () => {
      setSearching(true)
      try {
        const results = await messagingApi.searchUsers(newConvoSearch)
        setSearchResults(results)
      } catch {
        setSearchResults([])
      } finally {
        setSearching(false)
      }
    }, 300)

    return () => clearTimeout(timer)
  }, [newConvoSearch])

  // Search users for group creation
  useEffect(() => {
    if (!groupSearchQuery.trim()) {
      setGroupSearchResults([])
      return
    }

    const timer = setTimeout(async () => {
      try {
        const results = await messagingApi.searchUsers(groupSearchQuery)
        setGroupSearchResults(results)
      } catch {
        setGroupSearchResults([])
      }
    }, 300)

    return () => clearTimeout(timer)
  }, [groupSearchQuery])

  // Send message
  const handleSendMessage = () => {
    if (!message.trim() || !selectedConvo || !currentUserId) return

    const content = message.trim()
    const tempId = `temp-${Date.now()}-${Math.random().toString(36).slice(2)}`
    const senderInfo = {
      id: currentUserId,
      username: user?.username || "",
      full_name: user?.full_name || null,
      avatar_url: user?.avatar_url || null,
    }

    // Build reply_to data for optimistic rendering
    const replyToData = replyToMsg
      ? {
          id: replyToMsg.id,
          content: replyToMsg.content,
          sender_name: replyToMsg.sender?.full_name || replyToMsg.sender?.username || "Unknown",
          message_type: replyToMsg.message_type,
          is_deleted: replyToMsg.is_deleted || false,
          file_url: replyToMsg.file_url,
        }
      : null

    // Optimistic: add message to UI immediately
    if (selectedConvo.type === "direct") {
      const optimisticMsg: DirectMessageItem = {
        id: tempId,
        conversation_id: selectedConvo.id,
        sender_id: currentUserId,
        receiver_id: selectedConvo.other_user_id || "",
        content,
        message_type: "text",
        file_url: null,
        file_name: null,
        file_size: null,
        is_read: false,
        status: "sent",
        delivered_at: null,
        read_at: null,
        created_at: new Date().toISOString(),
        sender: senderInfo,
        reply_to_id: replyToMsg?.id || null,
        reply_to: replyToData,
        is_deleted: false,
        reactions: [],
      }
      setMessages((prev) => [...prev, optimisticMsg])
    } else {
      const optimisticMsg: GroupMessageItem = {
        id: tempId,
        group_id: selectedConvo.id,
        user_id: currentUserId,
        content,
        message_type: "text",
        file_url: null,
        file_name: null,
        file_size: null,
        is_pinned: false,
        created_at: new Date().toISOString(),
        sender: senderInfo,
        reply_to_id: replyToMsg?.id || null,
        reply_to: replyToData,
        is_deleted: false,
        reactions: [],
      }
      setMessages((prev) => [...prev, optimisticMsg])
    }

    if (selectedConvo.type === "direct") {
      wsManager.send({
        type: "direct_message",
        conversation_id: selectedConvo.id,
        receiver_id: selectedConvo.other_user_id,
        content,
        message_type: "text",
        reply_to_id: replyToMsg?.id || undefined,
      })
    } else {
      wsManager.send({
        type: "group_message",
        group_id: selectedConvo.id,
        content,
        message_type: "text",
        reply_to_id: replyToMsg?.id || undefined,
      })
    }

    setMessage("")
    setReplyToMsg(null)
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
    }
  }

  // Handle file upload
  // Invite member search
  useEffect(() => {
    if (!inviteSearchQuery.trim()) {
      setInviteSearchResults([])
      return
    }
    const timer = setTimeout(async () => {
      try {
        const results = await messagingApi.searchUsers(inviteSearchQuery)
        // Filter out existing group members
        const memberIds = new Set(groupMembers.map(m => m.id))
        setInviteSearchResults(results.filter(u => !memberIds.has(u.id)))
      } catch (err) {
        console.error("Failed to search users:", err)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [inviteSearchQuery, groupMembers])

  const handleInviteMember = async (userId: string) => {
    if (!selectedConvo || selectedConvo.type !== "group") return
    setInviting(true)
    try {
      await groupService.addMember(selectedConvo.id, userId)
      // Reload group members
      const members = await messagingApi.getGroupMembers(selectedConvo.id)
      setGroupMembers(members)
      setInviteSearchQuery("")
      setInviteSearchResults([])
    } catch (err) {
      console.error("Failed to invite member:", err)
    } finally {
      setInviting(false)
    }
  }

  const handleFileUpload = async (file: File, _isImage: boolean) => {
    if (!selectedConvo || !currentUserId) return

    setUploading(true)
    try {
      const result = await messagingApi.uploadFile(file)

      if (selectedConvo.type === "direct") {
        wsManager.send({
          type: "direct_message",
          conversation_id: selectedConvo.id,
          receiver_id: selectedConvo.other_user_id,
          content: null,
          message_type: result.message_type,
          file_url: result.file_url,
          file_name: result.file_name,
          file_size: result.file_size,
        })
      } else {
        wsManager.send({
          type: "group_message",
          group_id: selectedConvo.id,
          content: null,
          message_type: result.message_type,
          file_url: result.file_url,
          file_name: result.file_name,
          file_size: result.file_size,
        })
      }
    } catch (err) {
      console.error("Upload failed:", err)
    } finally {
      setUploading(false)
    }
  }

  const handleMultiFileUpload = async (files: FileList, isImage: boolean) => {
    if (!selectedConvo || !currentUserId || files.length === 0) return

    const maxFiles = isImage ? 10 : 3
    const maxSize = 20 * 1024 * 1024 // 20MB

    const fileArray = Array.from(files).slice(0, maxFiles)
    const oversized = fileArray.filter(f => f.size > maxSize)
    if (oversized.length > 0) {
      alert(t("msg.fileTooLarge", { names: oversized.map(f => f.name).join(", ") }))
      return
    }

    setUploading(true)
    try {
      for (const file of fileArray) {
        await handleFileUpload(file, isImage)
      }
    } finally {
      setUploading(false)
    }
  }

  // Handle Paste
  const handlePaste = (e: React.ClipboardEvent) => {
    if (e.clipboardData.files && e.clipboardData.files.length > 0) {
      e.preventDefault()
      const files = e.clipboardData.files
      if (files.length === 1) {
        const isImage = files[0].type.startsWith("image/")
        handleFileUpload(files[0], isImage)
      } else {
        const isImage = Array.from(files).some((f) => f.type.startsWith("image/"))
        handleMultiFileUpload(files, isImage)
      }
    }
  }

  // Start new conversation
  const handleStartConversation = async (otherUser: SearchUserResult) => {
    try {
      const convo = await messagingApi.createConversation(otherUser.id)
      setNewConvoOpen(false)
      setNewConvoSearch("")
      await loadConversations()

      setSelectedConvo({
        id: convo.id,
        type: "direct",
        name: otherUser.full_name || otherUser.username,
        avatar_url: otherUser.avatar_url,
        last_message: null,
        last_message_at: null,
        unread_count: 0,
        is_online: null,
        other_user_id: otherUser.id,
      })
    } catch (err) {
      console.error("Failed to create conversation:", err)
    }
  }

  // Send friend request
  const handleSendFriendRequest = async (userId: string) => {
    try {
      await messagingApi.sendFriendRequest(userId)
      setSearchResults((prev) =>
        prev.map((r) => (r.id === userId ? { ...r, friendship_status: "pending" } : r))
      )
    } catch (err) {
      console.error("Failed to send friend request:", err)
    }
  }

  // Handle typing indicator
  const handleTypingIndicator = () => {
    if (!selectedConvo || selectedConvo.type !== "direct") return
    wsManager.send({
      type: "typing",
      target_id: selectedConvo.other_user_id,
      target_type: "direct",
      conversation_id: selectedConvo.id,
    })
  }

  // Handle react to message
  const handleReactMessage = (msgId: string, reaction: string) => {
    if (!selectedConvo || !currentUserId) return
    const scope = selectedConvo.type === "direct" ? "direct" : "group"

    // Optimistic update
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== msgId) return m
        const currentReactions = m.reactions || []
        const myExisting = currentReactions.find((r) => r.user_id === currentUserId)
        let newReactions: ReactionItem[]
        if (myExisting && myExisting.reaction === reaction) {
          // Remove
          newReactions = currentReactions.filter((r) => r.user_id !== currentUserId)
        } else if (myExisting) {
          // Update
          newReactions = currentReactions.map((r) =>
            r.user_id === currentUserId ? { ...r, reaction } : r
          )
        } else {
          // Add
          newReactions = [
            ...currentReactions,
            { id: `temp-${Date.now()}`, user_id: currentUserId, username: user?.full_name || user?.username || "", reaction },
          ]
        }
        return { ...m, reactions: newReactions }
      })
    )

    wsManager.send({
      type: "react_message",
      message_id: msgId,
      reaction,
      scope,
      conversation_id: selectedConvo.type === "direct" ? selectedConvo.id : undefined,
      group_id: selectedConvo.type === "group" ? selectedConvo.id : undefined,
    })
    setReactionPickerMsgId(null)
  }

  // Handle delete message
  const handleDeleteMessage = (msgId: string) => {
    if (!selectedConvo) return
    const scope = selectedConvo.type === "direct" ? "direct" : "group"
    wsManager.send({
      type: "delete_message",
      message_id: msgId,
      scope,
    })
  }

  // Reaction emoji list
  const reactionEmojis = ["👍", "❤️", "😆", "😮", "😢", "😠"]

  // Scroll to a specific message by ID
  const scrollToMessage = (msgId: string) => {
    const el = document.querySelector(`[data-msg-id="${msgId}"]`)
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" })
      el.classList.add("bg-accent/50")
      setTimeout(() => el.classList.remove("bg-accent/50"), 1500)
    }
  }

  // Filter conversations by search
  const filteredConversations = conversations.filter((c) =>
    c.name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const isMe = (senderId: string) => senderId === currentUserId

  return (
    <div className="flex h-[calc(100vh-56px)] md:h-screen">
      {/* Conversation List */}
      <div
        className={cn(
          "flex flex-col border-r border-border bg-card transition-all duration-300",
          sidebarCollapsed ? "w-0 md:w-[68px]" : "w-full md:w-[300px] lg:w-[320px]",
          selectedConvo && "hidden md:flex"
        )}
      >
        {/* Header */}
        <div className="flex h-14 items-center justify-between border-b border-border px-4 shrink-0">
          {!sidebarCollapsed && (
            <h2 className="font-semibold text-foreground whitespace-nowrap">{t("msg.title")}</h2>
          )}
          <div className={cn("flex items-center gap-1", sidebarCollapsed && "mx-auto")}>
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 text-muted-foreground shrink-0"
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              title={sidebarCollapsed ? t("msg.expand") : t("msg.collapse")}
            >
              <Menu className="h-4 w-4" />
            </Button>
          </div>
        </div>
        
        {!sidebarCollapsed && (
          <>
            {/* Action buttons */}
            <div className="flex items-center justify-end gap-1 px-4 pt-2">
            {/* New Conversation */}
            <Dialog open={newConvoOpen} onOpenChange={setNewConvoOpen}>
              <DialogTrigger asChild>
                <Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground">
                  <UserPlus className="h-4 w-4" />
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>{t("msg.searchUser")}</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 pt-2">
                  <Input
                    placeholder={t("msg.searchUserPlaceholder")}
                    value={newConvoSearch}
                    onChange={(e) => setNewConvoSearch(e.target.value)}
                    className="bg-secondary"
                  />
                  <div className="max-h-[300px] space-y-2 overflow-y-auto">
                    {searching && (
                      <div className="flex items-center justify-center py-4">
                        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                      </div>
                    )}
                    {!searching && searchResults.length === 0 && newConvoSearch.trim() && (
                      <p className="py-4 text-center text-sm text-muted-foreground">
                        {t("msg.noUserFound")}
                      </p>
                    )}
                    {searchResults.map((u) => (
                      <div
                        key={u.id}
                        className="flex w-full items-center gap-3 rounded-lg p-2 transition-colors hover:bg-secondary"
                      >
                        <Avatar className="h-9 w-9">
                          {u.avatar_url ? <AvatarImage src={u.avatar_url} /> : null}
                          <AvatarFallback className="bg-accent text-accent-foreground text-xs">
                            {getInitials(u.full_name || u.username)}
                          </AvatarFallback>
                        </Avatar>
                        <div className="flex-1">
                          <p className="text-sm font-medium text-foreground">
                            {u.full_name || u.username}
                          </p>
                          <p className="text-xs text-muted-foreground">{u.student_id}</p>
                        </div>
                        <div className="flex gap-1">
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 text-xs"
                            onClick={() => handleStartConversation(u)}
                          >
                            {t("msg.sendMessage")}
                          </Button>
                          {u.friendship_status === null && (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-7 text-xs"
                              onClick={() => handleSendFriendRequest(u.id)}
                            >
                              <UserPlus className="h-3 w-3" />
                            </Button>
                          )}
                          {u.friendship_status === "pending" && (
                            <span className="flex items-center text-xs text-muted-foreground">
                              {t("msg.sent")}
                            </span>
                          )}
                          {u.friendship_status === "accepted" && (
                            <span className="flex items-center text-xs text-emerald-500">
                              <Check className="mr-1 h-3 w-3" />
                              {t("msg.friends")}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </DialogContent>
            </Dialog>

            {/* Create Group */}
            <Dialog open={groupCreateOpen} onOpenChange={setGroupCreateOpen}>
              <DialogTrigger asChild>
                <Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground">
                  <Plus className="h-4 w-4" />
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>{t("msg.createGroup")}</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 pt-2">
                  <Input
                    placeholder={t("msg.groupName")}
                    value={groupName}
                    onChange={(e) => setGroupName(e.target.value)}
                    className="bg-secondary"
                  />
                  <div>
                    <p className="mb-2 text-sm font-medium text-foreground">{t("msg.addMembers")}</p>
                    <Input
                      placeholder={t("msg.searchPlaceholder")}
                      value={groupSearchQuery}
                      onChange={(e) => setGroupSearchQuery(e.target.value)}
                      className="mb-2 bg-secondary"
                    />
                    {selectedGroupMembers.length > 0 && (
                      <div className="mb-2 flex flex-wrap gap-1">
                        {selectedGroupMembers.map((m) => (
                          <Badge key={m.id} variant="secondary" className="gap-1">
                            {m.full_name || m.username}
                            <X
                              className="h-3 w-3 cursor-pointer"
                              onClick={() =>
                                setSelectedGroupMembers((prev) =>
                                  prev.filter((p) => p.id !== m.id)
                                )
                              }
                            />
                          </Badge>
                        ))}
                      </div>
                    )}
                    <div className="max-h-[200px] space-y-2 overflow-y-auto">
                      {groupSearchResults.map((u) => {
                        const isSelected = selectedGroupMembers.some((m) => m.id === u.id)
                        return (
                          <label
                            key={u.id}
                            className="flex cursor-pointer items-center gap-3 rounded-lg p-2 hover:bg-secondary"
                          >
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => {
                                if (isSelected) {
                                  setSelectedGroupMembers((prev) =>
                                    prev.filter((p) => p.id !== u.id)
                                  )
                                } else {
                                  setSelectedGroupMembers((prev) => [...prev, u])
                                }
                              }}
                              className="rounded border-border"
                            />
                            <Avatar className="h-8 w-8">
                              {u.avatar_url ? <AvatarImage src={u.avatar_url} /> : null}
                              <AvatarFallback className="bg-accent text-accent-foreground text-xs">
                                {getInitials(u.full_name || u.username)}
                              </AvatarFallback>
                            </Avatar>
                            <span className="text-sm text-foreground">
                              {u.full_name || u.username}
                            </span>
                          </label>
                        )
                      })}
                    </div>
                  </div>
                  <Button
                    className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
                    disabled={!groupName.trim() || selectedGroupMembers.length === 0}
                    onClick={async () => {
                      try {
                        const memberIds = selectedGroupMembers.map((m) => m.id)
                        const group = await messagingApi.createGroup(groupName.trim(), memberIds)
                        setGroupCreateOpen(false)
                        setGroupName("")
                        setSelectedGroupMembers([])
                        setGroupSearchQuery("")
                        await loadConversations()
                        // Select the new group
                        setSelectedConvo({
                          id: group.id,
                          type: "group",
                          name: groupName.trim(),
                          avatar_url: null,
                          last_message: null,
                          last_message_at: null,
                          unread_count: 0,
                          member_count: memberIds.length + 1,
                          member_avatars: selectedGroupMembers.slice(0, 2).map((m) => ({
                            avatar_url: m.avatar_url,
                            full_name: m.full_name || m.username,
                          })),
                        })
                      } catch (err) {
                        console.error("Failed to create group:", err)
                      }
                    }}
                  >
                    {t("msg.create")}
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
          </>
        )}

        {sidebarCollapsed && (
          <div className="flex flex-col items-center gap-2 p-2">
            <Button
              size="icon"
              variant="ghost"
              className="h-10 w-10 text-muted-foreground"
              title={t("msg.findUser")}
              onClick={() => { setSidebarCollapsed(false); setNewConvoOpen(true) }}
            >
              <UserPlus className="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className="h-10 w-10 text-muted-foreground"
              title={t("msg.createGroupTooltip")}
              onClick={() => { setSidebarCollapsed(false); setGroupCreateOpen(true) }}
            >
              <Plus className="h-4 w-4" />
            </Button>
          </div>
        )}

        {!sidebarCollapsed && (
        <>
        {/* Search */}
        <div className="p-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder={t("msg.searchConversations")}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-9 bg-secondary pl-9 text-sm"
            />
          </div>
        </div>

        {/* Conversation List */}
        <ScrollArea className="flex-1">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : filteredConversations.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-muted-foreground">
              {t("msg.noConversations")}
            </div>
          ) : (
            <div className="space-y-1 p-2">
              {filteredConversations.map((convo) => (
                <button
                  key={convo.id}
                  onClick={() => setSelectedConvo(convo)}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left transition-colors overflow-hidden",
                    selectedConvo?.id === convo.id ? "bg-accent" : "hover:bg-secondary"
                  )}
                >
                  <div className="relative shrink-0">
                    {convo.type === "group" && convo.member_avatars && convo.member_avatars.length >= 2 ? (
                      <div className="relative h-10 w-10">
                        <Avatar className="absolute bottom-0 left-0 h-7 w-7 border-2 border-card">
                          {convo.member_avatars[0].avatar_url ? <AvatarImage src={convo.member_avatars[0].avatar_url} /> : null}
                          <AvatarFallback className="bg-secondary text-secondary-foreground text-[9px]">
                            {getInitials(convo.member_avatars[0].full_name)}
                          </AvatarFallback>
                        </Avatar>
                        <Avatar className="absolute right-0 top-0 h-7 w-7 border-2 border-card">
                          {convo.member_avatars[1].avatar_url ? <AvatarImage src={convo.member_avatars[1].avatar_url} /> : null}
                          <AvatarFallback className="bg-accent text-accent-foreground text-[9px]">
                            {getInitials(convo.member_avatars[1].full_name)}
                          </AvatarFallback>
                        </Avatar>
                      </div>
                    ) : (
                      <Avatar className="h-10 w-10">
                        {convo.avatar_url ? <AvatarImage src={convo.avatar_url} /> : null}
                        <AvatarFallback className="bg-secondary text-secondary-foreground text-xs">
                          {convo.type === "group" ? (
                            <Users className="h-4 w-4" />
                          ) : (
                            getInitials(convo.name)
                          )}
                        </AvatarFallback>
                      </Avatar>
                    )}
                    {convo.is_online && convo.type === "direct" && (
                      <span className="absolute bottom-0 right-0 h-3 w-3 rounded-full border-2 border-card bg-emerald-500" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0 overflow-hidden">
                    <div className="flex items-center gap-2 overflow-hidden">
                      <p className={cn("truncate text-sm text-foreground min-w-0 flex-1", convo.unread_count > 0 ? "font-bold" : "font-medium")}>{convo.name}</p>
                      <span className={cn("shrink-0 text-xs whitespace-nowrap", convo.unread_count > 0 ? "font-semibold text-foreground" : "text-muted-foreground")}>
                        {convo.last_message_at ? formatTime(convo.last_message_at, t) : ""}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {convo.unread_count > 0 ? (
                        <p className="truncate text-xs font-semibold text-foreground min-w-0 flex-1">
                          {t("msg.newMessage")}
                        </p>
                      ) : (
                        <p className="truncate text-xs text-muted-foreground min-w-0 flex-1">
                          {convo.last_message || (convo.type === "direct" && !convo.is_online ? convo.last_activity : "")}
                        </p>
                      )}
                      {convo.unread_count > 0 && (
                        <Badge
                          variant="destructive"
                          className="ml-2 h-5 min-w-5 shrink-0 px-1.5 text-xs"
                        >
                          {convo.unread_count}
                        </Badge>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </ScrollArea>
        </>
        )}
      </div>

      {/* Chat Area */}
      <div
        className={cn(
          "flex flex-1 flex-col bg-background",
          !selectedConvo && "hidden md:flex"
        )}
      >
        {selectedConvo ? (
          <>
            {/* Chat Header */}
            <div className="flex h-14 items-center justify-between border-b border-border px-4">
              <div className="flex items-center gap-3">
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-8 w-8 hidden md:flex"
                  onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
                  title={sidebarCollapsed ? t("msg.showList") : t("msg.hideList")}
                >
                  {sidebarCollapsed ? <PanelLeft className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-8 w-8 md:hidden"
                  onClick={() => setSelectedConvo(null)}
                >
                  <ArrowLeft className="h-4 w-4" />
                </Button>
                <div className="relative">
                  {selectedConvo.type === "group" && selectedConvo.member_avatars && selectedConvo.member_avatars.length >= 2 ? (
                    <div className="relative h-8 w-8">
                      <Avatar className="absolute bottom-0 left-0 h-5.5 w-5.5 border-2 border-background">
                        {selectedConvo.member_avatars[0].avatar_url ? <AvatarImage src={selectedConvo.member_avatars[0].avatar_url} /> : null}
                        <AvatarFallback className="bg-secondary text-secondary-foreground text-[8px]">
                          {getInitials(selectedConvo.member_avatars[0].full_name)}
                        </AvatarFallback>
                      </Avatar>
                      <Avatar className="absolute right-0 top-0 h-5.5 w-5.5 border-2 border-background">
                        {selectedConvo.member_avatars[1].avatar_url ? <AvatarImage src={selectedConvo.member_avatars[1].avatar_url} /> : null}
                        <AvatarFallback className="bg-accent text-accent-foreground text-[8px]">
                          {getInitials(selectedConvo.member_avatars[1].full_name)}
                        </AvatarFallback>
                      </Avatar>
                    </div>
                  ) : (
                    <Avatar className="h-8 w-8">
                      {selectedConvo.avatar_url ? (
                        <AvatarImage src={selectedConvo.avatar_url} />
                      ) : null}
                      <AvatarFallback className="bg-secondary text-secondary-foreground text-xs">
                        {selectedConvo.type === "group" ? (
                          <Users className="h-3.5 w-3.5" />
                        ) : (
                          getInitials(selectedConvo.name)
                        )}
                      </AvatarFallback>
                    </Avatar>
                  )}
                  {selectedConvo.is_online && selectedConvo.type === "direct" && (
                    <span className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full border-2 border-background bg-emerald-500" />
                  )}
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">{selectedConvo.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {selectedConvo.type === "direct"
                      ? selectedConvo.is_online
                        ? t("msg.active")
                        : selectedConvo.last_activity || t("common.offline")
                      : t("msg.membersCount", { n: selectedConvo.member_count || 0 })}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-8 w-8 text-muted-foreground"
                  onClick={() => setShowInfoPanel(!showInfoPanel)}
                >
                  <Info className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {/* Messages + Info panel wrapper */}
            <div className="flex flex-1 overflow-hidden">
              {/* Messages */}
              <div className="flex flex-1 flex-col">
                <ScrollArea className="flex-1 p-4">
                  {messagesLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    </div>
                  ) : messages.length === 0 ? (
                    <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
                      {t("msg.startConversation")}
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {messages.map((msg, idx) => {
                        const senderId = "sender_id" in msg ? msg.sender_id : msg.user_id
                        const isMine = isMe(senderId)
                        const sender = msg.sender
                        const msgType = msg.message_type
                        const fileUrl = msg.file_url
                        const fileName = msg.file_name
                        const fileSize = msg.file_size
                        const deleted = msg.is_deleted
                        const reactions = msg.reactions || []
                        const replyTo = msg.reply_to
                        const prevMsgDate = idx > 0 ? messages[idx - 1].created_at : null
                        const showDateSep = shouldShowDateSeparator(msg.created_at, prevMsgDate)

                        return (
                          <div key={msg.id}>
                            {showDateSep && (
                              <div className="flex items-center justify-center py-2">
                                <span className="rounded-full bg-secondary px-3 py-1 text-xs text-muted-foreground">
                                  {formatDateSeparator(msg.created_at, t)}
                                </span>
                              </div>
                            )}
                            {msgType === "system" ? (
                              <div className="flex items-center justify-center py-1">
                                <span className="text-xs italic text-muted-foreground">
                                  {msg.content}
                                </span>
                              </div>
                            ) : (
                          <div
                            data-msg-id={msg.id}
                            className={cn(
                              "flex gap-3 rounded-lg transition-colors",
                              isMine ? "justify-end" : "justify-start"
                            )}
                          >
                            {!isMine && (
                              <Avatar className="h-8 w-8 shrink-0">
                                {sender?.avatar_url ? (
                                  <AvatarImage src={sender.avatar_url} />
                                ) : null}
                                <AvatarFallback className="bg-accent text-accent-foreground text-xs">
                                  {getInitials(sender?.full_name || sender?.username)}
                                </AvatarFallback>
                              </Avatar>
                            )}
                            <div className={cn("group relative max-w-[70%]", isMine ? "flex flex-col items-end" : "flex flex-col items-start")}>
                              {/* Hover action buttons */}
                              {!deleted && !msg.id.startsWith("temp-") && (
                                <div className={cn(
                                  "absolute -top-3 z-10 hidden items-center gap-0.5 rounded-lg border border-border bg-card px-1 py-0.5 shadow-sm group-hover:flex",
                                  isMine ? "right-0" : "left-0"
                                )}>
                                  <button
                                    onClick={(e) => { e.stopPropagation(); setReactionPickerMsgId(reactionPickerMsgId === msg.id ? null : msg.id) }}
                                    className="rounded p-1 text-muted-foreground hover:bg-secondary hover:text-foreground"
                                    title={t("msg.react")}
                                  >
                                    <SmilePlus className="h-3.5 w-3.5" />
                                  </button>
                                  <button
                                    onClick={() => { setReplyToMsg(msg); textareaRef.current?.focus() }}
                                    className="rounded p-1 text-muted-foreground hover:bg-secondary hover:text-foreground"
                                    title={t("msg.reply")}
                                  >
                                    <Reply className="h-3.5 w-3.5" />
                                  </button>
                                  {isMine && (
                                    <button
                                      onClick={() => handleDeleteMessage(msg.id)}
                                      className="rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                                      title={t("msg.deleteMessage")}
                                    >
                                      <Trash2 className="h-3.5 w-3.5" />
                                    </button>
                                  )}
                                </div>
                              )}

                              {/* Reaction picker popup */}
                              {reactionPickerMsgId === msg.id && (
                                <div
                                  className={cn(
                                    "absolute -top-10 z-20 flex items-center gap-1 rounded-full border border-border bg-card px-2 py-1 shadow-lg",
                                    isMine ? "right-0" : "left-0"
                                  )}
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  {reactionEmojis.map((emoji) => (
                                    <button
                                      key={emoji}
                                      onClick={() => handleReactMessage(msg.id, emoji)}
                                      className="rounded-full p-1 text-base transition-transform hover:scale-125 hover:bg-secondary"
                                    >
                                      {emoji}
                                    </button>
                                  ))}
                                </div>
                              )}

                              {/* Message bubble */}
                              <div
                                className={cn(
                                  "rounded-2xl px-4 py-2.5",
                                  isMine
                                    ? "bg-primary text-primary-foreground"
                                    : "border border-border bg-card text-card-foreground"
                                )}
                              >
                                {/* Sender name for group messages */}
                                {!isMine && selectedConvo.type === "group" && sender && (
                                  <p className="mb-1 text-xs font-medium opacity-70">
                                    {sender.full_name || sender.username}
                                  </p>
                                )}

                                {/* Reply-to preview */}
                                {replyTo && (
                                  <button
                                    onClick={() => scrollToMessage(replyTo.id)}
                                    className={cn(
                                      "mb-2 w-full cursor-pointer rounded-lg border-l-2 px-2.5 py-1.5 text-left text-xs transition-colors hover:opacity-80",
                                      isMine
                                        ? "border-primary-foreground/40 bg-primary-foreground/10"
                                        : "border-primary/40 bg-secondary"
                                    )}
                                  >
                                    <p className={cn("font-medium", isMine ? "text-primary-foreground/80" : "text-foreground/80")}>
                                      {replyTo.sender_name}
                                    </p>
                                    {replyTo.message_type === "image" && replyTo.file_url ? (
                                      <img
                                        src={replyTo.file_url}
                                        alt={t("msg.photo")}
                                        className="mt-1 max-h-[60px] rounded object-cover"
                                      />
                                    ) : (
                                      <p className={cn("truncate", isMine ? "text-primary-foreground/60" : "text-muted-foreground")}>
                                        {replyTo.is_deleted ? t("msg.deletedMessage") : replyTo.content || (replyTo.message_type === "file" ? t("msg.fileAttachment") : `[${replyTo.message_type}]`)}
                                      </p>
                                    )}
                                  </button>
                                )}

                                {/* Message content */}
                                {deleted ? (
                                  <p className={cn(
                                    "text-sm italic",
                                    isMine ? "text-primary-foreground/50" : "text-muted-foreground"
                                  )}>
                                    {t("msg.deletedMessage")}
                                  </p>
                                ) : msgType === "image" && fileUrl ? (
                                  <div>
                                    <img
                                      src={fileUrl}
                                      alt={fileName || "Image"}
                                      className="max-h-[300px] max-w-full cursor-pointer rounded-lg object-cover hover:opacity-90 transition-opacity"
                                      onClick={() => {
                                        const allImages = messages
                                          .filter(m => m.message_type === "image" && m.file_url)
                                          .map(m => m.file_url!)
                                        const idx = allImages.indexOf(fileUrl)
                                        setLightboxImages(allImages)
                                        setLightboxIndex(idx >= 0 ? idx : 0)
                                      }}
                                      loading="lazy"
                                      onLoad={() => scrollToBottom()}
                                    />
                                  </div>
                                ) : msgType === "file" && fileUrl ? (
                                  <a
                                    href={fileUrl}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex items-center gap-2"
                                  >
                                    <FileText
                                      className={cn(
                                        "h-4 w-4",
                                        isMine
                                          ? "text-primary-foreground/70"
                                          : "text-muted-foreground"
                                      )}
                                    />
                                    <div>
                                      <span className="text-sm underline">{fileName}</span>
                                      {fileSize != null && (
                                        <p
                                          className={cn(
                                            "text-xs",
                                            isMine
                                              ? "text-primary-foreground/50"
                                              : "text-muted-foreground"
                                          )}
                                        >
                                          {formatFileSize(fileSize)}
                                        </p>
                                      )}
                                    </div>
                                    <Download className="h-3.5 w-3.5 opacity-60" />
                                  </a>
                                ) : (
                                  <p className="whitespace-pre-wrap text-sm leading-relaxed">
                                    {msg.content}
                                  </p>
                                )}
                                <div
                                  className={cn(
                                    "mt-1 flex items-center gap-1 text-xs",
                                    isMine
                                      ? "justify-end text-primary-foreground/70"
                                      : "text-muted-foreground"
                                  )}
                                >
                                  <span>{formatMessageTime(msg.created_at, t)}</span>
                                  {/* Status indicator for sender's messages (direct only) */}
                                  {isMine && selectedConvo.type === "direct" && "status" in msg && (
                                    <>
                                      {msg.status === "seen" ? (
                                        <CheckCheck className="h-3.5 w-3.5 text-blue-400" />
                                      ) : msg.status === "delivered" ? (
                                        <CheckCheck className="h-3.5 w-3.5" />
                                      ) : (
                                        <Check className="h-3.5 w-3.5" />
                                      )}
                                    </>
                                  )}
                                </div>
                              </div>

                              {/* Reactions display */}
                              {reactions.length > 0 && (
                                <div className={cn(
                                  "-mt-1.5 flex flex-wrap gap-1",
                                  isMine ? "justify-end" : "justify-start"
                                )}>
                                  {Object.entries(
                                    reactions.reduce<Record<string, { count: number; users: string[] }>>((acc, r) => {
                                      if (!acc[r.reaction]) acc[r.reaction] = { count: 0, users: [] }
                                      acc[r.reaction].count++
                                      acc[r.reaction].users.push(r.username)
                                      return acc
                                    }, {})
                                  ).map(([emoji, info]) => (
                                    <button
                                      key={emoji}
                                      onClick={() => handleReactMessage(msg.id, emoji)}
                                      className="flex items-center gap-0.5 rounded-full border border-border bg-card px-1.5 py-0.5 text-xs shadow-sm transition-colors hover:bg-secondary"
                                      title={info.users.join(", ")}
                                    >
                                      <span>{emoji}</span>
                                      {info.count > 1 && <span className="text-muted-foreground">{info.count}</span>}
                                    </button>
                                  ))}
                                </div>
                              )}
                            </div>
                            {isMine && (
                              <Avatar className="h-8 w-8 shrink-0">
                                {user?.avatar_url ? (
                                  <AvatarImage src={user.avatar_url} />
                                ) : null}
                                <AvatarFallback className="bg-secondary text-secondary-foreground text-xs">
                                  {getInitials(user?.full_name || user?.username)}
                                </AvatarFallback>
                              </Avatar>
                            )}
                          </div>
                          )}
                          </div>
                        )
                      })}

                      {/* Typing indicator */}
                      {typingUser && (
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <span className="flex gap-1">
                            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:0ms]" />
                            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:150ms]" />
                            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:300ms]" />
                          </span>
                          {t("msg.typing", { name: typingUser })}
                        </div>
                      )}

                      <div ref={messagesEndRef} />
                    </div>
                  )}
                </ScrollArea>

                {/* Input */}
                <div className="border-t border-border p-4">
                  {/* Reply bar */}
                  {replyToMsg && (
                    <div className="mb-2 flex items-center gap-2 rounded-lg border border-border bg-secondary/50 px-3 py-2">
                      <Reply className="h-4 w-4 shrink-0 text-primary" />
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-medium text-foreground">
                          {t("msg.replyTo", { name: replyToMsg.sender?.full_name || replyToMsg.sender?.username || "" })}
                        </p>
                        {replyToMsg.message_type === "image" && replyToMsg.file_url ? (
                          <img src={replyToMsg.file_url} alt={t("msg.photo")} className="mt-1 max-h-[40px] rounded object-cover" />
                        ) : (
                          <p className="truncate text-xs text-muted-foreground">
                            {replyToMsg.is_deleted
                              ? t("msg.deletedMessage")
                              : replyToMsg.content || (replyToMsg.message_type === "file" ? t("msg.fileAttachment") : `[${replyToMsg.message_type}]`)}
                          </p>
                        )}
                      </div>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-6 w-6 shrink-0 text-muted-foreground"
                        onClick={() => setReplyToMsg(null)}
                      >
                        <X className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  )}
                  <div className="flex items-end gap-2">
                    <input
                      ref={fileInputRef}
                      type="file"
                      multiple
                      className="hidden"
                      onChange={(e) => {
                        const files = e.target.files
                        if (files && files.length > 0) {
                          if (files.length === 1) {
                            handleFileUpload(files[0], false)
                          } else {
                            handleMultiFileUpload(files, false)
                          }
                        }
                        e.target.value = ""
                      }}
                    />
                    <input
                      ref={imageInputRef}
                      type="file"
                      accept="image/*"
                      multiple
                      className="hidden"
                      onChange={(e) => {
                        const files = e.target.files
                        if (files && files.length > 0) {
                          if (files.length === 1) {
                            handleFileUpload(files[0], true)
                          } else {
                            handleMultiFileUpload(files, true)
                          }
                        }
                        e.target.value = ""
                      }}
                    />
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-9 w-9 shrink-0 text-muted-foreground"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={uploading}
                    >
                      <Paperclip className="h-4 w-4" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-9 w-9 shrink-0 text-muted-foreground"
                      onClick={() => imageInputRef.current?.click()}
                      disabled={uploading}
                    >
                      <ImageIcon className="h-4 w-4" />
                    </Button>
                    <Textarea
                      ref={textareaRef}
                      placeholder={t("msg.inputPlaceholder")}
                      value={message}
                      onChange={(e) => {
                        setMessage(e.target.value)
                        handleTypingIndicator()
                      }}
                      onPaste={handlePaste}
                      className="max-h-[200px] min-h-[36px] flex-1 resize-none bg-card"
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault()
                          handleSendMessage()
                        }
                      }}
                      rows={1}
                    />
                    <Button
                      size="icon"
                      className="h-9 w-9 shrink-0 bg-primary text-primary-foreground hover:bg-primary/90"
                      onClick={handleSendMessage}
                      disabled={!message.trim() || uploading}
                    >
                      {uploading ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Send className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </div>
              </div>

              {/* Info Panel */}
              {showInfoPanel && (
                <div className="hidden w-[260px] flex-col border-l border-border bg-card lg:flex">
                  <div className="flex h-14 items-center justify-between border-b border-border px-4">
                    <span className="text-sm font-medium text-foreground">{t("msg.details")}</span>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7 text-muted-foreground"
                      onClick={() => setShowInfoPanel(false)}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>

                  {/* Tabs */}
                  <div className="flex border-b border-border">
                    {(["info", "media", "files"] as const).map((tab) => (
                      <button
                        key={tab}
                        onClick={() => setInfoTab(tab)}
                        className={cn(
                          "flex-1 py-2 text-xs font-medium transition-colors",
                          infoTab === tab
                            ? "border-b-2 border-primary text-primary"
                            : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        {tab === "info" ? t("msg.tabInfo") : tab === "media" ? t("msg.tabMedia") : t("msg.tabFiles")}
                      </button>
                    ))}
                  </div>

                  <ScrollArea className="flex-1 p-4">
                    {/* Info tab */}
                    {infoTab === "info" && (
                    <div className="space-y-6">
                      {/* Avatar + Name */}
                      <div className="flex flex-col items-center text-center">
                        <Avatar className="h-16 w-16">
                          {selectedConvo.avatar_url ? (
                            <AvatarImage src={selectedConvo.avatar_url} />
                          ) : null}
                          <AvatarFallback className="bg-accent text-accent-foreground text-lg">
                            {selectedConvo.type === "group" ? (
                              <Users className="h-6 w-6" />
                            ) : (
                              getInitials(selectedConvo.name)
                            )}
                          </AvatarFallback>
                        </Avatar>
                        <p className="mt-2 font-medium text-foreground">{selectedConvo.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {selectedConvo.type === "group" ? t("msg.groupChat") : t("msg.directMessage")}
                        </p>
                        {selectedConvo.type === "direct" && (
                          <p className="mt-1 text-xs text-muted-foreground">
                            {selectedConvo.is_online ? (
                              <span className="text-emerald-500">{t("msg.activeStatus")}</span>
                            ) : (
                              selectedConvo.last_activity || t("common.offline")
                            )}
                          </p>
                        )}
                      </div>

                      {/* Members (group) */}
                      {selectedConvo.type === "group" && groupMembers.length > 0 && (
                        <div>
                          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                            {t("msg.membersSection", { n: groupMembers.length })}
                          </p>
                          <div className="space-y-2">
                            {groupMembers.map((member) => (
                              <div key={member.id} className="flex items-center gap-2">
                                <div className="relative">
                                  <Avatar className="h-7 w-7">
                                    {member.avatar_url ? (
                                      <AvatarImage src={member.avatar_url} />
                                    ) : null}
                                    <AvatarFallback className="bg-secondary text-secondary-foreground text-[10px]">
                                      {getInitials(member.full_name || member.username)}
                                    </AvatarFallback>
                                  </Avatar>
                                  {member.is_online && (
                                    <span className="absolute bottom-0 right-0 h-2 w-2 rounded-full border border-card bg-emerald-500" />
                                  )}
                                </div>
                                <div className="flex-1">
                                  <span className="text-xs text-foreground">
                                    {member.full_name || member.username}
                                  </span>
                                  {member.role === "owner" && (
                                    <span className="ml-1 text-[10px] text-muted-foreground">
                                      {t("msg.adminRole")}
                                    </span>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>

                          {/* Invite member */}
                          <div className="mt-3 space-y-2">
                            <div className="relative">
                              <UserPlus className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                              <Input
                                placeholder={t("msg.inviteMember")}
                                value={inviteSearchQuery}
                                onChange={(e) => setInviteSearchQuery(e.target.value)}
                                className="h-8 bg-secondary pl-8 text-xs"
                              />
                            </div>
                            {inviteSearchResults.length > 0 && (
                              <div className="max-h-[150px] space-y-1 overflow-y-auto rounded-lg border border-border bg-card p-1">
                                {inviteSearchResults.map((u) => (
                                  <button
                                    key={u.id}
                                    disabled={inviting}
                                    onClick={() => handleInviteMember(u.id)}
                                    className="flex w-full items-center gap-2 rounded-md p-1.5 text-left hover:bg-secondary transition-colors"
                                  >
                                    <Avatar className="h-6 w-6">
                                      {u.avatar_url ? <AvatarImage src={u.avatar_url} /> : null}
                                      <AvatarFallback className="bg-accent text-accent-foreground text-[9px]">
                                        {getInitials(u.full_name || u.username)}
                                      </AvatarFallback>
                                    </Avatar>
                                    <span className="text-xs text-foreground truncate">{u.full_name || u.username}</span>
                                    <Plus className="ml-auto h-3.5 w-3.5 shrink-0 text-primary" />
                                  </button>
                                ))}
                              </div>
                            )}
                          </div>

                          {/* Leave / Disband group */}
                          <div className="mt-4 space-y-2">
                            {groupMembers.find((m) => m.id === currentUserId && m.role === "owner") ? (
                              <Button
                                variant="destructive"
                                className="w-full gap-2 text-xs"
                                onClick={() => setGroupActionDialog("disband")}
                              >
                                <Trash2 className="h-3.5 w-3.5" /> {t("msg.disbandGroup")}
                              </Button>
                            ) : (
                              <Button
                                variant="outline"
                                className="w-full gap-2 text-xs text-destructive hover:text-destructive"
                                onClick={() => setGroupActionDialog("leave")}
                              >
                                <LogOut className="h-3.5 w-3.5" /> {t("msg.leaveGroup")}
                              </Button>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                    )}

                    {/* Media tab - Image grid grouped by month */}
                    {infoTab === "media" && (
                      <div>
                        {mediaLoading ? (
                          <div className="flex items-center justify-center py-8">
                            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                          </div>
                        ) : mediaItems.length === 0 ? (
                          <div className="py-8 text-center">
                            <ImageIcon className="mx-auto h-8 w-8 text-muted-foreground/50" />
                            <p className="mt-2 text-xs text-muted-foreground">{t("msg.noPhotos")}</p>
                          </div>
                        ) : (
                          Object.entries(
                            mediaItems.reduce<Record<string, MediaItem[]>>((groups, item) => {
                              const d = new Date(item.created_at)
                              const key = `${d.getMonth() + 1}-${d.getFullYear()}`
                              ;(groups[key] ||= []).push(item)
                              return groups
                            }, {})
                          ).map(([month, items]) => {
                            const [m, y] = month.split("-")
                            return (
                            <div key={month} className="mb-4">
                              <p className="mb-2 text-[11px] font-medium text-muted-foreground">{t("msg.monthYear", { m, y })}</p>
                              <div className="grid grid-cols-3 gap-1">
                                {items.map((item) => (
                                  <button
                                    key={item.id}
                                    className="aspect-square overflow-hidden rounded bg-secondary"
                                    onClick={() => {
                                      const allUrls = mediaItems.map((m) => m.file_url)
                                      setLightboxImages(allUrls)
                                      setLightboxIndex(allUrls.indexOf(item.file_url))
                                    }}
                                  >
                                    <img
                                      src={item.file_url}
                                      alt={item.file_name}
                                      className="h-full w-full object-cover"
                                      loading="lazy"
                                    />
                                  </button>
                                ))}
                              </div>
                            </div>
                          )})
                        )}
                      </div>
                    )}

                    {/* Files tab - File list grouped by month */}
                    {infoTab === "files" && (
                      <div>
                        {mediaLoading ? (
                          <div className="flex items-center justify-center py-8">
                            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                          </div>
                        ) : mediaItems.length === 0 ? (
                          <div className="py-8 text-center">
                            <FileText className="mx-auto h-8 w-8 text-muted-foreground/50" />
                            <p className="mt-2 text-xs text-muted-foreground">{t("msg.noFiles")}</p>
                          </div>
                        ) : (
                          Object.entries(
                            mediaItems.reduce<Record<string, MediaItem[]>>((groups, item) => {
                              const d = new Date(item.created_at)
                              const key = `${d.getMonth() + 1}-${d.getFullYear()}`
                              ;(groups[key] ||= []).push(item)
                              return groups
                            }, {})
                          ).map(([month, items]) => {
                            const [m, y] = month.split("-")
                            return (
                            <div key={month} className="mb-4">
                              <p className="mb-2 text-[11px] font-medium text-muted-foreground">{t("msg.monthYear", { m, y })}</p>
                              <div className="space-y-1.5">
                                {items.map((item) => (
                                  <a
                                    key={item.id}
                                    href={item.file_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex items-center gap-2 rounded-lg p-2 hover:bg-secondary transition-colors"
                                  >
                                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-primary/10">
                                      <FileText className="h-4 w-4 text-primary" />
                                    </div>
                                    <div className="min-w-0 flex-1">
                                      <p className="truncate text-xs font-medium text-foreground">
                                        {item.file_name}
                                      </p>
                                      <p className="text-[10px] text-muted-foreground">
                                        {formatFileSize(item.file_size)}
                                      </p>
                                    </div>
                                    <Download className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                                  </a>
                                ))}
                              </div>
                            </div>
                          )})
                        )}
                      </div>
                    )}
                  </ScrollArea>
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex flex-1 items-center justify-center">
            <div className="text-center">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-accent">
                <Send className="h-8 w-8 text-accent-foreground" />
              </div>
              <h3 className="text-lg font-semibold text-foreground">{t("msg.yourMessages")}</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                {t("msg.selectConversation")}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Image Lightbox */}
      {lightboxImages.length > 0 && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
          onClick={() => setLightboxImages([])}
        >
          {/* Close button */}
          <Button
            size="icon"
            variant="ghost"
            className="absolute right-4 top-4 z-10 h-10 w-10 text-white hover:bg-white/20"
            onClick={() => setLightboxImages([])}
          >
            <X className="h-6 w-6" />
          </Button>

          {/* Counter */}
          <div className="absolute top-4 left-1/2 -translate-x-1/2 text-sm text-white/80">
            {lightboxIndex + 1} / {lightboxImages.length}
          </div>

          {/* Previous button */}
          {lightboxImages.length > 1 && (
            <Button
              size="icon"
              variant="ghost"
              className="absolute left-4 z-10 h-12 w-12 text-white hover:bg-white/20"
              onClick={(e) => {
                e.stopPropagation()
                setLightboxIndex((prev) => (prev - 1 + lightboxImages.length) % lightboxImages.length)
              }}
            >
              <ChevronLeft className="h-8 w-8" />
            </Button>
          )}

          {/* Image */}
          <img
            src={lightboxImages[lightboxIndex]}
            alt={t("msg.preview")}
            className="max-h-[85vh] max-w-[90vw] rounded-lg object-contain"
            onClick={(e) => e.stopPropagation()}
          />

          {/* Next button */}
          {lightboxImages.length > 1 && (
            <Button
              size="icon"
              variant="ghost"
              className="absolute right-4 z-10 h-12 w-12 text-white hover:bg-white/20"
              onClick={(e) => {
                e.stopPropagation()
                setLightboxIndex((prev) => (prev + 1) % lightboxImages.length)
              }}
            >
              <ChevronRight className="h-8 w-8" />
            </Button>
          )}

          {/* Download button */}
          <a
            href={lightboxImages[lightboxIndex]}
            download
            target="_blank"
            rel="noopener noreferrer"
            className="absolute bottom-4 left-1/2 -translate-x-1/2"
            onClick={(e) => e.stopPropagation()}
          >
            <Button variant="ghost" className="text-white hover:bg-white/20 gap-2">
              <Download className="h-4 w-4" /> {t("msg.downloadFile")}
            </Button>
          </a>
        </div>
      )}

      {/* Leave / Disband Group Confirm Dialog */}
      <AlertDialog open={groupActionDialog !== null} onOpenChange={(open) => { if (!open) setGroupActionDialog(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {groupActionDialog === "disband" ? t("msg.disbandGroup") : t("msg.leaveGroup")}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {groupActionDialog === "disband"
                ? t("msg.confirmDisband")
                : t("msg.confirmLeave")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("common.cancel")}</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={async () => {
                if (!selectedConvo) return
                try {
                  if (groupActionDialog === "disband") {
                    await groupService.deleteGroup(selectedConvo.id)
                  } else {
                    await groupService.leaveGroup(selectedConvo.id)
                  }
                  const leftId = selectedConvo.id
                  setSelectedConvo(null)
                  setShowInfoPanel(false)
                  setGroupActionDialog(null)
                  setConversations((prev) => prev.filter((c) => c.id !== leftId))
                } catch (err) {
                  console.error("Failed to leave/disband group:", err)
                }
              }}
            >
              {groupActionDialog === "disband" ? t("msg.disband") : t("msg.leave")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
