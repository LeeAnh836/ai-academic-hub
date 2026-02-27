import { useState, useEffect, useRef } from "react"
import {
  Send,
  Search,
  Paperclip,
  ImageIcon,
  Phone,
  Video,
  Users,
  Plus,
  ArrowLeft,
  Info,
  FileText,
  X,
  UserPlus,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { mockConversations, mockChatMessages, mockUsers } from "@/lib/mock-data"

export function MessagesPage() {
  const [selectedConvo, setSelectedConvo] = useState<string | null>("c1")
  const [message, setMessage] = useState("")
  const [searchQuery, setSearchQuery] = useState("")
  const [showInfoPanel, setShowInfoPanel] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px'
    }
  }, [message])

  const filteredConversations = mockConversations.filter((c) =>
    c.name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const activeConvo = mockConversations.find((c) => c.id === selectedConvo)

  return (
    <div className="flex h-[calc(100vh-56px)] md:h-screen">
      {/* Conversation List */}
      <div
        className={cn(
          "flex w-full flex-col border-r border-border bg-card md:w-[300px] lg:w-[320px]",
          selectedConvo && "hidden md:flex"
        )}
      >
        {/* Header */}
        <div className="flex h-14 items-center justify-between border-b border-border px-4">
          <h2 className="font-semibold text-foreground">Messages</h2>
          <div className="flex items-center gap-1">
            <Dialog>
              <DialogTrigger asChild>
                <Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground">
                  <UserPlus className="h-4 w-4" />
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>New Conversation</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 pt-2">
                  <Input placeholder="Search by student ID or name..." className="bg-secondary" />
                  <div className="space-y-2">
                    {mockUsers.slice(1, 5).map((user) => (
                      <button
                        key={user.id}
                        className="flex w-full items-center gap-3 rounded-lg p-2 text-left transition-colors hover:bg-secondary"
                      >
                        <div className="relative">
                          <Avatar className="h-9 w-9">
                            <AvatarFallback className="bg-accent text-accent-foreground text-xs">
                              {user.name.split(" ").map(n => n[0]).join("")}
                            </AvatarFallback>
                          </Avatar>
                          {user.online && (
                            <span className="absolute bottom-0 right-0 h-3 w-3 rounded-full border-2 border-card bg-emerald-500" />
                          )}
                        </div>
                        <div className="flex-1">
                          <p className="text-sm font-medium text-foreground">{user.name}</p>
                          <p className="text-xs text-muted-foreground">{user.studentId}</p>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              </DialogContent>
            </Dialog>
            <Dialog>
              <DialogTrigger asChild>
                <Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground">
                  <Plus className="h-4 w-4" />
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create Group Chat</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 pt-2">
                  <Input placeholder="Group name" className="bg-secondary" />
                  <div>
                    <p className="mb-2 text-sm font-medium text-foreground">Add Members</p>
                    <Input placeholder="Search students..." className="mb-2 bg-secondary" />
                    <div className="space-y-2">
                      {mockUsers.slice(1, 6).map((user) => (
                        <label
                          key={user.id}
                          className="flex items-center gap-3 rounded-lg p-2 cursor-pointer hover:bg-secondary"
                        >
                          <input type="checkbox" className="rounded border-border" />
                          <Avatar className="h-8 w-8">
                            <AvatarFallback className="bg-accent text-accent-foreground text-xs">
                              {user.name.split(" ").map(n => n[0]).join("")}
                            </AvatarFallback>
                          </Avatar>
                          <span className="text-sm text-foreground">{user.name}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                  <Button className="w-full bg-primary text-primary-foreground hover:bg-primary/90">Create Group</Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
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
          <div className="space-y-1 p-2">
            {filteredConversations.map((convo) => (
              <button
                key={convo.id}
                onClick={() => setSelectedConvo(convo.id)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left transition-colors",
                  selectedConvo === convo.id ? "bg-accent" : "hover:bg-secondary"
                )}
              >
                <div className="relative">
                  <Avatar className="h-10 w-10">
                    <AvatarFallback className="bg-secondary text-secondary-foreground text-xs">
                      {convo.type === "group" ? (
                        <Users className="h-4 w-4" />
                      ) : (
                        convo.name.split(" ").map(n => n[0]).join("")
                      )}
                    </AvatarFallback>
                  </Avatar>
                  {convo.online && convo.type === "direct" && (
                    <span className="absolute bottom-0 right-0 h-3 w-3 rounded-full border-2 border-card bg-emerald-500" />
                  )}
                </div>
                <div className="flex-1 overflow-hidden">
                  <div className="flex items-center justify-between">
                    <p className="truncate text-sm font-medium text-foreground">{convo.name}</p>
                    <span className="shrink-0 text-xs text-muted-foreground">{convo.updatedAt}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <p className="truncate text-xs text-muted-foreground">{convo.lastMessage}</p>
                    {convo.unread > 0 && (
                      <Badge variant="destructive" className="ml-2 h-5 min-w-5 shrink-0 px-1.5 text-xs">
                        {convo.unread}
                      </Badge>
                    )}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </ScrollArea>
      </div>

      {/* Chat Area */}
      <div
        className={cn(
          "flex flex-1 flex-col bg-background",
          !selectedConvo && "hidden md:flex"
        )}
      >
        {selectedConvo && activeConvo ? (
          <>
            {/* Chat Header */}
            <div className="flex h-14 items-center justify-between border-b border-border px-4">
              <div className="flex items-center gap-3">
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-8 w-8 md:hidden"
                  onClick={() => setSelectedConvo(null)}
                >
                  <ArrowLeft className="h-4 w-4" />
                </Button>
                <div className="relative">
                  <Avatar className="h-8 w-8">
                    <AvatarFallback className="bg-secondary text-secondary-foreground text-xs">
                      {activeConvo.type === "group" ? (
                        <Users className="h-3.5 w-3.5" />
                      ) : (
                        activeConvo.name.split(" ").map(n => n[0]).join("")
                      )}
                    </AvatarFallback>
                  </Avatar>
                  {activeConvo.online && activeConvo.type === "direct" && (
                    <span className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full border-2 border-background bg-emerald-500" />
                  )}
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">{activeConvo.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {activeConvo.type === "direct"
                      ? activeConvo.online ? "Online" : "Offline"
                      : `${activeConvo.members.length} members`}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground">
                  <Phone className="h-4 w-4" />
                </Button>
                <Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground">
                  <Video className="h-4 w-4" />
                </Button>
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
                  <div className="space-y-4">
                    {mockChatMessages.map((msg) => {
                      const isMe = msg.senderId === "u1"
                      return (
                        <div
                          key={msg.id}
                          className={cn("flex gap-3", isMe ? "justify-end" : "justify-start")}
                        >
                          {!isMe && (
                            <Avatar className="h-8 w-8 shrink-0">
                              <AvatarFallback className="bg-accent text-accent-foreground text-xs">SK</AvatarFallback>
                            </Avatar>
                          )}
                          <div
                            className={cn(
                              "max-w-[70%] rounded-2xl px-4 py-2.5",
                              isMe
                                ? "bg-primary text-primary-foreground"
                                : "bg-card text-card-foreground border border-border"
                            )}
                          >
                            {msg.type === "file" ? (
                              <div className="flex items-center gap-2">
                                <FileText className={cn("h-4 w-4", isMe ? "text-primary-foreground/70" : "text-muted-foreground")} />
                                <span className="text-sm underline">{msg.content}</span>
                              </div>
                            ) : (
                              <p className="text-sm leading-relaxed">{msg.content}</p>
                            )}
                            <p
                              className={cn(
                                "mt-1 text-xs",
                                isMe ? "text-primary-foreground/70" : "text-muted-foreground"
                              )}
                            >
                              {msg.timestamp}
                            </p>
                          </div>
                          {isMe && (
                            <Avatar className="h-8 w-8 shrink-0">
                              <AvatarFallback className="bg-secondary text-secondary-foreground text-xs">AC</AvatarFallback>
                            </Avatar>
                          )}
                        </div>
                      )
                    })}
                    {/* Typing indicator */}
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span className="flex gap-1">
                        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:0ms]" />
                        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:150ms]" />
                        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:300ms]" />
                      </span>
                      Sarah is typing...
                    </div>
                  </div>
                </ScrollArea>

                {/* Input */}
                <div className="border-t border-border p-4">
                  <div className="flex items-end gap-2">
                    <Button size="icon" variant="ghost" className="h-9 w-9 shrink-0 text-muted-foreground">
                      <Paperclip className="h-4 w-4" />
                    </Button>
                    <Button size="icon" variant="ghost" className="h-9 w-9 shrink-0 text-muted-foreground">
                      <ImageIcon className="h-4 w-4" />
                    </Button>
                    <Textarea
                      ref={textareaRef}
                      placeholder="Type a message ..."
                      value={message}
                      onChange={(e) => setMessage(e.target.value)}
                      className="flex-1 bg-card min-h-[36px] max-h-[200px] resize-none"
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault()
                          setMessage("")
                          if (textareaRef.current) {
                            textareaRef.current.style.height = 'auto'
                          }
                        }
                      }}
                      rows={1}
                    />
                    <Button size="icon" className="h-9 w-9 shrink-0 bg-primary text-primary-foreground hover:bg-primary/90">
                      <Send className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>

              {/* Info Panel */}
              {showInfoPanel && (
                <div className="hidden w-[260px] flex-col border-l border-border bg-card lg:flex">
                  <div className="flex h-14 items-center justify-between border-b border-border px-4">
                    <span className="text-sm font-medium text-foreground">Details</span>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7 text-muted-foreground"
                      onClick={() => setShowInfoPanel(false)}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                  <ScrollArea className="flex-1 p-4">
                    <div className="space-y-6">
                      {/* Avatar + Name */}
                      <div className="flex flex-col items-center text-center">
                        <Avatar className="h-16 w-16">
                          <AvatarFallback className="bg-accent text-accent-foreground text-lg">
                            {activeConvo.type === "group" ? (
                              <Users className="h-6 w-6" />
                            ) : (
                              activeConvo.name.split(" ").map(n => n[0]).join("")
                            )}
                          </AvatarFallback>
                        </Avatar>
                        <p className="mt-2 font-medium text-foreground">{activeConvo.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {activeConvo.type === "group" ? "Group Chat" : "Direct Message"}
                        </p>
                      </div>

                      {/* Members */}
                      {activeConvo.type === "group" && (
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Members</p>
                            <Button size="icon" variant="ghost" className="h-6 w-6 text-muted-foreground">
                              <UserPlus className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                          <div className="space-y-2">
                            {mockUsers.slice(0, 4).map((user) => (
                              <div key={user.id} className="flex items-center gap-2">
                                <div className="relative">
                                  <Avatar className="h-7 w-7">
                                    <AvatarFallback className="bg-secondary text-secondary-foreground text-[10px]">
                                      {user.name.split(" ").map(n => n[0]).join("")}
                                    </AvatarFallback>
                                  </Avatar>
                                  {user.online && (
                                    <span className="absolute bottom-0 right-0 h-2 w-2 rounded-full border border-card bg-emerald-500" />
                                  )}
                                </div>
                                <span className="text-xs text-foreground">{user.name}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Shared Files */}
                      <div>
                        <p className="mb-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                          Shared Files
                        </p>
                        <div className="space-y-2">
                          <div className="flex items-center gap-2 rounded-lg bg-secondary p-2">
                            <FileText className="h-4 w-4 text-muted-foreground" />
                            <div className="flex-1 overflow-hidden">
                              <p className="truncate text-xs text-foreground">CS301_Lecture_Notes.pdf</p>
                              <p className="text-[10px] text-muted-foreground">2.4 MB</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2 rounded-lg bg-secondary p-2">
                            <FileText className="h-4 w-4 text-muted-foreground" />
                            <div className="flex-1 overflow-hidden">
                              <p className="truncate text-xs text-foreground">Homework_3.docx</p>
                              <p className="text-[10px] text-muted-foreground">156 KB</p>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
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
              <h3 className="text-lg font-semibold text-foreground">Your Messages</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Select a conversation to start chatting
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
