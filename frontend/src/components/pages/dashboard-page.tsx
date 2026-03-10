import {
  FileText,
  Bot,
  Users,
  Clock,
  Plus,
  Upload,
  UserPlus,
  ArrowUpRight,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { useApp } from "@/lib/app-context"
import { useNavigate } from "react-router-dom"
import { getUserDisplayName } from "@/utils/user.utils"
import { formatRelativeTime } from "@/utils/format.utils"
import { useChatSessions } from "@/hooks/use-chat"
import { useDocuments } from "@/hooks/use-documents"
import { useGroups } from "@/hooks/use-groups"
import { useTranslation } from "@/lib/i18n"

export function DashboardPage() {
  const { user } = useApp()
  const navigate = useNavigate()
  const { sessions, loading: sessionsLoading } = useChatSessions(true)
  const { documents, loading: documentsLoading } = useDocuments(true)
  const { groups, loading: groupsLoading } = useGroups(true)
  const { t } = useTranslation()
  
  if (!user) return null
  
  const stats = [
    { label: t("dashboard.documents"), value: documents.length.toString(), icon: FileText, change: t("dashboard.thisWeek", { n: 3 }) },
    { label: t("dashboard.aiChats"), value: sessions.length.toString(), icon: Bot, change: t("dashboard.thisWeek", { n: 5 }) },
    { label: t("dashboard.studyGroups"), value: groups.length.toString(), icon: Users, change: t("dashboard.thisWeek", { n: 1 }) },
    { label: t("dashboard.studyTime"), value: "32h", icon: Clock, change: t("dashboard.thisWeek", { n: 4 }) },
  ]

  return (
    <div className="space-y-6 p-4 md:p-6 lg:p-8">
      {/* Welcome */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">
          {t("dashboard.welcomeBack", { name: getUserDisplayName(user, t).split(" ")[0] })}
        </h1>
        <p className="text-sm text-muted-foreground">
          {t("dashboard.subtitle")}
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
        <Button onClick={() => navigate("/ai-chat")} className="gap-2 bg-primary text-primary-foreground hover:bg-primary/90">
          <Plus className="h-4 w-4" />
          {t("dashboard.newAiChat")}
        </Button>
        <Button variant="outline" onClick={() => navigate("/documents")} className="gap-2">
          <Upload className="h-4 w-4" />
          {t("dashboard.uploadFile")}
        </Button>
        <Button variant="outline" onClick={() => navigate("/groups")} className="gap-2">
          <UserPlus className="h-4 w-4" />
          {t("dashboard.createGroup")}
        </Button>
      </div>

      {/* Recent Content Grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Recent AI Chats */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-base font-semibold text-foreground">{t("dashboard.recentAiChats")}</CardTitle>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/ai-chat")}
              className="gap-1 text-xs text-muted-foreground"
            >
              {t("dashboard.viewAll")} <ArrowUpRight className="h-3 w-3" />
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            {sessionsLoading ? (
              <p className="text-sm text-muted-foreground text-center py-4">{t("common.loading")}</p>
            ) : sessions.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">{t("dashboard.noChats")}</p>
            ) : (
              sessions.slice(0, 4).map((chat) => (
                <button
                  key={chat.id}
                  onClick={() => navigate("/ai-chat")}
                  className="flex w-full items-center gap-3 rounded-lg p-2 text-left transition-colors hover:bg-secondary"
                >
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent">
                    <Bot className="h-4 w-4 text-accent-foreground" />
                  </div>
                  <div className="flex-1 overflow-hidden">
                    <p className="truncate text-sm font-medium text-foreground">{chat.title}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {chat.message_count} {t("common.messages")} • {formatRelativeTime(chat.updated_at, t)}
                    </p>
                  </div>
                  <Badge variant="secondary" className="shrink-0 text-[10px]">
                    {chat.model_name}
                  </Badge>
                </button>
              ))
            )}
          </CardContent>
        </Card>

        {/* Recent Documents */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-base font-semibold text-foreground">{t("dashboard.recentDocuments")}</CardTitle>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/documents")}
              className="gap-1 text-xs text-muted-foreground"
            >
              {t("dashboard.viewAll")} <ArrowUpRight className="h-3 w-3" />
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            {documentsLoading ? (
              <p className="text-sm text-muted-foreground text-center py-4">{t("common.loading")}</p>
            ) : documents.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">{t("dashboard.noDocs")}</p>
            ) : (
              documents.slice(0, 4).map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center gap-3 rounded-lg p-2 transition-colors hover:bg-secondary"
                >
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent">
                    <FileText className="h-4 w-4 text-accent-foreground" />
                  </div>
                  <div className="flex-1 overflow-hidden">
                    <p className="truncate text-sm font-medium text-foreground">{doc.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {doc.file_type} • {formatRelativeTime(doc.updated_at, t)}
                    </p>
                  </div>
                  <Badge variant="secondary" className="shrink-0 text-xs">
                    {doc.category}
                  </Badge>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Active Groups */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-base font-semibold text-foreground">{t("dashboard.activeGroups")}</CardTitle>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/groups")}
              className="gap-1 text-xs text-muted-foreground"
            >
              {t("dashboard.viewAll")} <ArrowUpRight className="h-3 w-3" />
            </Button>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {groupsLoading ? (
                <p className="text-sm text-muted-foreground text-center py-4 col-span-full">{t("common.loading")}</p>
              ) : groups.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4 col-span-full">{t("dashboard.noGroups")}</p>
              ) : (
                groups.slice(0, 3).map((group) => (
                  <div
                    key={group.id}
                    className="flex items-center gap-3 rounded-lg border border-border p-3 transition-colors hover:bg-secondary"
                  >
                    <Avatar className="h-10 w-10 shrink-0">
                      <AvatarFallback className="bg-accent text-accent-foreground text-sm">
                        {group.group_name.split(" ").map(n => n[0]).slice(0, 2).join("")}
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex-1 overflow-hidden">
                      <p className="truncate text-sm font-medium text-foreground">{group.group_name}</p>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Users className="h-3 w-3" /> {group.member_count}
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" /> {formatRelativeTime(group.updated_at)}
                        </span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
