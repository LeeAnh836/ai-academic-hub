import { useState, useEffect, useCallback } from "react"
import {
  Users,
  Plus,
  Search,
  MessageCircle,
  MoreVertical,
  UserPlus,
  LogOut,
  Settings,
  X,
  Loader2,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
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
import { useNavigate } from "react-router-dom"
import { groupService } from "@/services/group.service"
import { messagingApi, type SearchUserResult } from "@/services/messaging.service"
import type { Group } from "@/types/api"
import { useTranslation } from "@/lib/i18n"
import { formatRelativeTime } from "@/utils/format.utils"

function getInitials(name: string) {
  return name.split(" ").map(n => n[0]).slice(0, 2).join("").toUpperCase()
}

interface GroupMemberInfo {
  id: string
  group_id: string
  user_id: string
  role: string
  joined_at: string | null
  user: {
    id: string
    username: string
    full_name: string | null
    avatar_url: string | null
    student_id: string | null
  } | null
}

export function GroupsPage() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null)
  const [groups, setGroups] = useState<Group[]>([])
  const [loading, setLoading] = useState(true)

  // Create group dialog
  const [createOpen, setCreateOpen] = useState(false)
  const [newGroupName, setNewGroupName] = useState("")
  const [memberSearch, setMemberSearch] = useState("")
  const [memberSearchResults, setMemberSearchResults] = useState<SearchUserResult[]>([])
  const [selectedMembers, setSelectedMembers] = useState<SearchUserResult[]>([])
  const [creating, setCreating] = useState(false)

  // Detail panel
  const [detailMembers, setDetailMembers] = useState<GroupMemberInfo[]>([])
  const [loadingMembers, setLoadingMembers] = useState(false)

  // Invite dialog in detail panel
  const [inviteOpen, setInviteOpen] = useState(false)
  const [inviteSearch, setInviteSearch] = useState("")
  const [inviteSearchResults, setInviteSearchResults] = useState<SearchUserResult[]>([])
  const [invitingId, setInvitingId] = useState<string | null>(null)

  const loadGroups = useCallback(async () => {
    try {
      setLoading(true)
      const data = await groupService.listGroups(0, 100)
      setGroups(data)
    } catch (err) {
      console.error("Failed to load groups:", err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadGroups()
  }, [loadGroups])

  // Search members for create dialog
  useEffect(() => {
    if (!memberSearch.trim()) {
      setMemberSearchResults([])
      return
    }
    const timer = setTimeout(async () => {
      try {
        const results = await messagingApi.searchUsers(memberSearch)
        setMemberSearchResults(results)
      } catch (err) {
        console.error("Failed to search users:", err)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [memberSearch])

  // Search users for invite
  useEffect(() => {
    if (!inviteSearch.trim()) {
      setInviteSearchResults([])
      return
    }
    const timer = setTimeout(async () => {
      try {
        const results = await messagingApi.searchUsers(inviteSearch)
        // Filter out existing members
        const existingIds = new Set(detailMembers.map((m) => m.user_id))
        setInviteSearchResults(results.filter((u) => !existingIds.has(u.id)))
      } catch (err) {
        console.error("Failed to search users:", err)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [inviteSearch, detailMembers])

  // Load members when selecting a group
  useEffect(() => {
    if (!selectedGroupId) {
      setDetailMembers([])
      return
    }
    let cancelled = false
    const load = async () => {
      setLoadingMembers(true)
      try {
        const members = await groupService.listMembers(selectedGroupId)
        if (!cancelled) setDetailMembers(members as unknown as GroupMemberInfo[])
      } catch (err) {
        console.error("Failed to load members:", err)
      } finally {
        if (!cancelled) setLoadingMembers(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [selectedGroupId])

  const filteredGroups = groups.filter((g) =>
    g.group_name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const activeGroup = groups.find((g) => g.id === selectedGroupId)

  const handleCreateGroup = async () => {
    if (!newGroupName.trim()) return
    setCreating(true)
    try {
      const group = await groupService.createGroup({
        group_name: newGroupName.trim(),
        group_type: "chat",
        is_public: false,
      })
      // Add members
      for (const m of selectedMembers) {
        await groupService.addMember(group.id, m.id)
      }
      setCreateOpen(false)
      setNewGroupName("")
      setSelectedMembers([])
      setMemberSearch("")
      setMemberSearchResults([])
      await loadGroups()
    } catch (err) {
      console.error("Failed to create group:", err)
    } finally {
      setCreating(false)
    }
  }

  const handleLeaveGroup = async (groupId: string) => {
    try {
      await groupService.leaveGroup(groupId)
      if (selectedGroupId === groupId) setSelectedGroupId(null)
      await loadGroups()
    } catch (err) {
      console.error("Failed to leave group:", err)
    }
  }

  const handleInviteMember = async (userId: string) => {
    if (!selectedGroupId) return
    setInvitingId(userId)
    try {
      await groupService.addMember(selectedGroupId, userId)
      setInviteSearchResults((prev) => prev.filter((u) => u.id !== userId))
      setInviteSearch("")
      // Reload members and groups
      const members = await groupService.listMembers(selectedGroupId)
      setDetailMembers(members as unknown as GroupMemberInfo[])
      await loadGroups()
    } catch (err) {
      console.error("Failed to invite member:", err)
    } finally {
      setInvitingId(null)
    }
  }

  return (
    <div className="space-y-6 p-4 md:p-6 lg:p-8">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t("groups.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("groups.subtitle")}</p>
        </div>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button className="gap-2 bg-primary text-primary-foreground hover:bg-primary/90">
              <Plus className="h-4 w-4" />
              {t("groups.createGroup")}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t("groups.createStudyGroup")}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-2">
              <div>
                <label className="text-sm font-medium text-foreground">{t("groups.groupName")}</label>
                <Input
                  placeholder={t("groups.groupNamePlaceholder")}
                  className="mt-1 bg-secondary"
                  value={newGroupName}
                  onChange={(e) => setNewGroupName(e.target.value)}
                />
              </div>
              <div>
                <label className="text-sm font-medium text-foreground">{t("groups.addMembers")}</label>
                <Input
                  placeholder={t("groups.searchStudents")}
                  className="mt-1 mb-2 bg-secondary"
                  value={memberSearch}
                  onChange={(e) => setMemberSearch(e.target.value)}
                />
                {selectedMembers.length > 0 && (
                  <div className="mb-2 flex flex-wrap gap-1">
                    {selectedMembers.map((m) => (
                      <Badge key={m.id} variant="secondary" className="gap-1">
                        {m.full_name || m.username}
                        <X
                          className="h-3 w-3 cursor-pointer"
                          onClick={() => setSelectedMembers((prev) => prev.filter((p) => p.id !== m.id))}
                        />
                      </Badge>
                    ))}
                  </div>
                )}
                <div className="max-h-40 space-y-2 overflow-y-auto">
                  {memberSearchResults.map((user) => {
                    const isSelected = selectedMembers.some((m) => m.id === user.id)
                    return (
                      <label
                        key={user.id}
                        className="flex items-center gap-3 rounded-lg p-2 cursor-pointer hover:bg-secondary"
                      >
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => {
                            if (isSelected) {
                              setSelectedMembers((prev) => prev.filter((p) => p.id !== user.id))
                            } else {
                              setSelectedMembers((prev) => [...prev, user])
                            }
                          }}
                          className="rounded border-border"
                        />
                        <Avatar className="h-7 w-7">
                          {user.avatar_url ? <AvatarImage src={user.avatar_url} /> : null}
                          <AvatarFallback className="bg-accent text-accent-foreground text-[10px]">
                            {getInitials(user.full_name || user.username)}
                          </AvatarFallback>
                        </Avatar>
                        <span className="text-sm text-foreground">{user.full_name || user.username}</span>
                      </label>
                    )
                  })}
                </div>
              </div>
              <Button
                className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
                disabled={!newGroupName.trim() || creating}
                onClick={handleCreateGroup}
              >
                {creating ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                {t("groups.createGroup")}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder={t("groups.searchGroups")}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="h-9 bg-card pl-9 text-sm"
        />
      </div>

      {/* Groups Grid & Detail */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : filteredGroups.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Users className="h-12 w-12 text-muted-foreground/40 mb-3" />
          <p className="text-muted-foreground">
            {searchQuery ? t("groups.noMatch") : t("groups.noGroups")}
          </p>
        </div>
      ) : (
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Groups List */}
        <div className={cn("space-y-4 lg:col-span-2", selectedGroupId && "hidden lg:block lg:col-span-1")}>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
            {filteredGroups.map((group) => (
              <Card
                key={group.id}
                className={cn(
                  "cursor-pointer transition-all hover:shadow-md",
                  selectedGroupId === group.id && "ring-2 ring-primary"
                )}
                onClick={() => setSelectedGroupId(group.id)}
              >
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    {group.member_avatars && group.member_avatars.length >= 2 ? (
                      <div className="relative h-12 w-12 shrink-0">
                        <Avatar className="absolute bottom-0 left-0 h-8 w-8 border-2 border-card">
                          {group.member_avatars[0].avatar_url ? <AvatarImage src={group.member_avatars[0].avatar_url} /> : null}
                          <AvatarFallback className="bg-secondary text-secondary-foreground text-[10px]">
                            {getInitials(group.member_avatars[0].full_name)}
                          </AvatarFallback>
                        </Avatar>
                        <Avatar className="absolute right-0 top-0 h-8 w-8 border-2 border-card">
                          {group.member_avatars[1].avatar_url ? <AvatarImage src={group.member_avatars[1].avatar_url} /> : null}
                          <AvatarFallback className="bg-accent text-accent-foreground text-[10px]">
                            {getInitials(group.member_avatars[1].full_name)}
                          </AvatarFallback>
                        </Avatar>
                      </div>
                    ) : (
                      <Avatar className="h-12 w-12 shrink-0">
                        <AvatarFallback className="bg-accent text-accent-foreground font-semibold">
                          {getInitials(group.group_name)}
                        </AvatarFallback>
                      </Avatar>
                    )}
                    <div className="flex-1 overflow-hidden">
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="text-sm font-semibold text-foreground">{group.group_name}</p>
                          <p className="text-xs text-muted-foreground">{group.description || t("groups.noDescription")}</p>
                        </div>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button size="icon" variant="ghost" className="h-7 w-7 shrink-0 text-muted-foreground" onClick={(e) => e.stopPropagation()}>
                              <MoreVertical className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={(e) => e.stopPropagation()}><Settings className="mr-2 h-4 w-4" /> {t("groups.settings")}</DropdownMenuItem>
                            <DropdownMenuItem onClick={(e) => { e.stopPropagation(); setSelectedGroupId(group.id); setInviteOpen(true) }}><UserPlus className="mr-2 h-4 w-4" /> {t("groups.invite")}</DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem className="text-destructive" onClick={(e) => { e.stopPropagation(); handleLeaveGroup(group.id) }}>
                              <LogOut className="mr-2 h-4 w-4" /> {t("groups.leaveGroup")}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                      <div className="mt-3 flex items-center gap-4 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Users className="h-3.5 w-3.5" /> {group.member_count} {t("common.members")}
                        </span>
                      </div>
                      <div className="mt-2 flex items-center justify-between">
                        <span className="text-xs text-muted-foreground">{t("groups.updatedTime", { time: formatRelativeTime(group.updated_at, t) })}</span>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 gap-1 text-xs text-primary"
                          onClick={(e) => { e.stopPropagation(); navigate("/messages", { state: { openGroupId: group.id } }) }}
                        >
                          <MessageCircle className="h-3 w-3" /> {t("groups.chat")}
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
        {selectedGroupId && activeGroup && (
          <Card className={cn("lg:col-span-2", !selectedGroupId && "hidden")}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {activeGroup.member_avatars && activeGroup.member_avatars.length >= 2 ? (
                    <div className="relative h-12 w-12 shrink-0">
                      <Avatar className="absolute bottom-0 left-0 h-8 w-8 border-2 border-card">
                        {activeGroup.member_avatars[0].avatar_url ? <AvatarImage src={activeGroup.member_avatars[0].avatar_url} /> : null}
                        <AvatarFallback className="bg-secondary text-secondary-foreground text-[10px]">
                          {getInitials(activeGroup.member_avatars[0].full_name)}
                        </AvatarFallback>
                      </Avatar>
                      <Avatar className="absolute right-0 top-0 h-8 w-8 border-2 border-card">
                        {activeGroup.member_avatars[1].avatar_url ? <AvatarImage src={activeGroup.member_avatars[1].avatar_url} /> : null}
                        <AvatarFallback className="bg-accent text-accent-foreground text-[10px]">
                          {getInitials(activeGroup.member_avatars[1].full_name)}
                        </AvatarFallback>
                      </Avatar>
                    </div>
                  ) : (
                    <Avatar className="h-12 w-12">
                      <AvatarFallback className="bg-accent text-accent-foreground font-semibold">
                        {getInitials(activeGroup.group_name)}
                      </AvatarFallback>
                    </Avatar>
                  )}
                  <div>
                    <CardTitle className="text-lg text-foreground">{activeGroup.group_name}</CardTitle>
                    <p className="text-sm text-muted-foreground">{activeGroup.description || t("groups.noDescription")}</p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-muted-foreground lg:hidden"
                  onClick={() => setSelectedGroupId(null)}
                >
                  {t("common.close")}
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Stats */}
              <div className="rounded-lg bg-secondary p-3 text-center">
                <p className="text-lg font-bold text-foreground">{activeGroup.member_count}</p>
                <p className="text-xs text-muted-foreground">{t("common.members")}</p>
              </div>

              {/* Actions */}
              <div className="flex gap-3">
                <Button className="flex-1 gap-2 bg-primary text-primary-foreground hover:bg-primary/90" onClick={() => navigate("/messages", { state: { openGroupId: activeGroup.id } })}>
                  <MessageCircle className="h-4 w-4" /> {t("groups.openChat")}
                </Button>
                <Button variant="outline" className="flex-1 gap-2 bg-transparent" onClick={() => setInviteOpen(!inviteOpen)}>
                  <UserPlus className="h-4 w-4" /> {t("groups.invite")}
                </Button>
              </div>

              {/* Invite Section */}
              {inviteOpen && (
                <div className="space-y-3">
                  <Input
                    placeholder={t("groups.searchInvite")}
                    value={inviteSearch}
                    onChange={(e) => setInviteSearch(e.target.value)}
                    className="bg-secondary"
                  />
                  {inviteSearchResults.length > 0 && (
                    <div className="max-h-40 space-y-1 overflow-y-auto">
                      {inviteSearchResults.map((user) => (
                        <div key={user.id} className="flex items-center gap-3 rounded-lg p-2 hover:bg-secondary">
                          <Avatar className="h-7 w-7">
                            {user.avatar_url ? <AvatarImage src={user.avatar_url} /> : null}
                            <AvatarFallback className="bg-accent text-accent-foreground text-[10px]">
                              {getInitials(user.full_name || user.username)}
                            </AvatarFallback>
                          </Avatar>
                          <span className="flex-1 text-sm text-foreground">{user.full_name || user.username}</span>
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 text-xs"
                            disabled={invitingId === user.id}
                            onClick={() => handleInviteMember(user.id)}
                          >
                            {invitingId === user.id ? <Loader2 className="h-3 w-3 animate-spin" /> : t("groups.invite")}
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Members */}
              <div>
                <h3 className="mb-3 text-sm font-medium text-foreground">{t("common.members")}</h3>
                {loadingMembers ? (
                  <div className="flex justify-center py-4">
                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                  </div>
                ) : (
                <div className="space-y-2">
                  {detailMembers.map((member) => (
                    <div key={member.id} className="flex items-center gap-3 rounded-lg p-2 hover:bg-secondary">
                      <Avatar className="h-8 w-8">
                        {member.user?.avatar_url ? <AvatarImage src={member.user.avatar_url} /> : null}
                        <AvatarFallback className="bg-accent text-accent-foreground text-xs">
                          {getInitials(member.user?.full_name || member.user?.username || "?")}
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex-1">
                        <p className="text-sm font-medium text-foreground">{member.user?.full_name || member.user?.username || "Unknown"}</p>
                        {member.user?.student_id && (
                          <p className="text-xs text-muted-foreground">{member.user.student_id}</p>
                        )}
                      </div>
                      <Badge variant="secondary" className="text-xs capitalize">
                        {member.role}
                      </Badge>
                    </div>
                  ))}
                </div>
                )}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
      )}
    </div>
  )
}
