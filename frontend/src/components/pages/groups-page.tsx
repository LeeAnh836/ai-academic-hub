import { useState } from "react"
import {
  Users,
  Plus,
  Search,
  FileText,
  MessageCircle,
  MoreVertical,
  UserPlus,
  LogOut,
  Settings,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Textarea } from "@/components/ui/textarea"
import { useApp } from "@/lib/app-context"
import { mockGroups, mockUsers, mockDocuments } from "@/lib/mock-data"

export function GroupsPage() {
  const { setCurrentPage } = useApp()
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null)

  const filteredGroups = mockGroups.filter((g) =>
    g.name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const activeGroup = mockGroups.find((g) => g.id === selectedGroup)

  return (
    <div className="space-y-6 p-4 md:p-6 lg:p-8">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Study Groups</h1>
          <p className="text-sm text-muted-foreground">Collaborate with your classmates</p>
        </div>
        <Dialog>
          <DialogTrigger asChild>
            <Button className="gap-2 bg-primary text-primary-foreground hover:bg-primary/90">
              <Plus className="h-4 w-4" />
              Create Group
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create Study Group</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-2">
              <div>
                <label className="text-sm font-medium text-foreground">Group Name</label>
                <Input placeholder="e.g. CS301 Study Group" className="mt-1 bg-secondary" />
              </div>
              <div>
                <label className="text-sm font-medium text-foreground">Description</label>
                <Textarea placeholder="What is this group about?" className="mt-1 bg-secondary resize-none" rows={3} />
              </div>
              <div>
                <label className="text-sm font-medium text-foreground">Add Members</label>
                <Input placeholder="Search students..." className="mt-1 mb-2 bg-secondary" />
                <div className="max-h-40 space-y-2 overflow-y-auto">
                  {mockUsers.slice(1, 6).map((user) => (
                    <label
                      key={user.id}
                      className="flex items-center gap-3 rounded-lg p-2 cursor-pointer hover:bg-secondary"
                    >
                      <input type="checkbox" className="rounded border-border" />
                      <Avatar className="h-7 w-7">
                        <AvatarFallback className="bg-accent text-accent-foreground text-[10px]">
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

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search groups..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="h-9 bg-card pl-9 text-sm"
        />
      </div>

      {/* Groups Grid & Detail */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Groups List */}
        <div className={cn("space-y-4 lg:col-span-2", selectedGroup && "hidden lg:block lg:col-span-1")}>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
            {filteredGroups.map((group) => (
              <Card
                key={group.id}
                className={cn(
                  "cursor-pointer transition-all hover:shadow-md",
                  selectedGroup === group.id && "ring-2 ring-primary"
                )}
                onClick={() => setSelectedGroup(group.id)}
              >
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <Avatar className="h-12 w-12 shrink-0">
                      <AvatarFallback className="bg-accent text-accent-foreground font-semibold">
                        {group.name.split(" ").map(n => n[0]).slice(0, 2).join("")}
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex-1 overflow-hidden">
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="text-sm font-semibold text-foreground">{group.name}</p>
                          <p className="text-xs text-muted-foreground">{group.description}</p>
                        </div>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button size="icon" variant="ghost" className="h-7 w-7 shrink-0 text-muted-foreground" onClick={(e) => e.stopPropagation()}>
                              <MoreVertical className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem><Settings className="mr-2 h-4 w-4" /> Settings</DropdownMenuItem>
                            <DropdownMenuItem><UserPlus className="mr-2 h-4 w-4" /> Invite</DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem className="text-destructive"><LogOut className="mr-2 h-4 w-4" /> Leave Group</DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                      <div className="mt-3 flex items-center gap-4 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Users className="h-3.5 w-3.5" /> {group.members} members
                        </span>
                        <span className="flex items-center gap-1">
                          <FileText className="h-3.5 w-3.5" /> {group.files} files
                        </span>
                      </div>
                      <div className="mt-2 flex items-center justify-between">
                        <span className="text-xs text-muted-foreground">Active {group.lastActive}</span>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 gap-1 text-xs text-primary"
                          onClick={(e) => { e.stopPropagation(); setCurrentPage("messages") }}
                        >
                          <MessageCircle className="h-3 w-3" /> Chat
                        </Button>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Group Detail */}
        {selectedGroup && activeGroup && (
          <Card className={cn("lg:col-span-2", !selectedGroup && "hidden")}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Avatar className="h-12 w-12">
                    <AvatarFallback className="bg-accent text-accent-foreground font-semibold">
                      {activeGroup.name.split(" ").map(n => n[0]).slice(0, 2).join("")}
                    </AvatarFallback>
                  </Avatar>
                  <div>
                    <CardTitle className="text-lg text-foreground">{activeGroup.name}</CardTitle>
                    <p className="text-sm text-muted-foreground">{activeGroup.description}</p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-muted-foreground lg:hidden"
                  onClick={() => setSelectedGroup(null)}
                >
                  Close
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Stats */}
              <div className="grid grid-cols-3 gap-4">
                <div className="rounded-lg bg-secondary p-3 text-center">
                  <p className="text-lg font-bold text-foreground">{activeGroup.members}</p>
                  <p className="text-xs text-muted-foreground">Members</p>
                </div>
                <div className="rounded-lg bg-secondary p-3 text-center">
                  <p className="text-lg font-bold text-foreground">{activeGroup.files}</p>
                  <p className="text-xs text-muted-foreground">Files</p>
                </div>
                <div className="rounded-lg bg-secondary p-3 text-center">
                  <p className="text-lg font-bold text-foreground">{activeGroup.lastActive}</p>
                  <p className="text-xs text-muted-foreground">Last Active</p>
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-3">
                <Button className="flex-1 gap-2 bg-primary text-primary-foreground hover:bg-primary/90" onClick={() => setCurrentPage("messages")}>
                  <MessageCircle className="h-4 w-4" /> Open Chat
                </Button>
                <Button variant="outline" className="flex-1 gap-2 bg-transparent">
                  <UserPlus className="h-4 w-4" /> Invite
                </Button>
              </div>

              {/* Members */}
              <div>
                <h3 className="mb-3 text-sm font-medium text-foreground">Members</h3>
                <div className="space-y-2">
                  {mockUsers.slice(0, activeGroup.members > 5 ? 5 : activeGroup.members).map((user) => (
                    <div key={user.id} className="flex items-center gap-3 rounded-lg p-2 hover:bg-secondary">
                      <div className="relative">
                        <Avatar className="h-8 w-8">
                          <AvatarFallback className="bg-accent text-accent-foreground text-xs">
                            {user.name.split(" ").map(n => n[0]).join("")}
                          </AvatarFallback>
                        </Avatar>
                        {user.online && (
                          <span className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full border-2 border-card bg-emerald-500" />
                        )}
                      </div>
                      <div className="flex-1">
                        <p className="text-sm font-medium text-foreground">{user.name}</p>
                        <p className="text-xs text-muted-foreground">{user.studentId}</p>
                      </div>
                      <Badge variant="secondary" className="text-xs">
                        {user.id === "u1" ? "Admin" : "Member"}
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>

              {/* Shared Files */}
              <div>
                <h3 className="mb-3 text-sm font-medium text-foreground">Shared Files</h3>
                <div className="space-y-2">
                  {mockDocuments.filter(d => d.shared).slice(0, 3).map((doc) => (
                    <div key={doc.id} className="flex items-center gap-3 rounded-lg bg-secondary p-3">
                      <FileText className="h-4 w-4 text-muted-foreground" />
                      <div className="flex-1 overflow-hidden">
                        <p className="truncate text-sm text-foreground">{doc.name}</p>
                        <p className="text-xs text-muted-foreground">{doc.size} &middot; {doc.updatedAt}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
