import { useState, useEffect, useRef, useCallback } from "react"
import {
  Bot,
  Send,
  Plus,
  Search,
  MoreVertical,
  Trash2,
  ArrowLeft,
  Loader2,
  PanelLeftClose,
  PanelLeft,
  Menu,
  FileText,
  X,
  Paperclip,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useChatSessions, useChatMessages, useChatAsk } from "@/hooks/use-chat"
import { useToast } from "@/hooks/use-toast"
import { MarkdownMessage } from "@/components/markdown-message"
import { documentService } from "@/services/document.service"
import type { ChatMessage } from "@/types/api"

// Extended local message type for optimistic updates and file display
type AttachedFileInfo = {
  name: string
  size: number
  type: string
}

type LocalMessage = ChatMessage & {
  attachedFiles?: AttachedFileInfo[]
  isOptimistic?: boolean
  isLoading?: boolean
}

const MAX_FILES = 3
const MAX_FILE_SIZE_MB = 20
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
const ALLOWED_MIME = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
]

export function AIChatPage() {
  const [selectedChat, setSelectedChat] = useState<string | null>(null)
  const [isDraftMode, setIsDraftMode] = useState(true)
  const [message, setMessage] = useState("")
  const [searchQuery, setSearchQuery] = useState("")
  const [historyCollapsed, setHistoryCollapsed] = useState(false)
  const [attachedFiles, setAttachedFiles] = useState<File[]>([])
  const [isDragging, setIsDragging] = useState(false)
  const [localMessages, setLocalMessages] = useState<LocalMessage[]>([])
  const [isSending, setIsSending] = useState(false)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const dragCounterRef = useRef(0)
  const { toast } = useToast()

  const { sessions, loading: sessionsLoading, createSession, deleteSession } = useChatSessions()
  const { messages, loading: messagesLoading, refetch: refetchMessages } = useChatMessages(selectedChat)
  const { askInSession } = useChatAsk()

  // Sync fetched messages into localMessages (only when not in the middle of sending)
  useEffect(() => {
    if (!isSending) {
      setLocalMessages(messages as LocalMessage[])
    }
  }, [messages, isSending])

  // Auto-scroll to bottom when local messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [localMessages])

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = "auto"
      textarea.style.height = Math.min(textarea.scrollHeight, 200) + "px"
    }
  }, [message])

  // Reset state when entering draft mode (new chat)
  useEffect(() => {
    if (isDraftMode) {
      setLocalMessages([])
    }
  }, [isDraftMode])

  const filteredConversations = sessions.filter((c) =>
    c.title.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const generateTitle = (msg: string): string => {
    if (msg.length <= 50) return msg
    const title = msg.substring(0, 50)
    const lastSpace = title.lastIndexOf(" ")
    return (lastSpace > 20 ? title.substring(0, lastSpace) : title) + "..."
  }

  // Start new chat (draft mode)
  // Validate & add files helper
  const addFiles = useCallback((incoming: FileList | File[]) => {
    const files = Array.from(incoming)
    const accepted: File[] = []
    const errors: string[] = []

    for (const file of files) {
      if (!ALLOWED_MIME.includes(file.type)) {
        errors.push(`"${file.name}" không được hỗ trợ (chỉ PDF, DOCX, TXT)`)
        continue
      }
      if (file.size > MAX_FILE_SIZE_BYTES) {
        errors.push(`"${file.name}" vượt quá ${MAX_FILE_SIZE_MB} MB`)
        continue
      }
      accepted.push(file)
    }

    if (errors.length) {
      toast({ title: 'File không hợp lệ', description: errors.join('\n'), variant: 'destructive' })
    }

    if (accepted.length) {
      setAttachedFiles((prev) => {
        const combined = [...prev, ...accepted]
        if (combined.length > MAX_FILES) {
          toast({
            title: 'Giới hạn file',
            description: `Chỉ được đính kèm tối đa ${MAX_FILES} file. ${combined.length - MAX_FILES} file bị bỏ qua.`,
            variant: 'destructive',
          })
        }
        return combined.slice(0, MAX_FILES)
      })
    }
  }, [toast])

  const handleNewChat = () => {
    setSelectedChat(null)
    setIsDraftMode(true)
    setAttachedFiles([])
    setLocalMessages([])
  }

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await deleteSession(sessionId)
      if (selectedChat === sessionId) {
        handleNewChat()
      }
      toast({
        title: "Success",
        description: "Chat session deleted",
      })
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to delete session",
        variant: "destructive",
      })
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addFiles(e.target.files)
    }
    e.target.value = ""
  }

  const handleRemoveFile = (index: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index))
  }

  // ── Drag & Drop ────────────────────────────────────────────────
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    dragCounterRef.current++
    if (e.dataTransfer.types.includes("Files")) {
      setIsDragging(true)
    }
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    dragCounterRef.current--
    if (dragCounterRef.current === 0) {
      setIsDragging(false)
    }
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    dragCounterRef.current = 0
    setIsDragging(false)
    if (e.dataTransfer.files.length > 0) {
      addFiles(e.dataTransfer.files)
    }
  }, [addFiles])

  // ── Send Message ───────────────────────────────────────────────
  const handleSendMessage = async () => {
    if (!message.trim() && attachedFiles.length === 0) return

    const userMessage = message.trim()
    const currentFiles = [...attachedFiles]

    // Clear input immediately
    setMessage("")
    setAttachedFiles([])
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
    }

    // ── Optimistic: add user message + AI loading bubble ──────
    const optimisticUserId = `opt-user-${Date.now()}`
    const optimisticAiId = `opt-ai-${Date.now()}`
    const optimisticUser: LocalMessage = {
      id: optimisticUserId,
      session_id: selectedChat || "draft",
      user_id: "me",
      role: "user",
      content: userMessage,
      retrieved_chunks: [],
      total_tokens: 0,
      confidence_score: null,
      created_at: new Date().toISOString(),
      isOptimistic: true,
      attachedFiles: currentFiles.map((f) => ({ name: f.name, size: f.size, type: f.type })),
    }
    const optimisticAi: LocalMessage = {
      id: optimisticAiId,
      session_id: selectedChat || "draft",
      user_id: "ai",
      role: "assistant",
      content: "",
      retrieved_chunks: [],
      total_tokens: 0,
      confidence_score: null,
      created_at: new Date().toISOString(),
      isOptimistic: true,
      isLoading: true,
    }

    setLocalMessages((prev) => [...prev, optimisticUser, optimisticAi])
    setIsSending(true)

    try {
      let chatId = selectedChat
      let isNewSession = false

      if (isDraftMode || !selectedChat) {
        isNewSession = true
        const firstFileName = currentFiles[0]?.name
        const autoTitle = generateTitle(userMessage || firstFileName || "File chat")
        const newSession = await createSession({
          title: autoTitle,
          session_type: "general",
          model_name: "llama3.2:1b",
        })
        chatId = newSession.id
      }

      const askOptions: any = {}

      // Upload all files concurrently and collect document IDs
      if (currentFiles.length > 0) {
        const uploadResults = await Promise.allSettled(
          currentFiles.map((file) =>
            documentService.uploadDocument({
              file,
              title: file.name.replace(/\.[^/.]+$/, ""),
              category: "document",
            })
          )
        )

        const docIds: string[] = []
        const failedFiles: string[] = []
        uploadResults.forEach((result, i) => {
          if (result.status === "fulfilled") {
            docIds.push(result.value.id)
          } else {
            failedFiles.push(currentFiles[i].name)
            console.error(`Upload failed for ${currentFiles[i].name}:`, result.reason)
          }
        })

        if (failedFiles.length) {
          toast({
            title: "Một số file không upload được",
            description: failedFiles.join(", "),
            variant: "destructive",
          })
        }

        if (docIds.length) {
          // ── Poll until all docs are embedded in Qdrant (max 45 s) ──
          const POLL_INTERVAL = 3000
          const MAX_WAIT = 45_000
          const pollStart = Date.now()

          setLocalMessages((prev) =>
            prev.map((m) =>
              m.id === optimisticAiId
                ? { ...m, content: "⏳ Đang xử lý file..." }
                : m
            )
          )

          while (Date.now() - pollStart < MAX_WAIT) {
            await new Promise((r) => setTimeout(r, POLL_INTERVAL))
            try {
              const statuses = await documentService.checkBatchProcessingStatus(docIds)
              const allDone = statuses.every(
                (s) => s.is_processed || s.processing_status === "failed"
              )
              if (allDone) break
            } catch {
              // ignore polling errors; proceed after timeout
              break
            }
          }

          // Reset loading state back to spinning dots before the AI call
          setLocalMessages((prev) =>
            prev.map((m) =>
              m.id === optimisticAiId ? { ...m, content: "" } : m
            )
          )

          askOptions.document_ids = docIds
          askOptions.top_k = 5
          askOptions.score_threshold = 0.5
        }
      }

      const response = await askInSession(chatId!, userMessage, askOptions)

      // Replace optimistic messages with real ones
      setLocalMessages((prev) => {
        const filtered = prev.filter(
          (m) => m.id !== optimisticUserId && m.id !== optimisticAiId
        )
        const realUser: LocalMessage = {
          ...(response.user_message as LocalMessage),
          attachedFiles: currentFiles.map((f) => ({ name: f.name, size: f.size, type: f.type })),
        }
        return [...filtered, realUser, response.ai_message as LocalMessage]
      })

      if (isNewSession) {
        setSelectedChat(chatId)
        setIsDraftMode(false)
      } else {
        setTimeout(() => refetchMessages(), 300)
      }
    } catch (error: any) {
      setLocalMessages((prev) =>
        prev.filter((m) => m.id !== optimisticUserId && m.id !== optimisticAiId)
      )
      toast({
        title: "Error",
        description: error.message || "Failed to send message",
        variant: "destructive",
      })
      setMessage(userMessage)
      setAttachedFiles(currentFiles)
    } finally {
      setIsSending(false)
    }
  }

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffMins = Math.floor((now.getTime() - date.getTime()) / 60000)
    if (diffMins < 1) return "Just now"
    if (diffMins < 60) return `${diffMins}m ago`
    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours}h ago`
    return date.toLocaleDateString()
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  // ── Render ─────────────────────────────────────────────────────
  return (
    <div className="flex h-[calc(100vh-56px)] md:h-screen">
      {/* ── Conversation List ── */}
      <div
        className={cn(
          "flex flex-col border-r border-border bg-card transition-all duration-300",
          historyCollapsed ? "w-0 md:w-[68px]" : "w-full md:w-[300px] lg:w-[320px]",
          selectedChat && "hidden md:flex"
        )}
      >
        {/* Header */}
        <div className="flex h-14 items-center justify-between border-b border-border px-4 shrink-0">
          {!historyCollapsed && (
            <h2 className="font-semibold text-foreground whitespace-nowrap">AI Chats</h2>
          )}
          <Button
            size="icon"
            variant="ghost"
            className={cn("h-8 w-8 text-muted-foreground shrink-0", historyCollapsed && "mx-auto")}
            onClick={() => setHistoryCollapsed(!historyCollapsed)}
            title={historyCollapsed ? "Mở rộng lịch sử" : "Thu gọn lịch sử trò chuyện"}
          >
            <Menu className="h-4 w-4" />
          </Button>
        </div>

        {/* Search & New Chat */}
        {!historyCollapsed && (
          <div className="p-3 space-y-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search conversations..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-9 bg-secondary pl-9 text-sm"
              />
            </div>
            <Button
              variant="outline"
              className="w-full justify-start gap-2"
              size="sm"
              onClick={handleNewChat}
            >
              <Plus className="h-4 w-4" />
              <span>Thêm đoạn chat mới</span>
            </Button>
          </div>
        )}

        {historyCollapsed && (
          <div className="p-2">
            <Button
              size="icon"
              variant="outline"
              className="w-full h-10"
              title="Thêm đoạn chat mới"
              onClick={handleNewChat}
            >
              <Plus className="h-4 w-4" />
            </Button>
          </div>
        )}

        {/* Session List */}
        <ScrollArea className="flex-1">
          {!historyCollapsed && (
            <>
              {sessionsLoading ? (
                <div className="flex items-center justify-center p-4">
                  <Loader2 className="h-6 w-6 animate-spin text-primary" />
                </div>
              ) : filteredConversations.length === 0 ? (
                <div className="p-4 text-center text-sm text-muted-foreground">
                  No chats yet. Start a new conversation!
                </div>
              ) : (
                <div className="space-y-1 p-2">
                  {filteredConversations.map((chat) => (
                    <button
                      key={chat.id}
                      onClick={() => {
                        setSelectedChat(chat.id)
                        setIsDraftMode(false)
                      }}
                      className={cn(
                        "flex w-full items-center rounded-lg transition-colors px-3 py-2.5 text-left",
                        selectedChat === chat.id && !isDraftMode
                          ? "bg-accent"
                          : "hover:bg-secondary"
                      )}
                    >
                      <div className="flex-1 overflow-hidden">
                        <div className="flex items-center justify-between gap-2">
                          <p className="truncate text-sm font-medium text-foreground">{chat.title}</p>
                          <span className="shrink-0 text-xs text-muted-foreground">
                            {formatTimestamp(chat.updated_at)}
                          </span>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
        </ScrollArea>
      </div>

      {/* ── Chat Area ── */}
      <div
        className={cn(
          "flex flex-1 flex-col bg-background relative",
          !selectedChat && !isDraftMode && "hidden md:flex"
        )}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        {/* Drag-and-drop overlay */}
        {isDragging && (
          <div className="absolute inset-0 z-50 flex items-center justify-center bg-primary/10 border-2 border-dashed border-primary rounded-lg pointer-events-none">
            <div className="text-center">
              <Paperclip className="h-12 w-12 mx-auto mb-3 text-primary" />
              <p className="text-lg font-semibold text-primary">Thả file vào đây</p>
              <p className="text-sm text-muted-foreground">PDF, DOCX, TXT</p>
            </div>
          </div>
        )}

        {selectedChat || isDraftMode ? (
          <>
            {/* Chat Header */}
            <div className="flex h-14 items-center justify-between border-b border-border px-4">
              <div className="flex items-center gap-3">
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-8 w-8 hidden md:flex"
                  onClick={() => setHistoryCollapsed(!historyCollapsed)}
                  title={historyCollapsed ? "Show chat history" : "Hide chat history"}
                >
                  {historyCollapsed ? (
                    <PanelLeft className="h-4 w-4" />
                  ) : (
                    <PanelLeftClose className="h-4 w-4" />
                  )}
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-8 w-8 md:hidden"
                  onClick={() => setSelectedChat(null)}
                >
                  <ArrowLeft className="h-4 w-4" />
                </Button>
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">
                    {isDraftMode
                      ? "New Chat"
                      : sessions.find((c) => c.id === selectedChat)?.title}
                  </p>
                  <p className="text-xs text-muted-foreground">AI Tutor</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {!isDraftMode && selectedChat && (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={() => handleDeleteSession(selectedChat!)}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete Chat
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                )}
              </div>
            </div>

            {/* Messages */}
            <ScrollArea className="flex-1 p-4">
              <div className="mx-auto max-w-3xl space-y-6">
                {messagesLoading && !isDraftMode && localMessages.length === 0 ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                  </div>
                ) : (isDraftMode || localMessages.length === 0) ? (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <img
                      src="/logo.png"
                      alt="Logo"
                      className="h-16 w-16 object-contain mb-4"
                    />
                    <h3 className="text-lg font-semibold text-foreground mb-2">
                      {isDraftMode ? "Bắt đầu cuộc trò chuyện mới" : "No messages yet"}
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      {isDraftMode
                        ? "Gửi tin nhắn để bắt đầu. Hệ thống sẽ tự động tạo tiêu đề cho bạn."
                        : "Start the conversation!"}
                    </p>
                  </div>
                ) : (
                  localMessages.map((msg) => (
                    <div
                      key={msg.id}
                      className={cn(
                        "flex gap-3",
                        msg.role === "user" ? "justify-end" : "justify-start"
                      )}
                    >
                      {msg.role === "assistant" && (
                        <Avatar className="h-8 w-8 shrink-0 border border-border">
                          <AvatarFallback className="bg-primary/10 text-primary text-xs">
                            <Bot className="h-4 w-4" />
                          </AvatarFallback>
                        </Avatar>
                      )}
                      <div className={cn("flex flex-col gap-1", msg.role === "user" ? "items-end" : "items-start")}>
                        {/* Attached file chips – shown above the text bubble */}
                        {msg.attachedFiles && msg.attachedFiles.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 max-w-[320px]">
                            {msg.attachedFiles.map((f, idx) => (
                              <div
                                key={idx}
                                className="flex items-center gap-1.5 rounded-xl border border-border bg-secondary/70 px-2.5 py-1.5 text-xs"
                              >
                                <FileText className="h-3.5 w-3.5 shrink-0 text-primary" />
                                <div className="overflow-hidden max-w-[160px]">
                                  <p className="truncate font-medium text-foreground">{f.name}</p>
                                  <p className="text-muted-foreground">{formatFileSize(f.size)}</p>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                        {/* Message bubble */}
                        <div
                          className={cn(
                            "max-w-[80%] rounded-2xl px-4 py-3",
                            msg.role === "user"
                              ? "bg-primary text-primary-foreground"
                              : "bg-secondary text-secondary-foreground"
                          )}
                        >
                          {msg.isLoading ? (
                            <div className="flex flex-col gap-1.5 py-1">
                              {msg.content ? (
                                <span className="text-sm opacity-80">{msg.content}</span>
                              ) : null}
                              <div className="flex items-center gap-1.5">
                                <span className="h-2 w-2 rounded-full bg-current animate-bounce [animation-delay:-0.3s]" />
                                <span className="h-2 w-2 rounded-full bg-current animate-bounce [animation-delay:-0.15s]" />
                                <span className="h-2 w-2 rounded-full bg-current animate-bounce" />
                              </div>
                            </div>
                          ) : (
                            <>
                              <MarkdownMessage content={msg.content} role={msg.role as "user" | "assistant"} />
                              {!msg.isOptimistic && (
                                <span className="mt-1 block text-xs opacity-70">
                                  {formatTimestamp(msg.created_at)}
                                </span>
                              )}
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  ))
                )}
                <div ref={messagesEndRef} />
              </div>
            </ScrollArea>

            {/* ── Input Area ── */}
            <div className="border-t border-border p-4">
              <div className="mx-auto max-w-3xl">
                {/* Attached file preview */}
                {attachedFiles.length > 0 && (
                  <div className="mb-2 flex flex-wrap gap-2">
                    {attachedFiles.map((file, idx) => (
                      <div
                        key={idx}
                        className="flex items-center gap-2 rounded-lg border border-border bg-secondary/60 px-3 py-1.5 text-sm"
                      >
                        <FileText className="h-4 w-4 shrink-0 text-primary" />
                        <span className="truncate font-medium text-foreground max-w-[160px]">
                          {file.name}
                        </span>
                        <span className="text-muted-foreground shrink-0 text-xs">
                          {formatFileSize(file.size)}
                        </span>
                        <button
                          onClick={() => handleRemoveFile(idx)}
                          className="ml-1 rounded-full p-0.5 hover:bg-destructive/20 text-muted-foreground hover:text-destructive transition-colors"
                          aria-label="Remove file"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Input row */}
                <div className="flex items-end gap-2 rounded-xl border border-border bg-secondary px-3 py-2 focus-within:border-primary transition-colors">
                  {/* Hidden file input */}
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.docx,.txt"
                    multiple
                    className="hidden"
                    onChange={handleFileChange}
                  />
                  {/* "+" Attach button */}
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isSending || attachedFiles.length >= MAX_FILES}
                    title={attachedFiles.length >= MAX_FILES ? `Đã đạt giới hạn ${MAX_FILES} file` : "chứ có thể đính kèm tối đa 3 file (PDF, DOCX, TXT)"}
                    className="shrink-0 mb-0.5 flex h-7 w-7 items-center justify-center rounded-full bg-muted text-muted-foreground hover:bg-primary/10 hover:text-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Plus className="h-4 w-4" />
                  </button>

                  {/* Textarea */}
                  <Textarea
                    ref={textareaRef}
                    placeholder="Ask me anything ..."
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault()
                        handleSendMessage()
                      }
                    }}
                    className="flex-1 bg-transparent border-0 shadow-none focus-visible:ring-0 min-h-[36px] max-h-[200px] resize-none p-0 py-0.5 text-sm placeholder:text-muted-foreground"
                    disabled={isSending}
                    rows={1}
                  />

                  {/* Send button */}
                  <Button
                    size="icon"
                    onClick={handleSendMessage}
                    disabled={(!message.trim() && attachedFiles.length === 0) || isSending}
                    className="shrink-0 h-8 w-8 mb-0.5"
                  >
                    {isSending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                  </Button>
                </div>
                <p className="mt-1.5 text-center text-xs text-muted-foreground">
                  Nhấn Enter để gửi · Shift+Enter xuống dòng · Đính kèm tối đa {MAX_FILES} file (PDF, DOCX, TXT ≤ {MAX_FILE_SIZE_MB} MB)
                </p>
              </div>
            </div>
          </>
        ) : (
          <div className="hidden md:flex flex-1 items-center justify-center">
            <div className="text-center">
              <Bot className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium text-foreground mb-2">No Chat Selected</h3>
              <p className="text-sm text-muted-foreground">
                Select a chat or create a new one to start
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}