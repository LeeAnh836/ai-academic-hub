import { useState, useEffect, useRef } from "react"
import {
  Bot,
  Send,
  Plus,
  Search,
  MoreVertical,
  Trash2,
  ArrowLeft,
  Loader2,
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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { useChatSessions, useChatMessages, useChatAsk } from "@/hooks/use-chat"
import { useToast } from "@/hooks/use-toast"
import { ChatDocumentSelector } from "@/components/chat-document-selector"

export function AIChatPage() {
  const [selectedChat, setSelectedChat] = useState<string | null>(null)
  const [message, setMessage] = useState("")
  const [searchQuery, setSearchQuery] = useState("")
  const [newSessionTitle, setNewSessionTitle] = useState("")
  const [documentSelectorOpen, setDocumentSelectorOpen] = useState(false)
  const [sessionDocuments, setSessionDocuments] = useState<string[]>([])
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const { toast } = useToast()

  const { sessions, loading: sessionsLoading, createSession, deleteSession } = useChatSessions()
  const { messages, loading: messagesLoading, refetch: refetchMessages } = useChatMessages(selectedChat)
  const { askInSession, loading: askLoading } = useChatAsk()

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px'
    }
  }, [message])

  const filteredConversations = sessions.filter((c) =>
    c.title.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const handleCreateSession = async () => {
    if (!newSessionTitle.trim()) {
      toast({
        title: "Error",
        description: "Please enter a title",
        variant: "destructive",
      })
      return
    }

    try {
      const newSession = await createSession({
        title: newSessionTitle,
        session_type: 'general',
        model_name: 'llama3.2:1b',
      })
      setSelectedChat(newSession.id)
      setNewSessionTitle("")
      setCreateDialogOpen(false)
      toast({
        title: "Success",
        description: "Chat session created",
      })
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to create session",
        variant: "destructive",
      })
    }
  }

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await deleteSession(sessionId)
      if (selectedChat === sessionId) {
        setSelectedChat(null)
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

  const handleSendMessage = async () => {
    if (!message.trim()) return
    if (!selectedChat) {
      toast({
        title: "Error",
        description: "Please create a chat session first",
        variant: "destructive",
      })
      return
    }

    const userMessage = message.trim()
    setMessage("")

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }

    try {
      // Ask AI directly (will save both user message and AI response)
      await askInSession(selectedChat, userMessage, {
        document_ids: sessionDocuments.length > 0 ? sessionDocuments : null,
        top_k: 5,
        score_threshold: 0.5,
      })
      
      // Refresh messages to show the conversation
      await refetchMessages()
      
      toast({
        title: "Success",
        description: "AI has responded to your question",
      })
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to send message",
        variant: "destructive",
      })
      setMessage(userMessage)  // Restore message on error
    }
  }

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    
    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    
    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours}h ago`
    
    return date.toLocaleDateString()
  }

  return (
    <div className="flex h-[calc(100vh-56px)] md:h-screen">
      {/* Conversation List */}
      <div
        className={cn(
          "flex w-full flex-col border-r border-border bg-card md:w-[300px] lg:w-[320px]",
          selectedChat && "hidden md:flex"
        )}
      >
        {/* Header */}
        <div className="flex h-14 items-center justify-between border-b border-border px-4">
          <h2 className="font-semibold text-foreground">AI Chats</h2>
          <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
            <DialogTrigger asChild>
              <Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground">
                <Plus className="h-4 w-4" />
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>New Chat Session</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 pt-4">
                <div>
                  <Label htmlFor="title">Session Title</Label>
                  <Input
                    id="title"
                    value={newSessionTitle}
                    onChange={(e) => setNewSessionTitle(e.target.value)}
                    placeholder="e.g. Math Homework Help"
                    className="mt-1"
                    onKeyDown={(e) => e.key === 'Enter' && handleCreateSession()}
                  />
                </div>
                <div className="flex gap-2">
                  <Button onClick={handleCreateSession} className="flex-1">
                    Create
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setCreateDialogOpen(false)
                      setNewSessionTitle("")
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {/* Search */}
        <div className="p-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search conversations..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-9 bg-secondary pl-9 text-sm"
            />
          </div>
        </div>

        {/* Conversation List */}
        <ScrollArea className="flex-1">
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
                  onClick={() => setSelectedChat(chat.id)}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left transition-colors",
                    selectedChat === chat.id ? "bg-accent" : "hover:bg-secondary"
                  )}
                >
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                    <Bot className="h-4 w-4 text-primary" />
                  </div>
                  <div className="flex-1 overflow-hidden">
                    <div className="flex items-center justify-between">
                      <p className="truncate text-sm font-medium text-foreground">{chat.title}</p>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {formatTimestamp(chat.updated_at)}
                      </span>
                    </div>
                    <p className="truncate text-xs text-muted-foreground">
                      {chat.message_count} messages
                    </p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </ScrollArea>
      </div>

      {/* Chat Area */}
      <div
        className={cn(
          "flex flex-1 flex-col bg-background",
          !selectedChat && "hidden md:flex"
        )}
      >
        {selectedChat ? (
          <>
            {/* Chat Header */}
            <div className="flex h-14 items-center justify-between border-b border-border px-4">
              <div className="flex items-center gap-3">
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
                    {sessions.find((c) => c.id === selectedChat)?.title}
                  </p>
                  <p className="text-xs text-muted-foreground">AI Tutor</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setDocumentSelectorOpen(true)}
                  className="h-8"
                >
                  <Paperclip className="h-4 w-4 mr-1" />
                  {sessionDocuments.length > 0 
                    ? `${sessionDocuments.length} docs` 
                    : "Attach"}
                </Button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground">
                      <MoreVertical className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem 
                      className="text-destructive"
                      onClick={() => handleDeleteSession(selectedChat)}
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      Delete Chat
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>

            {/* Messages */}
            <ScrollArea className="flex-1 p-4">
              <div className="mx-auto max-w-3xl space-y-6">
                {messagesLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                  </div>
                ) : messages.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <Bot className="h-12 w-12 text-muted-foreground mb-4" />
                    <p className="text-sm text-muted-foreground">
                      No messages yet. Start the conversation!
                    </p>
                  </div>
                ) : (
                  messages.map((msg) => (
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
                      <div
                        className={cn(
                          "max-w-[80%] rounded-2xl px-4 py-3",
                          msg.role === "user"
                            ? "bg-primary text-primary-foreground"
                            : "bg-secondary text-secondary-foreground"
                        )}
                      >
                        <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
                        <span className="mt-1 block text-xs opacity-70">
                          {formatTimestamp(msg.created_at)}
                        </span>
                      </div>
                    </div>
                  ))
                )}
                <div ref={messagesEndRef} />
              </div>
            </ScrollArea>

            {/* Input */}
            <div className="border-t border-border p-4">
              <div className="mx-auto max-w-3xl">
                <div className="flex items-end gap-2">
                  <Textarea
                    ref={textareaRef}
                    placeholder="Ask me anything ..."
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault()
                        handleSendMessage()
                      }
                    }}
                    className="flex-1 bg-secondary min-h-[44px] max-h-[200px] resize-none"
                    disabled={askLoading}
                    rows={1}
                  />
                  <Button
                    size="icon"
                    onClick={handleSendMessage}
                    disabled={!message.trim() || askLoading}
                    className="shrink-0 h-[44px] w-[44px]"
                  >
                    {askLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="hidden md:flex flex-1 items-center justify-center">
            <div className="text-center">
              <Bot className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium text-foreground mb-2">
                No Chat Selected
              </h3>
              <p className="text-sm text-muted-foreground">
                Select a chat or create a new one to start
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Document Selector Dialog */}
      <ChatDocumentSelector
        open={documentSelectorOpen}
        onOpenChange={setDocumentSelectorOpen}
        selectedDocIds={sessionDocuments}
        onDocumentsChange={setSessionDocuments}
      />
    </div>
  )
}
