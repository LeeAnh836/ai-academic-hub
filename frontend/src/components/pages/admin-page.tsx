import { useState, useEffect, useCallback } from "react"
import {
  Users,
  FileText,
  Bot,
  HardDrive,
  Search,
  MoreVertical,
  Shield,
  Ban,
  Trash2,
  Activity,
  UserCheck,
  FolderOpen,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Globe,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useTranslation } from "@/lib/i18n"
import { adminService } from "@/services/admin.service"
import type {
  AdminStats,
  AdminUser,
  AdminGroup,
  AdminDocument,
  AdminActivityLog,
} from "@/types/api"

function getInitials(name: string | null | undefined): string {
  if (!name) return "?"
  return name
    .split(" ")
    .filter((n) => n.length > 0)
    .map((n) => n[0].toUpperCase())
    .slice(0, 2)
    .join("")
}

function useDebounce(value: string, delay: number) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const handler = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(handler)
  }, [value, delay])
  return debounced
}

export function AdminPage() {
  const { t } = useTranslation()

  // Stats
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [statsLoading, setStatsLoading] = useState(true)

  // Users
  const [users, setUsers] = useState<AdminUser[]>([])
  const [usersTotal, setUsersTotal] = useState(0)
  const [usersPage, setUsersPage] = useState(1)
  const [userSearch, setUserSearch] = useState("")
  const [usersLoading, setUsersLoading] = useState(false)
  const debouncedUserSearch = useDebounce(userSearch, 400)

  // Groups
  const [groups, setGroups] = useState<AdminGroup[]>([])
  const [groupsTotal, setGroupsTotal] = useState(0)
  const [groupsPage, setGroupsPage] = useState(1)
  const [groupSearch, setGroupSearch] = useState("")
  const [groupsLoading, setGroupsLoading] = useState(false)
  const debouncedGroupSearch = useDebounce(groupSearch, 400)

  // Documents
  const [documents, setDocuments] = useState<AdminDocument[]>([])
  const [docsTotal, setDocsTotal] = useState(0)
  const [docsPage, setDocsPage] = useState(1)
  const [fileSearch, setFileSearch] = useState("")
  const [docsLoading, setDocsLoading] = useState(false)
  const debouncedFileSearch = useDebounce(fileSearch, 400)

  // Activity Logs
  const [logs, setLogs] = useState<AdminActivityLog[]>([])
  const [logsTotal, setLogsTotal] = useState(0)
  const [logsPage, setLogsPage] = useState(1)
  const [logsLoading, setLogsLoading] = useState(false)

  // Active tab
  const [activeTab, setActiveTab] = useState("users")

  const PAGE_SIZE = 20

  // ---- Fetch functions ----
  const fetchStats = useCallback(async () => {
    setStatsLoading(true)
    try {
      const data = await adminService.getStats()
      setStats(data)
    } catch (e) {
      console.error("Failed to fetch admin stats", e)
    } finally {
      setStatsLoading(false)
    }
  }, [])

  const fetchUsers = useCallback(async () => {
    setUsersLoading(true)
    try {
      const data = await adminService.getUsers({
        search: debouncedUserSearch || undefined,
        page: usersPage,
        page_size: PAGE_SIZE,
      })
      setUsers(data.users)
      setUsersTotal(data.total)
    } catch (e) {
      console.error("Failed to fetch users", e)
    } finally {
      setUsersLoading(false)
    }
  }, [debouncedUserSearch, usersPage])

  const fetchGroups = useCallback(async () => {
    setGroupsLoading(true)
    try {
      const data = await adminService.getGroups({
        search: debouncedGroupSearch || undefined,
        page: groupsPage,
        page_size: PAGE_SIZE,
      })
      setGroups(data.groups)
      setGroupsTotal(data.total)
    } catch (e) {
      console.error("Failed to fetch groups", e)
    } finally {
      setGroupsLoading(false)
    }
  }, [debouncedGroupSearch, groupsPage])

  const fetchDocuments = useCallback(async () => {
    setDocsLoading(true)
    try {
      const data = await adminService.getDocuments({
        search: debouncedFileSearch || undefined,
        page: docsPage,
        page_size: PAGE_SIZE,
      })
      setDocuments(data.documents)
      setDocsTotal(data.total)
    } catch (e) {
      console.error("Failed to fetch documents", e)
    } finally {
      setDocsLoading(false)
    }
  }, [debouncedFileSearch, docsPage])

  const fetchLogs = useCallback(async () => {
    setLogsLoading(true)
    try {
      const data = await adminService.getActivityLogs({
        page: logsPage,
        page_size: 50,
      })
      setLogs(data.logs)
      setLogsTotal(data.total)
    } catch (e) {
      console.error("Failed to fetch logs", e)
    } finally {
      setLogsLoading(false)
    }
  }, [logsPage])

  // ---- Load on mount ----
  useEffect(() => { fetchStats() }, [fetchStats])
  useEffect(() => { fetchUsers() }, [fetchUsers])
  useEffect(() => { fetchGroups() }, [fetchGroups])
  useEffect(() => { fetchDocuments() }, [fetchDocuments])
  useEffect(() => { fetchLogs() }, [fetchLogs])

  // Reset page when search changes
  useEffect(() => { setUsersPage(1) }, [debouncedUserSearch])
  useEffect(() => { setGroupsPage(1) }, [debouncedGroupSearch])
  useEffect(() => { setDocsPage(1) }, [debouncedFileSearch])

  // ---- Action handlers ----
  const handleChangeRole = async (user: AdminUser) => {
    const newRole = user.role === "admin" ? "user" : "admin"
    try {
      await adminService.changeUserRole(user.id, newRole as "admin" | "user")
      fetchUsers()
      fetchStats()
    } catch (e) {
      console.error("Failed to change role", e)
    }
  }

  const handleBanUser = async (user: AdminUser) => {
    try {
      await adminService.banUser(user.id)
      fetchUsers()
    } catch (e) {
      console.error("Failed to ban user", e)
    }
  }

  const handleDeleteUser = async (user: AdminUser) => {
    if (!confirm(t("admin.confirmDeleteUser") || `Delete user ${user.full_name || user.username}?`)) return
    try {
      await adminService.deleteUser(user.id)
      fetchUsers()
      fetchStats()
    } catch (e) {
      console.error("Failed to delete user", e)
    }
  }

  const handleDeleteGroup = async (group: AdminGroup) => {
    if (!confirm(t("admin.confirmDeleteGroup") || `Delete group ${group.name}?`)) return
    try {
      await adminService.deleteGroup(group.id)
      fetchGroups()
      fetchStats()
    } catch (e) {
      console.error("Failed to delete group", e)
    }
  }

  const handleDeleteDocument = async (doc: AdminDocument) => {
    if (!confirm(t("admin.confirmDeleteFile") || `Delete file ${doc.name}?`)) return
    try {
      await adminService.deleteDocument(doc.id)
      fetchDocuments()
      fetchStats()
    } catch (e) {
      console.error("Failed to delete document", e)
    }
  }

  // ---- Pagination helpers ----
  const usersTotalPages = Math.ceil(usersTotal / PAGE_SIZE)
  const groupsTotalPages = Math.ceil(groupsTotal / PAGE_SIZE)
  const docsTotalPages = Math.ceil(docsTotal / PAGE_SIZE)
  const logsTotalPages = Math.ceil(logsTotal / 50)

  function PaginationControls({
    page,
    totalPages,
    total,
    onPrev,
    onNext,
  }: {
    page: number
    totalPages: number
    total: number
    onPrev: () => void
    onNext: () => void
  }) {
    if (totalPages <= 1) return null
    return (
      <div className="flex items-center justify-between px-4 py-3">
        <span className="text-xs text-muted-foreground">
          {total} {t("admin.totalItems") || "total"}
        </span>
        <div className="flex items-center gap-2">
          <Button size="icon" variant="outline" className="h-7 w-7" disabled={page <= 1} onClick={onPrev}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-xs text-muted-foreground">
            {page} / {totalPages}
          </span>
          <Button size="icon" variant="outline" className="h-7 w-7" disabled={page >= totalPages} onClick={onNext}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    )
  }

  // ---- Stats cards ----
  const adminStats = stats
    ? [
        { key: "totalUsers", label: t("admin.totalUsers"), value: stats.total_users.toLocaleString(), icon: Users },
        { key: "activeToday", label: t("admin.activeToday"), value: stats.active_today.toString(), icon: UserCheck, clickable: true },
        { key: "totalGroups", label: t("admin.totalGroups"), value: stats.total_groups.toString(), icon: FolderOpen },
        { key: "aiConversations", label: t("admin.aiConversations"), value: stats.total_ai_chats.toLocaleString(), icon: Bot },
        { key: "totalFiles", label: t("admin.totalFiles"), value: stats.total_files.toLocaleString(), icon: FileText },
        { key: "storageUsed", label: t("admin.storageUsed"), value: stats.storage_used, icon: HardDrive },
      ]
    : []

  const handleStatClick = (key: string) => {
    if (key === "activeToday") {
      setActiveTab("logs")
    }
  }

  return (
    <div className="space-y-6 p-4 md:p-6 lg:p-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">{t("admin.title")}</h1>
        <p className="text-sm text-muted-foreground">{t("admin.subtitle")}</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
        {statsLoading
          ? Array.from({ length: 6 }).map((_, i) => (
              <Card key={i}>
                <CardContent className="flex h-[110px] items-center justify-center p-4">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </CardContent>
              </Card>
            ))
          : adminStats.map((stat) => (
              <Card
                key={stat.key}
                className={cn(
                  stat.clickable && "cursor-pointer transition-shadow hover:shadow-md hover:ring-1 hover:ring-primary/30"
                )}
                onClick={() => stat.clickable && handleStatClick(stat.key)}
              >
                <CardContent className="p-4">
                  <div className="flex items-center gap-2">
                    <div className="rounded-lg bg-accent p-2">
                      <stat.icon className="h-4 w-4 text-accent-foreground" />
                    </div>
                  </div>
                  <div className="mt-3">
                    <p className="text-xl font-bold text-foreground">{stat.value}</p>
                    <p className="text-xs text-muted-foreground">{stat.label}</p>
                  </div>
                </CardContent>
              </Card>
            ))}
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="bg-secondary">
          <TabsTrigger value="users" className="gap-2 data-[state=active]:bg-card data-[state=active]:text-foreground">
            <Users className="h-4 w-4" /> {t("admin.users")}
          </TabsTrigger>
          <TabsTrigger value="groups" className="gap-2 data-[state=active]:bg-card data-[state=active]:text-foreground">
            <FolderOpen className="h-4 w-4" /> {t("admin.groups")}
          </TabsTrigger>
          <TabsTrigger value="files" className="gap-2 data-[state=active]:bg-card data-[state=active]:text-foreground">
            <FileText className="h-4 w-4" /> {t("admin.files")}
          </TabsTrigger>
          <TabsTrigger value="logs" className="gap-2 data-[state=active]:bg-card data-[state=active]:text-foreground">
            <Activity className="h-4 w-4" /> {t("admin.logs")}
          </TabsTrigger>
        </TabsList>

        {/* ==================== Users Tab ==================== */}
        <TabsContent value="users" className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder={t("admin.searchUsers")}
                value={userSearch}
                onChange={(e) => setUserSearch(e.target.value)}
                className="h-9 bg-card pl-9 text-sm"
              />
            </div>
          </div>
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    <th className="px-4 py-3 text-left">{t("admin.user")}</th>
                    <th className="hidden px-4 py-3 text-left sm:table-cell">{t("admin.studentId")}</th>
                    <th className="hidden px-4 py-3 text-left md:table-cell">{t("admin.email")}</th>
                    <th className="px-4 py-3 text-left">{t("admin.role")}</th>
                    <th className="px-4 py-3 text-left">{t("admin.status")}</th>
                    <th className="px-4 py-3 text-right">{t("admin.actions")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {usersLoading ? (
                    <tr>
                      <td colSpan={6} className="py-12 text-center">
                        <Loader2 className="mx-auto h-6 w-6 animate-spin text-muted-foreground" />
                      </td>
                    </tr>
                  ) : users.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-12 text-center text-sm text-muted-foreground">
                        {t("admin.noUsers") || "No users found"}
                      </td>
                    </tr>
                  ) : (
                    users.map((user) => (
                      <tr key={user.id} className="transition-colors hover:bg-secondary">
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            <Avatar className="h-8 w-8">
                              <AvatarFallback className="bg-accent text-accent-foreground text-xs">
                                {getInitials(user.full_name || user.username)}
                              </AvatarFallback>
                            </Avatar>
                            <div>
                              <span className="text-sm font-medium text-foreground">
                                {user.full_name || user.username}
                              </span>
                              {!user.is_active && (
                                <Badge variant="destructive" className="ml-2 text-[10px]">Banned</Badge>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="hidden px-4 py-3 text-sm text-muted-foreground sm:table-cell">
                          {user.student_id || "N/A"}
                        </td>
                        <td className="hidden px-4 py-3 text-sm text-muted-foreground md:table-cell">
                          {user.email}
                        </td>
                        <td className="px-4 py-3">
                          <Badge
                            variant={user.role === "admin" ? "default" : "secondary"}
                            className={cn(
                              "text-xs",
                              user.role === "admin" && "bg-primary text-primary-foreground"
                            )}
                          >
                            {user.role === "admin" ? "Admin" : "Student"}
                          </Badge>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1.5">
                            <span
                              className={cn(
                                "h-2 w-2 rounded-full",
                                user.online ? "bg-emerald-500" : "bg-muted-foreground"
                              )}
                            />
                            <span className="text-xs text-muted-foreground">
                              {user.online ? t("common.online") : (user.last_seen || "Offline")}
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button size="icon" variant="ghost" className="h-7 w-7 text-muted-foreground">
                                <MoreVertical className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onClick={() => handleChangeRole(user)}>
                                <Shield className="mr-2 h-4 w-4" />
                                {user.role === "admin" ? t("admin.demoteUser") || "Make Student" : t("admin.changeRole")}
                              </DropdownMenuItem>
                              <DropdownMenuItem onClick={() => handleBanUser(user)}>
                                <Ban className="mr-2 h-4 w-4" />
                                {user.is_active ? t("admin.banUser") : t("admin.unbanUser") || "Unban"}
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem className="text-destructive" onClick={() => handleDeleteUser(user)}>
                                <Trash2 className="mr-2 h-4 w-4" /> {t("admin.deleteUser")}
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <PaginationControls
              page={usersPage}
              totalPages={usersTotalPages}
              total={usersTotal}
              onPrev={() => setUsersPage((p) => Math.max(1, p - 1))}
              onNext={() => setUsersPage((p) => Math.min(usersTotalPages, p + 1))}
            />
          </Card>
        </TabsContent>

        {/* ==================== Groups Tab ==================== */}
        <TabsContent value="groups" className="space-y-4">
          <div className="relative max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder={t("admin.searchGroups")}
              value={groupSearch}
              onChange={(e) => setGroupSearch(e.target.value)}
              className="h-9 bg-card pl-9 text-sm"
            />
          </div>
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    <th className="px-4 py-3 text-left">{t("admin.group")}</th>
                    <th className="hidden px-4 py-3 text-left sm:table-cell">{t("common.members")}</th>
                    <th className="hidden px-4 py-3 text-left md:table-cell">{t("admin.files")}</th>
                    <th className="px-4 py-3 text-left">{t("admin.lastActive")}</th>
                    <th className="px-4 py-3 text-right">{t("admin.actions")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {groupsLoading ? (
                    <tr>
                      <td colSpan={5} className="py-12 text-center">
                        <Loader2 className="mx-auto h-6 w-6 animate-spin text-muted-foreground" />
                      </td>
                    </tr>
                  ) : groups.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-12 text-center text-sm text-muted-foreground">
                        {t("admin.noGroups") || "No groups found"}
                      </td>
                    </tr>
                  ) : (
                    groups.map((group) => (
                      <tr key={group.id} className="transition-colors hover:bg-secondary">
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            <Avatar className="h-8 w-8">
                              <AvatarFallback className="bg-accent text-accent-foreground text-xs">
                                {getInitials(group.name)}
                              </AvatarFallback>
                            </Avatar>
                            <div>
                              <span className="text-sm font-medium text-foreground">{group.name}</span>
                              {group.description && (
                                <p className="text-xs text-muted-foreground">{group.description}</p>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="hidden px-4 py-3 text-sm text-muted-foreground sm:table-cell">
                          {group.members}
                        </td>
                        <td className="hidden px-4 py-3 text-sm text-muted-foreground md:table-cell">
                          {group.files}
                        </td>
                        <td className="px-4 py-3 text-sm text-muted-foreground">{group.last_active}</td>
                        <td className="px-4 py-3 text-right">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button size="icon" variant="ghost" className="h-7 w-7 text-muted-foreground">
                                <MoreVertical className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem className="text-destructive" onClick={() => handleDeleteGroup(group)}>
                                <Trash2 className="mr-2 h-4 w-4" /> {t("admin.deleteGroup")}
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <PaginationControls
              page={groupsPage}
              totalPages={groupsTotalPages}
              total={groupsTotal}
              onPrev={() => setGroupsPage((p) => Math.max(1, p - 1))}
              onNext={() => setGroupsPage((p) => Math.min(groupsTotalPages, p + 1))}
            />
          </Card>
        </TabsContent>

        {/* ==================== Files Tab ==================== */}
        <TabsContent value="files" className="space-y-4">
          <div className="relative max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder={t("admin.searchFiles")}
              value={fileSearch}
              onChange={(e) => setFileSearch(e.target.value)}
              className="h-9 bg-card pl-9 text-sm"
            />
          </div>
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    <th className="px-4 py-3 text-left">{t("admin.files")}</th>
                    <th className="hidden px-4 py-3 text-left sm:table-cell">{t("admin.owner")}</th>
                    <th className="hidden px-4 py-3 text-left md:table-cell">{t("docs.size")}</th>
                    <th className="px-4 py-3 text-left">{t("docs.modified")}</th>
                    <th className="px-4 py-3 text-right">{t("admin.actions")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {docsLoading ? (
                    <tr>
                      <td colSpan={5} className="py-12 text-center">
                        <Loader2 className="mx-auto h-6 w-6 animate-spin text-muted-foreground" />
                      </td>
                    </tr>
                  ) : documents.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-12 text-center text-sm text-muted-foreground">
                        {t("admin.noFiles") || "No files found"}
                      </td>
                    </tr>
                  ) : (
                    documents.map((doc) => (
                      <tr key={doc.id} className="transition-colors hover:bg-secondary">
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            <FileText className="h-4 w-4 text-muted-foreground" />
                            <span className="text-sm font-medium text-foreground">{doc.name}</span>
                            {doc.shared && (
                              <Badge variant="secondary" className="text-xs">{t("common.shared")}</Badge>
                            )}
                          </div>
                        </td>
                        <td className="hidden px-4 py-3 text-sm text-muted-foreground sm:table-cell">
                          {doc.owner}
                        </td>
                        <td className="hidden px-4 py-3 text-sm text-muted-foreground md:table-cell">
                          {doc.size}
                        </td>
                        <td className="px-4 py-3 text-sm text-muted-foreground">
                          {new Date(doc.updated_at).toLocaleDateString()}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button size="icon" variant="ghost" className="h-7 w-7 text-muted-foreground">
                                <MoreVertical className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem className="text-destructive" onClick={() => handleDeleteDocument(doc)}>
                                <Trash2 className="mr-2 h-4 w-4" /> {t("common.delete")}
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <PaginationControls
              page={docsPage}
              totalPages={docsTotalPages}
              total={docsTotal}
              onPrev={() => setDocsPage((p) => Math.max(1, p - 1))}
              onNext={() => setDocsPage((p) => Math.min(docsTotalPages, p + 1))}
            />
          </Card>
        </TabsContent>

        {/* ==================== Activity Logs Tab ==================== */}
        <TabsContent value="logs" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base text-foreground">{t("admin.recentActivity")} &mdash; {new Date().toLocaleDateString()}</CardTitle>
            </CardHeader>
            <CardContent>
              {logsLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : logs.length === 0 ? (
                <p className="py-12 text-center text-sm text-muted-foreground">
                  {t("admin.noLogs") || "No activity logs"}
                </p>
              ) : (
                <ScrollArea className="h-[400px]">
                  <div className="space-y-4">
                    {logs.map((log) => (
                      <div key={log.id} className="flex items-start gap-3">
                        <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent">
                          {log.action.includes("failed") ? (
                            <Ban className="h-4 w-4 text-destructive" />
                          ) : (
                            <Activity className="h-4 w-4 text-accent-foreground" />
                          )}
                        </div>
                        <div className="flex-1">
                          <p className="text-sm text-foreground">
                            <span className="font-medium">{log.user}</span>{" "}
                            <span className="text-muted-foreground">{log.action}</span>
                            {log.target && (
                              <>
                                {" "}
                                <span className="font-medium">{log.target}</span>
                              </>
                            )}
                          </p>
                          <div className="flex items-center gap-2">
                            <p className="text-xs text-muted-foreground">{log.timestamp}</p>
                            {log.ip_address && (
                              <p className="flex items-center gap-1 text-xs text-muted-foreground">
                                <Globe className="h-3 w-3" /> {log.ip_address}
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              )}
            </CardContent>
            <PaginationControls
              page={logsPage}
              totalPages={logsTotalPages}
              total={logsTotal}
              onPrev={() => setLogsPage((p) => Math.max(1, p - 1))}
              onNext={() => setLogsPage((p) => Math.min(logsTotalPages, p + 1))}
            />
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
