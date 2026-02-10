import { useState } from "react"
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
import {
  mockAdminStats,
  mockUsers,
  mockGroups,
  mockDocuments,
  mockActivityLogs,
} from "@/lib/mock-data"

const adminStats = [
  { label: "Total Users", value: mockAdminStats.totalUsers.toLocaleString(), icon: Users, change: "+24 this week" },
  { label: "Active Today", value: mockAdminStats.activeToday.toString(), icon: UserCheck, change: "27% of users" },
  { label: "Total Groups", value: mockAdminStats.totalGroups.toString(), icon: FolderOpen, change: "+3 this week" },
  { label: "AI Conversations", value: mockAdminStats.totalAIChats.toLocaleString(), icon: Bot, change: "+890 this week" },
  { label: "Total Files", value: mockAdminStats.totalFiles.toLocaleString(), icon: FileText, change: "+156 this week" },
  { label: "Storage Used", value: mockAdminStats.storageUsed, icon: HardDrive, change: "of 500 GB" },
]

export function AdminPage() {
  const [userSearch, setUserSearch] = useState("")
  const [groupSearch, setGroupSearch] = useState("")
  const [fileSearch, setFileSearch] = useState("")

  const filteredUsers = mockUsers.filter(
    (u) =>
      u.name.toLowerCase().includes(userSearch.toLowerCase()) ||
      u.email.toLowerCase().includes(userSearch.toLowerCase()) ||
      u.studentId.toLowerCase().includes(userSearch.toLowerCase())
  )

  return (
    <div className="space-y-6 p-4 md:p-6 lg:p-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">Admin Panel</h1>
        <p className="text-sm text-muted-foreground">System management and monitoring</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
        {adminStats.map((stat) => (
          <Card key={stat.label}>
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
              <p className="mt-1 text-[11px] text-muted-foreground">{stat.change}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Tabs */}
      <Tabs defaultValue="users" className="space-y-4">
        <TabsList className="bg-secondary">
          <TabsTrigger value="users" className="gap-2 data-[state=active]:bg-card data-[state=active]:text-foreground">
            <Users className="h-4 w-4" /> Users
          </TabsTrigger>
          <TabsTrigger value="groups" className="gap-2 data-[state=active]:bg-card data-[state=active]:text-foreground">
            <FolderOpen className="h-4 w-4" /> Groups
          </TabsTrigger>
          <TabsTrigger value="files" className="gap-2 data-[state=active]:bg-card data-[state=active]:text-foreground">
            <FileText className="h-4 w-4" /> Files
          </TabsTrigger>
          <TabsTrigger value="logs" className="gap-2 data-[state=active]:bg-card data-[state=active]:text-foreground">
            <Activity className="h-4 w-4" /> Logs
          </TabsTrigger>
        </TabsList>

        {/* Users Tab */}
        <TabsContent value="users" className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search users by name, email, or ID..."
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
                    <th className="px-4 py-3 text-left">User</th>
                    <th className="hidden px-4 py-3 text-left sm:table-cell">Student ID</th>
                    <th className="hidden px-4 py-3 text-left md:table-cell">Email</th>
                    <th className="px-4 py-3 text-left">Role</th>
                    <th className="px-4 py-3 text-left">Status</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {filteredUsers.map((user) => (
                    <tr key={user.id} className="transition-colors hover:bg-secondary">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <Avatar className="h-8 w-8">
                            <AvatarFallback className="bg-accent text-accent-foreground text-xs">
                              {user.name.split(" ").map(n => n[0]).join("")}
                            </AvatarFallback>
                          </Avatar>
                          <span className="text-sm font-medium text-foreground">{user.name}</span>
                        </div>
                      </td>
                      <td className="hidden px-4 py-3 text-sm text-muted-foreground sm:table-cell">
                        {user.studentId}
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
                            {user.online ? "Online" : user.lastSeen}
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
                            <DropdownMenuItem>
                              <Shield className="mr-2 h-4 w-4" /> Change Role
                            </DropdownMenuItem>
                            <DropdownMenuItem>
                              <Ban className="mr-2 h-4 w-4" /> Ban User
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem className="text-destructive">
                              <Trash2 className="mr-2 h-4 w-4" /> Delete User
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </TabsContent>

        {/* Groups Tab */}
        <TabsContent value="groups" className="space-y-4">
          <div className="relative max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search groups..."
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
                    <th className="px-4 py-3 text-left">Group</th>
                    <th className="hidden px-4 py-3 text-left sm:table-cell">Members</th>
                    <th className="hidden px-4 py-3 text-left md:table-cell">Files</th>
                    <th className="px-4 py-3 text-left">Last Active</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {mockGroups.map((group) => (
                    <tr key={group.id} className="transition-colors hover:bg-secondary">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <Avatar className="h-8 w-8">
                            <AvatarFallback className="bg-accent text-accent-foreground text-xs">
                              {group.name.split(" ").map(n => n[0]).slice(0, 2).join("")}
                            </AvatarFallback>
                          </Avatar>
                          <div>
                            <span className="text-sm font-medium text-foreground">{group.name}</span>
                            <p className="text-xs text-muted-foreground">{group.description}</p>
                          </div>
                        </div>
                      </td>
                      <td className="hidden px-4 py-3 text-sm text-muted-foreground sm:table-cell">
                        {group.members}
                      </td>
                      <td className="hidden px-4 py-3 text-sm text-muted-foreground md:table-cell">
                        {group.files}
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">{group.lastActive}</td>
                      <td className="px-4 py-3 text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button size="icon" variant="ghost" className="h-7 w-7 text-muted-foreground">
                              <MoreVertical className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem>View Details</DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem className="text-destructive">
                              <Trash2 className="mr-2 h-4 w-4" /> Delete Group
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </TabsContent>

        {/* Files Tab */}
        <TabsContent value="files" className="space-y-4">
          <div className="relative max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search files..."
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
                    <th className="px-4 py-3 text-left">File</th>
                    <th className="hidden px-4 py-3 text-left sm:table-cell">Owner</th>
                    <th className="hidden px-4 py-3 text-left md:table-cell">Size</th>
                    <th className="px-4 py-3 text-left">Modified</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {mockDocuments.map((doc) => (
                    <tr key={doc.id} className="transition-colors hover:bg-secondary">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <FileText className="h-4 w-4 text-muted-foreground" />
                          <span className="text-sm font-medium text-foreground">{doc.name}</span>
                          {doc.shared && <Badge variant="secondary" className="text-xs">Shared</Badge>}
                        </div>
                      </td>
                      <td className="hidden px-4 py-3 text-sm text-muted-foreground sm:table-cell">
                        {doc.owner}
                      </td>
                      <td className="hidden px-4 py-3 text-sm text-muted-foreground md:table-cell">
                        {doc.size}
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">{doc.updatedAt}</td>
                      <td className="px-4 py-3 text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button size="icon" variant="ghost" className="h-7 w-7 text-muted-foreground">
                              <MoreVertical className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem>Download</DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem className="text-destructive">
                              <Trash2 className="mr-2 h-4 w-4" /> Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </TabsContent>

        {/* Activity Logs Tab */}
        <TabsContent value="logs" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base text-foreground">Recent Activity</CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[400px]">
                <div className="space-y-4">
                  {mockActivityLogs.map((log) => (
                    <div key={log.id} className="flex items-start gap-3">
                      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent">
                        <Activity className="h-4 w-4 text-accent-foreground" />
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
                        <p className="text-xs text-muted-foreground">{log.timestamp}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
