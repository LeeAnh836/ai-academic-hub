import {
  LayoutDashboard,
  Bot,
  MessageCircle,
  FileText,
  Users,
  Menu,
  Shield,
  User,
  GraduationCap,
  LogOut,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useApp } from "@/lib/app-context"
import { useAuth } from "@/hooks/use-auth"
import { useNavigate, useLocation } from "react-router-dom"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet"
import { getUserInitials, getUserDisplayName, getRoleLabel, isAdmin } from "@/utils/user.utils"
import { useToast } from "@/hooks/use-toast"
import { useState } from "react"

const bottomNavItems = [
  { id: "dashboard" as const, label: "Home", icon: LayoutDashboard, path: "/dashboard" },
  { id: "ai-chat" as const, label: "AI Chat", icon: Bot, path: "/ai-chat" },
  { id: "messages" as const, label: "Messages", icon: MessageCircle, badge: 7, path: "/messages" },
  { id: "documents" as const, label: "Files", icon: FileText, path: "/documents" },
  { id: "groups" as const, label: "Groups", icon: Users, path: "/groups" },
]

export function MobileHeader() {
  const { user, setUser } = useApp()
  const { logout } = useAuth()
  const { toast } = useToast()
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  
  // Don't render if user is not loaded yet
  if (!user) return null

  const handleLogout = async () => {
    try {
      await logout()
      setUser(null)
      setOpen(false)
      toast({
        title: "Đăng xuất thành công",
        description: "Bạn đã đăng xuất khỏi hệ thống",
      })
    } catch (error) {
      console.error("Logout error:", error)
      // Even if API call fails, still clear user state
      setUser(null)
      setOpen(false)
    }
  }

  const pageTitle: Record<string, string> = {
    "/dashboard": "Dashboard",
    "/ai-chat": "AI Chat",
    "/messages": "Messages",
    "/documents": "Documents",
    "/groups": "Groups",
    "/admin": "Admin Panel",
    "/settings": "Settings",
  }

  return (
    <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-border bg-card px-4 md:hidden">
      <div className="flex items-center gap-3">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <GraduationCap className="h-4 w-4" />
        </div>
        <span className="font-semibold text-foreground">{pageTitle[location.pathname] || "Dashboard"}</span>
      </div>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger asChild>
          <button className="text-muted-foreground">
            <Menu className="h-5 w-5" />
          </button>
        </SheetTrigger>
        <SheetContent side="right" className="w-[260px] bg-card p-0">
          <div className="flex flex-col h-full">
            <div className="flex items-center gap-3 border-b border-border p-4">
              <Avatar className="h-10 w-10">
                {user.avatar_url && (
                  <AvatarImage 
                    src={`${user.avatar_url}?t=${new Date(user.updated_at || Date.now()).getTime()}`} 
                    alt={getUserDisplayName(user)} 
                  />
                )}
                <AvatarFallback className="bg-primary text-primary-foreground text-sm">
                  {getUserInitials(user)}
                </AvatarFallback>
              </Avatar>
              <div>
                <p className="text-sm font-medium text-foreground">{getUserDisplayName(user)}</p>
                <p className="text-xs text-muted-foreground">{getRoleLabel(user.role)}</p>
              </div>
            </div>
            <nav className="flex-1 p-3 space-y-1">
              {isAdmin(user) && (
                <button
                  onClick={() => { navigate("/admin"); setOpen(false) }}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                    location.pathname === "/admin"
                      ? "bg-accent text-accent-foreground"
                      : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                  )}
                >
                  <Shield className="h-5 w-5" />
                  Admin Panel
                </button>
              )}
              <button
                onClick={() => { navigate("/settings"); setOpen(false) }}
                className={cn(
                  "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  location.pathname === "/settings"
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                )}
              >
                <User className="h-5 w-5" />
                Settings
              </button>
            </nav>
            {/* Logout Button */}
            <div className="border-t border-border p-3">
              <button
                onClick={handleLogout}
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
              >
                <LogOut className="h-5 w-5" />
                Đăng xuất
              </button>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </header>
  )
}

export function MobileBottomNav() {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 flex h-16 items-center justify-around border-t border-border bg-card md:hidden">
      {bottomNavItems.map((item) => (
        <button
          key={item.id}
          onClick={() => navigate(item.path)}
          className={cn(
            "relative flex flex-col items-center gap-0.5 px-3 py-1 text-xs transition-colors",
            location.pathname === item.path
              ? "text-primary"
              : "text-muted-foreground"
          )}
        >
          <div className="relative">
            <item.icon className="h-5 w-5" />
            {item.badge && (
              <span className="absolute -right-2 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-medium text-destructive-foreground">
                {item.badge}
              </span>
            )}
          </div>
          <span className="font-medium">{item.label}</span>
        </button>
      ))}
    </nav>
  )
}
