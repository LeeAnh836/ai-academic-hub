import {
  FileText,
  Bot,
  Users,
  Clock,
  Plus,
  Upload,
  UserPlus,
  ArrowUpRight,
  MessageCircle,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { useApp } from "@/lib/app-context"
import { mockAIConversations, mockDocuments, mockGroups } from "@/lib/mock-data"

const stats = [
  { label: "Documents", value: "24", icon: FileText, change: "+3 this week" },
  { label: "AI Chats", value: "18", icon: Bot, change: "+5 this week" },
  { label: "Study Groups", value: "5", icon: Users, change: "+1 this week" },
  { label: "Study Time", value: "32h", icon: Clock, change: "+4h this week" },
]

export function DashboardPage() {
  const { setCurrentPage, user } = useApp()

  return (
    <div className="space-y-6 p-4 md:p-6 lg:p-8">
      {/* Welcome */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">
          Welcome back, {user.name.split(" ")[0]}
        </h1>
        <p className="text-sm text-muted-foreground">
          Here is what is happening with your studies today.
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.label}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div className="rounded-lg bg-accent p-2">
                  <stat.icon className="h-5 w-5 text-accent-foreground" />
                </div>
              </div>
              <div className="mt-3">
                <p className="text-2xl font-bold text-foreground">{stat.value}</p>
                <p className="text-sm text-muted-foreground">{stat.label}</p>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{stat.change}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="flex flex-wrap gap-3">
        <Button onClick={() => setCurrentPage("ai-chat")} className="gap-2 bg-primary text-primary-foreground hover:bg-primary/90">
          <Plus className="h-4 w-4" />
          New AI Chat
        </Button>
        <Button variant="outline" onClick={() => setCurrentPage("documents")} className="gap-2">
          <Upload className="h-4 w-4" />
          Upload File
        </Button>
        <Button variant="outline" onClick={() => setCurrentPage("groups")} className="gap-2">
          <UserPlus className="h-4 w-4" />
          Create Group
        </Button>
      </div>

      {/* Recent Content Grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Recent AI Chats */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-base font-semibold text-foreground">Recent AI Chats</CardTitle>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setCurrentPage("ai-chat")}
              className="gap-1 text-xs text-muted-foreground"
            >
              View all <ArrowUpRight className="h-3 w-3" />
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            {mockAIConversations.slice(0, 4).map((chat) => (
              <button
                key={chat.id}
                onClick={() => setCurrentPage("ai-chat")}
                className="flex w-full items-center gap-3 rounded-lg p-2 text-left transition-colors hover:bg-secondary"
              >
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent">
                  <Bot className="h-4 w-4 text-accent-foreground" />
                </div>
                <div className="flex-1 overflow-hidden">
                  <p className="truncate text-sm font-medium text-foreground">{chat.title}</p>
                  <p className="truncate text-xs text-muted-foreground">{chat.lastMessage}</p>
                </div>
                <span className="shrink-0 text-xs text-muted-foreground">{chat.updatedAt}</span>
              </button>
            ))}
          </CardContent>
        </Card>

        {/* Recent Documents */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-base font-semibold text-foreground">Recent Documents</CardTitle>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setCurrentPage("documents")}
              className="gap-1 text-xs text-muted-foreground"
            >
              View all <ArrowUpRight className="h-3 w-3" />
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            {mockDocuments.slice(0, 4).map((doc) => (
              <div
                key={doc.id}
                className="flex items-center gap-3 rounded-lg p-2 transition-colors hover:bg-secondary"
              >
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent">
                  <FileText className="h-4 w-4 text-accent-foreground" />
                </div>
                <div className="flex-1 overflow-hidden">
                  <p className="truncate text-sm font-medium text-foreground">{doc.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {doc.size} &middot; {doc.updatedAt}
                  </p>
                </div>
                {doc.shared && (
                  <Badge variant="secondary" className="shrink-0 text-xs">
                    Shared
                  </Badge>
                )}
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Active Groups */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-base font-semibold text-foreground">Active Groups</CardTitle>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setCurrentPage("groups")}
              className="gap-1 text-xs text-muted-foreground"
            >
              View all <ArrowUpRight className="h-3 w-3" />
            </Button>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {mockGroups.slice(0, 3).map((group) => (
                <div
                  key={group.id}
                  className="flex items-center gap-3 rounded-lg border border-border p-3 transition-colors hover:bg-secondary"
                >
                  <Avatar className="h-10 w-10 shrink-0">
                    <AvatarFallback className="bg-accent text-accent-foreground text-sm">
                      {group.name.split(" ").map(n => n[0]).slice(0, 2).join("")}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex-1 overflow-hidden">
                    <p className="truncate text-sm font-medium text-foreground">{group.name}</p>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Users className="h-3 w-3" /> {group.members}
                      </span>
                      <span className="flex items-center gap-1">
                        <MessageCircle className="h-3 w-3" /> {group.lastActive}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
