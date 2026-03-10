import {
  LayoutDashboard,
  Bot,
  MessageCircle,
  FileText,
  Users,
  Shield,
  ChevronLeft,
  ChevronRight,
  LogOut,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useApp } from "@/lib/app-context"
import { useAuth } from "@/hooks/use-auth"
import { useNavigate, useLocation } from "react-router-dom"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { getUserInitials, getUserDisplayName, getRoleLabel, isAdmin } from "@/utils/user.utils"
import { useToast } from "@/hooks/use-toast"
import { useTranslation } from "@/lib/i18n"

const navItems = [
  { id: "ai-chat" as const, tKey: "nav.aiChat", icon: Bot, path: "/ai-chat" },
  { id: "dashboard" as const, tKey: "nav.dashboard", icon: LayoutDashboard, path: "/dashboard" },
  { id: "messages" as const, tKey: "nav.messages", icon: MessageCircle, path: "/messages" },
  { id: "documents" as const, tKey: "nav.documents", icon: FileText, path: "/documents" },
  { id: "groups" as const, tKey: "nav.groups", icon: Users, path: "/groups" },
]

const adminItems = [
  { id: "admin" as const, tKey: "nav.adminPanel", icon: Shield, path: "/admin" },
]

export function AppSidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const { user, setUser, unreadCount } = useApp()
  const { logout } = useAuth()
  const { toast } = useToast()
  const { t } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  
  // Don't render if user is not loaded yet
  if (!user) {
    return null
  }

  const handleLogout = async () => {
    try {
      await logout()
      setUser(null)
      toast({
        title: t("nav.logoutSuccess"),
        description: t("nav.logoutDesc"),
      })
    } catch (error) {
      console.error("Logout error:", error)
      // Even if API call fails, still clear user state
      setUser(null)
    }
  }

  return (
    <aside
      className={cn(
        "fixed left-0 top-0 z-30 flex h-full flex-col border-r border-border bg-card transition-all duration-300",
        collapsed ? "w-[68px]" : "w-[240px]"
      )}
    >
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 border-b border-border px-4">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-lg">
          <img 
            src="/logo.png"
            alt="Logo"
            className="h-full w-full object-contain"/>
        </div>
        {!collapsed && (
          <span className = "text-xl font-bold tracking-tight">
            <span className="text-[#2B6CB0]">Wise</span>
            <span className="text-[#7AC943]">ChatAI</span>
          </span>
          // <span className="text-xl font-bold bg-gradient-to-r from-blue-600 to-green-500 bg-clip-text text-transparent">
          //   WiseChatAI
          // </span>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-3">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => navigate(item.path)}
            className={cn(
              "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
              location.pathname === item.path
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:bg-secondary hover:text-foreground"
            )}
          >
            <item.icon className="h-5 w-5 shrink-0" />
            {!collapsed && (
              <>
                <span className="flex-1 text-left">{t(item.tKey)}</span>
                {item.id === "messages" && unreadCount > 0 && (
                  <Badge variant="destructive" className="h-5 min-w-5 px-1.5 text-xs">
                    {unreadCount > 99 ? "99+" : unreadCount}
                  </Badge>
                )}
              </>
            )}
            {collapsed && item.id === "messages" && unreadCount > 0 && (
              <Badge variant="destructive" className="absolute right-2 h-4 min-w-4 px-1 text-[10px]">
                {unreadCount > 99 ? "99+" : unreadCount}
              </Badge>
            )}
          </button>
        ))}

        {isAdmin(user) && (
          <>
            <div className={cn("my-3 border-t border-border", collapsed && "mx-2")} />
            {adminItems.map((item) => (
              <button
                key={item.id}
                onClick={() => navigate(item.path)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  location.pathname === item.path
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                )}
              >
                <item.icon className="h-5 w-5 shrink-0" />
                {!collapsed && <span className="flex-1 text-left">{t(item.tKey)}</span>}
              </button>
            ))}
          </>
        )}
      </nav>

      {/* Collapse toggle */}
      <div className="border-t border-border p-3">
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggle}
          className="w-full justify-center"
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </Button>
      </div>

      {/* User Profile */}
      <div className="border-t border-border p-3">
        <button
          onClick={() => navigate("/settings")}
          className={cn(
            "flex w-full items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-secondary",
            location.pathname === "/settings" && "bg-accent"
          )}
        >
          <Avatar className="h-8 w-8 shrink-0">
            {user.avatar_url && (
              <AvatarImage 
                src={`${user.avatar_url}?t=${new Date(user.updated_at || Date.now()).getTime()}`} 
                alt={getUserDisplayName(user, t)} 
              />
            )}
            <AvatarFallback className="bg-primary text-primary-foreground text-xs">
              {getUserInitials(user)}
            </AvatarFallback>
          </Avatar>
          {!collapsed && (
            <div className="flex-1 text-left">
              <p className="text-sm font-medium text-foreground">
                {getUserDisplayName(user, t)}
              </p>
              <p className="text-xs text-muted-foreground">
                {getRoleLabel(user.role, t)}
              </p>
            </div>
          )}
        </button>

        {/* Logout Button */}
        <button
          onClick={handleLogout}
          className={cn(
            "mt-2 flex w-full items-center gap-3 rounded-lg px-2 py-2 text-sm font-medium transition-colors",
            "text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
          )}
        >
          <LogOut className="h-5 w-5 shrink-0" />
          {!collapsed && <span className="flex-1 text-left">{t("nav.logout")}</span>}
        </button>
      </div>
    </aside>
  )
}
